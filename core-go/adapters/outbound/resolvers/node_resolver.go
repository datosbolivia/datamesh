package resolvers

import (
	"bufio"
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

// NodeDataProductResolver fetches and parses OKF v0.2 Markdown files containing YAML frontmatter.
type NodeDataProductResolver struct {
	httpClient *http.Client
}

// NewNodeDataProductResolver initializes the node resolver.
func NewNodeDataProductResolver(timeout time.Duration) *NodeDataProductResolver {
	if timeout <= 0 {
		timeout = 30 * time.Second
	}
	return &NodeDataProductResolver{
		httpClient: &http.Client{Timeout: timeout},
	}
}

// FetchDataProduct retrieves markdown content from URL or local path and constructs a DataProduct aggregate.
func (r *NodeDataProductResolver) FetchDataProduct(ctx context.Context, resolvedURL string) (*domain.DataProduct, error) {
	raw, err := r.readContent(ctx, resolvedURL)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch node at %s: %w", resolvedURL, err)
	}

	manifest, desc, err := parseFrontmatter(raw)
	if err != nil {
		return nil, fmt.Errorf("failed to parse OKF frontmatter: %w", err)
	}

	dp, err := domain.NewDataProduct(resolvedURL, manifest, desc, nil)
	if err != nil {
		return nil, err
	}
	dp.RawContent = raw
	return dp, nil
}

func (r *NodeDataProductResolver) readContent(ctx context.Context, targetURL string) (string, error) {
	if strings.HasPrefix(targetURL, "file://") {
		localPath := strings.TrimPrefix(targetURL, "file://")
		data, err := os.ReadFile(localPath)
		return string(data), err
	}

	if !strings.HasPrefix(targetURL, "http://") && !strings.HasPrefix(targetURL, "https://") {
		// Treat as local file path
		data, err := os.ReadFile(targetURL)
		return string(data), err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, targetURL, nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("User-Agent", "datamesh-sdk/0.2 (Go-Core)")

	resp, err := r.httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("HTTP error %d %s", resp.StatusCode, resp.Status)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}
	return string(body), nil
}

func parseFrontmatter(content string) (domain.Manifest, string, error) {
	var manifest domain.Manifest
	scanner := bufio.NewScanner(strings.NewReader(content))

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
				// Collect remaining lines as body
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

	manifest = parseSimpleManifestYAML(frontmatterLines)
	bodyDesc := strings.TrimSpace(strings.Join(bodyLines, "\n"))
	return manifest, bodyDesc, nil
}

func parseSimpleManifestYAML(lines []string) domain.Manifest {
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
				if currentContract.Type != "" {
					m.Contracts = append(m.Contracts, currentContract)
					currentContract = domain.Contract{}
				}
				// Can be "- type: datapackage"
				if strings.HasPrefix(itemVal, "type:") {
					currentContract.Type = strings.Trim(strings.TrimSpace(strings.TrimPrefix(itemVal, "type:")), "\"'")
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
				}
			}
		}
	}

	if currentContract.Type != "" {
		m.Contracts = append(m.Contracts, currentContract)
	}

	return m
}
