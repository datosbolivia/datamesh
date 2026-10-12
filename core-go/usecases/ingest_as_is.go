package usecases

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
	"github.com/datosbolivia/datamesh-sdk/core-go/ports/inbound"
	"github.com/datosbolivia/datamesh-sdk/core-go/ports/outbound"
)

// AsIsIngestUseCase orchestrates the dual discovery path defined in ADR 0013:
// conformant well-known first, then an as-is heuristic probe (llms.txt,
// datapackage.json/yaml/yml, index.md OKF, CKAN package_show), always converting
// the source into a canonical ODKF DataProduct; it also exposes ODKF export
// converters toward CKAN/Frictionless DataPackage and W3C DCAT.
type AsIsIngestUseCase struct {
	wellKnown     outbound.WellKnownResolverPort
	reader        outbound.UnifiedMetadataReaderPort
	ckanClient    outbound.CKANClientPort
	authProviders map[string]outbound.AuthProviderPort
}

var _ inbound.InteroperabilityServicePort = (*AsIsIngestUseCase)(nil)

// NewAsIsIngestUseCase constructs AsIsIngestUseCase; all ports are optional so the
// probe chain degrades gracefully when a port is not configured.
func NewAsIsIngestUseCase(
	wellKnown outbound.WellKnownResolverPort,
	reader outbound.UnifiedMetadataReaderPort,
	ckanClient outbound.CKANClientPort,
	authProviders map[string]outbound.AuthProviderPort,
) *AsIsIngestUseCase {
	if authProviders == nil {
		authProviders = make(map[string]outbound.AuthProviderPort)
	}
	return &AsIsIngestUseCase{
		wellKnown:     wellKnown,
		reader:        reader,
		ckanClient:    ckanClient,
		authProviders: authProviders,
	}
}

// Ingest resolves any target endpoint into a canonical ODKF DataProduct (ADR 0013).
// If every probe fails the last error is returned with per-stage context.
func (uc *AsIsIngestUseCase) Ingest(ctx context.Context, target, authType string) (*domain.DataProduct, error) {
	target = strings.TrimSpace(target)
	if target == "" {
		return nil, errors.New("ingest target cannot be empty")
	}

	errs := []string{}

	if uc.wellKnown != nil {
		if wk, err := uc.wellKnown.FetchWellKnown(ctx, target); err == nil && wk != nil {
			if dp, err := uc.ingestConformant(ctx, target, wk, authType); err == nil {
				return dp, nil
			} else {
				errs = append(errs, fmt.Sprintf("conformant: %v", err))
			}
		}
	}

	if uc.reader != nil {
		if dp, err := uc.reader.ReadNode(ctx, target); err == nil {
			return dp, nil
		} else {
			errs = append(errs, fmt.Sprintf("as-is reader: %v", err))
		}
	}

	if uc.ckanClient != nil {
		if dp, err := uc.ingestCKAN(ctx, target, authType); err == nil {
			return dp, nil
		} else {
			errs = append(errs, fmt.Sprintf("ckan: %v", err))
		}
	}

	if len(errs) == 0 {
		return nil, errors.New("no ingestion port is configured for target " + target)
	}
	return nil, fmt.Errorf("cannot ingest %q as ODKF: %s", target, strings.Join(errs, "; "))
}

// ingestConformant dispatches on the well-known catalog type (CU-14) to the idiomatic port.
func (uc *AsIsIngestUseCase) ingestConformant(ctx context.Context, target string, wk *domain.WellKnownDiscovery, authType string) (*domain.DataProduct, error) {
	switch strings.ToLower(wk.Catalog.Type) {
	case "okf", "git", "dcat":
		if uc.reader == nil {
			return nil, errors.New("reader port required for catalog type " + wk.Catalog.Type)
		}
		return uc.reader.ReadNode(ctx, target)
	case "ckan":
		base := wk.Catalog.APIEndpoint
		if base == "" {
			base = target
		}
		return uc.ingestCKAN(ctx, base, authType)
	default:
		return nil, fmt.Errorf("unsupported conformant catalog type %q", wk.Catalog.Type)
	}
}

