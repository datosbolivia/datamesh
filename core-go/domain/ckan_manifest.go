package domain

import (
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
)

// ReconstructManifestFromCKAN transforms a raw CKANPackage (información, ADR 0014
// layer 2) into a canonical ODKF PackageManifest (conocimiento, layer 3). It is
// pure domain logic with no I/O, so any use case can depend on it without
// coupling to another use case.
func ReconstructManifestFromCKAN(pkg *CKANPackage) (*PackageManifest, error) {
	if pkg == nil {
		return nil, fmt.Errorf("cannot reconstruct OKF from a nil CKAN package")
	}

	manifestName := Slugify(pkg.Name)
	if manifestName == "" {
		manifestName = Slugify(pkg.Title)
	}

	resources := make([]Resource, 0, len(pkg.Resources))
	for _, r := range pkg.Resources {
		resFormat := strings.ToLower(strings.TrimSpace(r.Format))
		if resFormat == "" {
			resFormat = "csv"
		}
		resName := Slugify(r.Name)
		if resName == "" {
			resName = resourceNameFromID(r.ID)
		}

		resources = append(resources, Resource{
			Name:       resName,
			Path:       r.URL,
			Format:     resFormat,
			BytesCount: r.Size,
		})
	}

	// Extract extras: spatial, temporal, quality
	metadata := make(map[string]interface{})
	var spatialCoverage *SpatialCoverage
	var temporalCoverage *TemporalCoverage

	for _, extra := range pkg.Extras {
		key := strings.ToLower(strings.TrimSpace(extra.Key))
		valStr := fmt.Sprintf("%v", extra.Value)

		switch key {
		case "spatial", "spatial-coverage", "spatial_coverage":
			spatialCoverage = parseSpatialExtra(valStr)
		case "temporal_start", "temporal_start_date":
			if temporalCoverage == nil {
				temporalCoverage = &TemporalCoverage{}
			}
			temporalCoverage.Start = valStr
		case "temporal_end", "temporal_end_date":
			if temporalCoverage == nil {
				temporalCoverage = &TemporalCoverage{}
			}
			temporalCoverage.End = valStr
		case "frequency", "accrualperiodicity":
			if temporalCoverage == nil {
				temporalCoverage = &TemporalCoverage{}
			}
			temporalCoverage.Frequency = valStr
		default:
			metadata[extra.Key] = extra.Value
		}
	}

	if spatialCoverage != nil {
		metadata["spatial"] = spatialCoverage
	}
	if temporalCoverage != nil {
		metadata["temporal"] = temporalCoverage
	}

	tags := make([]string, 0, len(pkg.Tags))
	for _, t := range pkg.Tags {
		tags = append(tags, t.Name)
	}
	metadata["tags"] = tags

	if pkg.Organization != nil {
		metadata["publisher"] = pkg.Organization.Title
	}

	return &PackageManifest{
		Name:        manifestName,
		Title:       pkg.Title,
		Description: pkg.Notes,
		Format:      PackageFormatDataPackageYAML,
		Version:     pkg.Version,
		Resources:   resources,
		Metadata:    metadata,
	}, nil
}

// resourceNameFromID derives a stable, panic-free resource name from a CKAN
// resource identifier. It tolerates empty and arbitrarily short IDs (a bare
// r.ID[:8] would panic on IDs shorter than 8 characters).
func resourceNameFromID(id string) string {
	slug := Slugify(id)
	if slug == "" {
		return "resource"
	}
	runes := []rune(slug)
	if len(runes) > 8 {
		runes = runes[:8]
	}
	return "resource_" + string(runes)
}

func parseSpatialExtra(val string) *SpatialCoverage {
	val = strings.TrimSpace(val)
	if strings.HasPrefix(val, "{") {
		// GeoJSON BBox or geometry
		var geojson map[string]interface{}
		if err := json.Unmarshal([]byte(val), &geojson); err == nil {
			if bboxRaw, ok := geojson["bbox"].([]interface{}); ok && len(bboxRaw) == 4 {
				bbox := make([]float64, 4)
				for i := 0; i < 4; i++ {
					if f, ok := bboxRaw[i].(float64); ok {
						bbox[i] = f
					}
				}
				return &SpatialCoverage{
					BBox:        bbox,
					Granularity: "geojson",
				}
			}
		}
	} else if strings.Contains(val, ",") {
		parts := strings.Split(val, ",")
		if len(parts) == 4 {
			bbox := make([]float64, 4)
			valid := true
			for i, p := range parts {
				f, err := strconv.ParseFloat(strings.TrimSpace(p), 64)
				if err != nil {
					valid = false
					break
				}
				bbox[i] = f
			}
			if valid {
				return &SpatialCoverage{
					BBox:        bbox,
					Granularity: "bounding_box",
				}
			}
		}
	}
	return &SpatialCoverage{
		Country: val,
	}
}
