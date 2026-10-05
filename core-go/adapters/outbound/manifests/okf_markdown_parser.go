package manifests

import (
	"bufio"
	"bytes"
	"context"
	"errors"
	"strings"
	"time"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

// OKFMarkdownParser parses OKF v0.2 Markdown files (such as index.md) with YAML frontmatter.
type OKFMarkdownParser struct{}

func NewOKFMarkdownParser() *OKFMarkdownParser {
	return &OKFMarkdownParser{}
}

func (p *OKFMarkdownParser) Name() string {
	return "okf-markdown"
}

func (p *OKFMarkdownParser) CanParse(filenameOrURL string, data []byte) bool {
	lower := strings.ToLower(filenameOrURL)
	if strings.HasSuffix(lower, ".md") {
		return true
	}
	trimmed := strings.TrimSpace(string(data))
	return strings.HasPrefix(trimmed, "---")
}

func (p *OKFMarkdownParser) ParseManifest(ctx context.Context, data []byte, baseURL string) (*domain.PackageManifest, error) {
	manifest, body, err := ParseOKFFrontmatter(data)
	if err != nil {
		return nil, err
	}

	return &domain.PackageManifest{
		Title:       manifest.Title,
		Description: body,
		Format:      domain.PackageFormatOKFMarkdown,
		Version:     manifest.Lineage.Version,
		Resources:   make([]domain.Resource, 0),
		Metadata: map[string]interface{}{
			"dimensions": manifest.Dimensions,
			"type":       manifest.Type,
			"contracts":  manifest.Contracts,
		},
	}, nil
}

// ParseOKFFrontmatter extracts OKF domain.Manifest and Markdown body from raw markdown content.
func ParseOKFFrontmatter(data []byte) (domain.Manifest, string, error) {
	var manifest domain.Manifest
	scanner := bufio.NewScanner(bytes.NewReader(data))

	inFrontmatter := false
	var frontmatterLines []string
	var bodyLines []string

	for scanner.Scan() {
		line := scanner.Text()
		trimmed := strings.TrimSpace(line)

		if trimmed == "---" {
			if !inFrontmatter {
				inFrontmatter = true
				continue
			} else {
				inFrontmatter = false
				for scanner.Scan() {
					bodyLines = append(bodyLines, scanner.Text())
				}
				break
			}
		}

		if inFrontmatter {
			frontmatterLines = append(frontmatterLines, line)
		} else {
			bodyLines = append(bodyLines, line)
		}
	}

	if len(frontmatterLines) == 0 {
		return manifest, strings.Join(bodyLines, "\n"), errors.New("no YAML frontmatter found delimited by '---'")
	}

	manifest = parseManifestFromYAML(frontmatterLines)
	bodyDesc := strings.TrimSpace(strings.Join(bodyLines, "\n"))
	return manifest, bodyDesc, nil
}

func parseManifestFromYAML(lines []string) domain.Manifest {
	var m domain.Manifest
	currentSection := ""
	var currentContract domain.Contract

	for _, rawLine := range lines {
		trimmed := strings.TrimSpace(rawLine)
		if trimmed == "" || strings.HasPrefix(trimmed, "#") {
			continue
		}

		if strings.HasSuffix(trimmed, ":") {
			sec := strings.TrimSuffix(trimmed, ":")
			switch sec {
			case "dimensions", "contracts", "lineage":
				currentSection = sec
				continue
			}
		}

		// Handle list items
		if strings.HasPrefix(trimmed, "- ") {
			itemVal := strings.TrimPrefix(trimmed, "- ")
			if currentSection == "dimensions" {
				m.Dimensions = append(m.Dimensions, strings.Trim(itemVal, "\"'"))
				continue
			}
			if currentSection == "contracts" {
				if currentContract.Type != "" || currentContract.Path != "" {
					m.Contracts = append(m.Contracts, currentContract)
					currentContract = domain.Contract{}
				}
				if strings.Contains(itemVal, ":") {
					parts := strings.SplitN(itemVal, ":", 2)
					subK := strings.TrimSpace(parts[0])
					subV := strings.Trim(strings.TrimSpace(parts[1]), "\"'")
					if subK == "type" {
						currentContract.Type = subV
					} else if subK == "path" {
						currentContract.Path = subV
					}
				}
				continue
			}
		}

		// Key-Value parsing
		parts := strings.SplitN(trimmed, ":", 2)
		if len(parts) == 2 {
			k := strings.TrimSpace(parts[0])
			v := strings.Trim(strings.TrimSpace(parts[1]), "\"'")

			switch currentSection {
			case "contracts":
				if k == "path" {
					currentContract.Path = v
				} else if k == "type" {
					currentContract.Type = v
				}
			case "lineage":
				if k == "version" {
					m.Lineage.Version = v
				} else if k == "updated_at" {
					if t, err := time.Parse(time.RFC3339, v); err == nil {
						m.Lineage.UpdatedAt = t
					}
				}
			default:
				if k == "type" {
					m.Type = v
				} else if k == "title" {
					m.Title = v
				} else if k == "domain" || k == "dominio" {
					m.Dimensions = append(m.Dimensions, v)
				}
			}
		}
	}

	if currentContract.Type != "" || currentContract.Path != "" {
		m.Contracts = append(m.Contracts, currentContract)
	}

	if len(m.Dimensions) == 0 {
		m.Dimensions = []string{"core"}
	}

	return m
}