// ingestCKAN reads a raw CKAN dataset as-is and reconstructs the ODKF DataProduct
// reusing the CKAN anticorruption layer and the domain reconstruction (CU-13 / ADR 0010).
func (uc *AsIsIngestUseCase) ingestCKAN(ctx context.Context, ckanBaseURL, authType string) (*domain.DataProduct, error) {
	if uc.ckanClient == nil {
		return nil, errors.New("CKAN client port is not configured")
	}

	id := ckanPackageID(ckanBaseURL)
	if id == "" {
		return nil, errors.New("target must select a CKAN dataset (package id or /dataset/<id> URL)")
	}

	auth := uc.authProviders[authType]
	pkg, err := uc.ckanClient.GetPackage(ctx, ckanBaseURL, id, auth)
	if err != nil {
		return nil, fmt.Errorf("failed to read CKAN package %q as-is: %w", id, err)
	}

	manifest, err := domain.ReconstructManifestFromCKAN(pkg)
	if err != nil {
		return nil, fmt.Errorf("failed to reconstruct ODKF from CKAN package %q: %w", id, err)
	}
	return dataProductFromManifest(manifest)
}

// ExportCKANDataPackage serializes an ODKF DataProduct as CKAN/Frictionless datapackage JSON.
func (uc *AsIsIngestUseCase) ExportCKANDataPackage(ctx context.Context, dp *domain.DataProduct) ([]byte, error) {
	if dp == nil {
		return nil, errors.New("data product is nil; cannot export")
	}
	return dp.ToCKANDataPackageJSON()
}

// ExportDCAT serializes an ODKF DataProduct as a W3C DCAT-AP dataset JSON-LD document.
func (uc *AsIsIngestUseCase) ExportDCAT(ctx context.Context, dp *domain.DataProduct) ([]byte, error) {
	if dp == nil {
		return nil, errors.New("data product is nil; cannot export")
	}
	return dp.ToDCATJSON()
}

// ckanPackageID extracts the dataset id from a CKAN catalog or package URL (the last
// non-empty path segment, ignoring known action suffixes that denote catalog hosts).
func ckanPackageID(target string) string {
	s := strings.TrimRight(strings.TrimSpace(target), "/")
	if i := strings.LastIndex(s, "/"); i >= 0 {
		s = s[i+1:]
	}
	switch s {
	case "api", "action", "package_show", "package_search", "status_show",
		"datastore_search", "datastore_search_sql", "dataset", "group", "organization":
		return ""
	}
	return s
}

// dataProductFromManifest elevates a normalized PackageManifest (información, ADR 0014
// layer 2) into a canonical ODKF DataProduct (conocimiento, layer 3), applying domain
// invariants (título, tipo, dimensiones) at the boundary.
func dataProductFromManifest(pm *domain.PackageManifest) (*domain.DataProduct, error) {
	dims, mtype := []string{"value"}, "dataset"
	if raw, ok := pm.Metadata["dimensions"]; ok {
		switch d := raw.(type) {
		case []interface{}:
			var dd []string
			for _, v := range d {
				if s, ok := v.(string); ok && s != "" {
					dd = append(dd, s)
				}
			}
			if len(dd) > 0 {
				dims = dd
			}
		case []string:
			if len(d) > 0 {
				dims = d
			}
		case string:
			if d != "" {
				dims = []string{d}
			}
		}
	}
	if t, ok := pm.Metadata["type"].(string); ok && t != "" {
		mtype = t
	}

	id := pm.Name
	if id == "" {
		id = domain.Slugify(pm.Title)
	}
	manifest := domain.Manifest{
		Type:       mtype,
		Title:      pm.Title,
		Dimensions: dims,
		Lineage: domain.Lineage{
			Version: pm.Version,
			Sources: []string{},
		},
	}
	return domain.NewDataProduct(id, manifest, pm.Description, pm.Resources)
}
