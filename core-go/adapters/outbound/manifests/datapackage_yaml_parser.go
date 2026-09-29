package manifests

import (
	"bufio"
	"bytes"
	"context"
	"strconv"
	"strings"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

// DataPackageYAMLParser parses Frictionless DataPackage manifests formatted in YAML (.yaml and .yml).
type DataPackageYAMLParser struct{}

func NewDataPackageYAMLParser() *DataPackageYAMLParser {
	return &DataPackageYAMLParser{}
}

func (p *DataPackageYAMLParser) Name() string {
	return "datapackage-yaml"
}

func (p *DataPackageYAMLParser) CanParse(filenameOrURL string, data []byte) bool {
	lower := strings.ToLower(filenameOrURL)
	if strings.HasSuffix(lower, "datapackage.yaml") || strings.HasSuffix(lower, "datapackage.yml") {
		return true
	}
	content := string(data)
	return strings.Contains(content, "resources:") && (strings.Contains(content, "- name:") || strings.Contains(content, "  name:"))
}

func (p *DataPackageYAMLParser) ParseManifest(ctx context.Context, data []byte, baseURL string) (*domain.PackageManifest, error) {
	scanner := bufio.NewScanner(bytes.NewReader(data))

	manifest := &domain.PackageManifest{
		Format:    domain.PackageFormatDataPackageYAML,
		Resources: make([]domain.Resource, 0),
	}

	inResources := false
	inResourceFields := false
	var currentRes *domain.Resource

	flushCurrentResource := func() {
		if currentRes != nil && currentRes.Name != "" {
			if currentRes.Format == "" {
				currentRes.Format = inferFormatFromPath(currentRes.Path)
			}
			currentRes.Path = resolveResourcePath(baseURL, currentRes.Path)
			manifest.Resources = append(manifest.Resources, *currentRes)
			currentRes = nil
		}
	}

	for scanner.Scan() {
		line := scanner.Text()
		trimmed := strings.TrimSpace(line)
		if trimmed == "" || strings.HasPrefix(trimmed, "#") {
			continue
		}

		// Root keys
		if !inResources {
			if strings.HasPrefix(trimmed, "resources:") {
				inResources = true
				continue
			}

			parts := strings.SplitN(trimmed, ":", 2)
			if len(parts) == 2 {
				k := strings.ToLower(strings.TrimSpace(parts[0]))
				v := strings.Trim(strings.TrimSpace(parts[1]), "\"'")
				switch k {
				case "name":
					manifest.Name = v
				case "title":
					manifest.Title = v
				case "description":
					manifest.Description = v
				case "version":
					manifest.Version = v
				}
			}
			continue
		}

		// In resources list
		if strings.HasPrefix(trimmed, "- ") {
			flushCurrentResource()
			currentRes = &domain.Resource{}
			inResourceFields = false

			item := strings.TrimPrefix(trimmed, "- ")
			if strings.HasPrefix(item, "name:") {
				currentRes.Name = strings.Trim(strings.TrimSpace(strings.TrimPrefix(item, "name:")), "\"'")
			}
			continue
		}

		// Resource properties
		if currentRes != nil {
			if strings.HasPrefix(trimmed, "schema:") || strings.HasPrefix(trimmed, "fields:") {
				inResourceFields = true
				continue
			}

			if inResourceFields {
				// We don't need detailed column parsing for manifest resolution
				continue
			}

			parts := strings.SplitN(trimmed, ":", 2)
			if len(parts) == 2 {
				k := strings.ToLower(strings.TrimSpace(parts[0]))
				v := strings.Trim(strings.TrimSpace(parts[1]), "\"'")

				switch k {
				case "name":
					if currentRes.Name == "" {
						currentRes.Name = v
					}
				case "path":
					currentRes.Path = v
				case "format":
					currentRes.Format = strings.ToLower(v)
				case "hash", "hash_sha256":
					currentRes.HashSHA256 = v
				case "bytes", "bytes_count":
					if b, err := strconv.ParseInt(v, 10, 64); err == nil {
						currentRes.BytesCount = b
					}
				}
			}
		}
	}

	flushCurrentResource()

	return manifest, scanner.Err()
}
