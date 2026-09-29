package outbound

import (
	"context"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

// ManifestParserPort defines the extensible contract for parsing any package metadata standard
// (Frictionless datapackage.json/yaml/yml, OKF index.md frontmatter, DCAT, RO-Crate, etc.).
type ManifestParserPort interface {
	Name() string
	CanParse(filenameOrURL string, data []byte) bool
	ParseManifest(ctx context.Context, data []byte, baseURL string) (*domain.PackageManifest, error)
}

// UnifiedMetadataReaderPort coordinates heterogeneous manifest parsers and locates
// package descriptors (datapackage.json, datapackage.yaml, datapackage.yml, index.md, llms.txt).
type UnifiedMetadataReaderPort interface {
	RegisterParser(parser ManifestParserPort)
	ReadPackage(ctx context.Context, uriOrPath string) (*domain.PackageManifest, error)
	ReadNode(ctx context.Context, uriOrPath string) (*domain.DataProduct, error)
	ReadCatalog(ctx context.Context, uriOrPath string) (*domain.Catalog, error)
}
