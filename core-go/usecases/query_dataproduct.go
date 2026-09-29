package usecases

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
	"github.com/datosbolivia/datamesh-sdk/core-go/ports/outbound"
)

// QueryDataProductUseCase orchestrates fetching resource data and executing tabular and SQL queries.
type QueryDataProductUseCase struct {
	engine        outbound.QueryEnginePort
	storage       outbound.StoragePort
	triadResolver outbound.TriadResolverPort
	httpClient    *http.Client
}

// NewQueryDataProductUseCase initializes the query use case.
func NewQueryDataProductUseCase(
	engine outbound.QueryEnginePort,
	storage outbound.StoragePort,
	triadResolver outbound.TriadResolverPort,
) *QueryDataProductUseCase {
	return &QueryDataProductUseCase{
		engine:        engine,
		storage:       storage,
		triadResolver: triadResolver,
		httpClient:    &http.Client{},
	}
}

// ExecuteSQL parses canonical triads from a SQL statement, resolves physical paths, and delegates to the query engine.
func (uc *QueryDataProductUseCase) ExecuteSQL(ctx context.Context, sqlQuery string) (*domain.QueryResult, error) {
	triads := domain.ExtractTriadsFromSQL(sqlQuery)
	resolvedMap := make(map[string]domain.ResolvedResource)

	for _, t := range triads {
		key := t.String()
		if uc.triadResolver != nil {
			res, err := uc.triadResolver.ResolveTriad(ctx, t)
			if err != nil {
				return nil, fmt.Errorf("failed to resolve triad '%s': %w", key, err)
			}
			resolvedMap[key] = *res
		} else {
			// Fallback: assume local or direct
			resolvedMap[key] = domain.ResolvedResource{
				Triad:       t,
				PhysicalURI: t.Resource,
				Format:      "csv",
			}
		}
	}

	req := domain.SQLQueryRequest{
		SQLQuery:       sqlQuery,
		Triads:         triads,
		ResolvedTables: resolvedMap,
	}

	return uc.engine.ExecuteSQL(ctx, req)
}

// Query executes a tabular query against a target resource URI.
func (uc *QueryDataProductUseCase) Query(ctx context.Context, req domain.QueryRequest) (*domain.QueryResult, error) {
	if strings.TrimSpace(req.ResourceURI) == "" {
		return nil, fmt.Errorf("resource URI cannot be empty")
	}

	data, format, err := uc.loadResourceData(ctx, req.ResourceURI)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch resource data: %w", err)
	}

	return uc.engine.Execute(ctx, req, data, format)
}

func (uc *QueryDataProductUseCase) loadResourceData(ctx context.Context, uri string) ([]byte, string, error) {
	format := strings.TrimPrefix(strings.ToLower(filepath.Ext(uri)), ".")
	if format == "" {
		format = "csv"
	}

	// 1. Try cached storage if available
	if uc.storage != nil {
		if exists, _ := uc.storage.Exists(ctx, uri); exists {
			data, err := uc.storage.Load(ctx, uri)
			if err == nil {
				return data, format, nil
			}
		}
	}

	// 2. Local file
	if strings.HasPrefix(uri, "file://") || !strings.HasPrefix(uri, "http://") && !strings.HasPrefix(uri, "https://") {
		localPath := strings.TrimPrefix(uri, "file://")
		data, err := os.ReadFile(localPath)
		return data, format, err
	}

	// 3. Remote HTTP fetch
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodGet, uri, nil)
	if err != nil {
		return nil, "", err
	}
	resp, err := uc.httpClient.Do(httpReq)
	if err != nil {
		return nil, "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, "", fmt.Errorf("HTTP error %d %s", resp.StatusCode, resp.Status)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, "", err
	}

	// Cache to storage if available
	if uc.storage != nil {
		_ = uc.storage.Save(ctx, uri, body)
	}

	return body, format, nil
}
