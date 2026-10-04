package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
	"github.com/datosbolivia/datamesh-sdk/core-go/usecases"
)

// ServerConfig defines options for datamesh serve.
type ServerConfig struct {
	Port         string
	Host         string
	EnableProxy  bool
	EnableMcp    bool
	EnableCors   bool
}

// StartDataMeshServer boots the HTTP REST, CORS proxy, and JSON-RPC / MCP server.
func StartDataMeshServer(
	cfg ServerConfig,
	catalogUC *usecases.DiscoverCatalogUseCase,
	dataProductUC *usecases.ResolveDataProductUseCase,
	queryUC *usecases.QueryDataProductUseCase,
	appCfg domain.Config,
) error {
	mux := http.NewServeMux()

	// 1. Health check
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		enableCorsHeaders(w)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":  "ok",
			"service": "datamesh-server",
			"version": "0.2.0",
			"time":    time.Now().UTC().Format(time.RFC3339),
		})
	})

	// 2. CORS Proxy Endpoint (/proxy?url=...)
	mux.HandleFunc("/proxy", func(w http.ResponseWriter, r *http.Request) {
		enableCorsHeaders(w)
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusOK)
			return
		}

		targetURL := r.URL.Query().Get("url")
		if targetURL == "" {
			http.Error(w, `{"error": "Missing 'url' query parameter"}`, http.StatusBadRequest)
			return
		}

		parsedURL, err := url.Parse(targetURL)
		if err != nil || (parsedURL.Scheme != "http" && parsedURL.Scheme != "https") {
			http.Error(w, `{"error": "Invalid target URL scheme"}`, http.StatusBadRequest)
			return
		}

		req, err := http.NewRequestWithContext(r.Context(), http.MethodGet, targetURL, nil)
		if err != nil {
			http.Error(w, fmt.Sprintf(`{"error": "%s"}`, err.Error()), http.StatusInternalServerError)
			return
		}

		req.Header.Set("User-Agent", "DataMesh-Sovereign-Proxy/0.2.0 (+https://datosbolivia.org)")
		client := &http.Client{Timeout: 30 * time.Second}
		resp, err := client.Do(req)
		if err != nil {
			http.Error(w, fmt.Sprintf(`{"error": "Proxy request failed: %s"}`, err.Error()), http.StatusBadGateway)
			return
		}
		defer resp.Body.Close()

		// Forward headers
		if ct := resp.Header.Get("Content-Type"); ct != "" {
			w.Header().Set("Content-Type", ct)
		}
		w.WriteHeader(resp.StatusCode)
		_, _ = io.Copy(w, resp.Body)
	})

	// 3. REST API: /api/catalog
	mux.HandleFunc("/api/catalog", func(w http.ResponseWriter, r *http.Request) {
		enableCorsHeaders(w)
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusOK)
			return
		}

		target := r.URL.Query().Get("url")
		ctx := r.Context()
		var cat *domain.Catalog
		var err error
		if target != "" {
			cat, err = catalogUC.Discover(ctx, target)
		} else {
			cat, err = catalogUC.DiscoverAll(ctx)
		}

		if err != nil {
			http.Error(w, fmt.Sprintf(`{"error": "%s"}`, err.Error()), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(cat)
	})

	// 4. REST API: /api/sql
	mux.HandleFunc("/api/sql", func(w http.ResponseWriter, r *http.Request) {
		enableCorsHeaders(w)
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusOK)
			return
		}

		var reqBody struct {
			Query string `json:"query"`
		}
		if r.Method == http.MethodPost {
			if err := json.NewDecoder(r.Body).Decode(&reqBody); err != nil {
				http.Error(w, `{"error": "Invalid JSON body"}`, http.StatusBadRequest)
				return
			}
		} else {
			reqBody.Query = r.URL.Query().Get("q")
		}

		if reqBody.Query == "" {
			http.Error(w, `{"error": "Missing SQL query"}`, http.StatusBadRequest)
			return
		}

		res, err := queryUC.ExecuteSQL(r.Context(), reqBody.Query)
		if err != nil {
			http.Error(w, fmt.Sprintf(`{"error": "%s"}`, err.Error()), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(res)
	})

	// 5. Model Context Protocol (MCP) JSON-RPC 2.0 Endpoint (/mcp)
	mux.HandleFunc("/mcp", func(w http.ResponseWriter, r *http.Request) {
		enableCorsHeaders(w)
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusOK)
			return
		}

		var rpcReq struct {
			JSONRPC string                 `json:"jsonrpc"`
			ID      interface{}            `json:"id"`
			Method  string                 `json:"method"`
			Params  map[string]interface{} `json:"params"`
		}

		if err := json.NewDecoder(r.Body).Decode(&rpcReq); err != nil {
			http.Error(w, `{"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "Parse error"}}`, http.StatusOK)
			return
		}

		resp := handleMcpRPC(r.Context(), rpcReq.Method, rpcReq.Params, rpcReq.ID, catalogUC, dataProductUC, queryUC)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	})

	addr := fmt.Sprintf("%s:%s", cfg.Host, cfg.Port)
	fmt.Fprintf(os.Stdout, "DataMesh Server listening on http://%s\n", addr)
	fmt.Fprintf(os.Stdout, "  Endpoints:\n")
	fmt.Fprintf(os.Stdout, "  - Health:     http://%s/health\n", addr)
	fmt.Fprintf(os.Stdout, "  - CORS Proxy: http://%s/proxy?url=<target_url>\n", addr)
	fmt.Fprintf(os.Stdout, "  - REST Cat:   http://%s/api/catalog\n", addr)
	fmt.Fprintf(os.Stdout, "  - REST SQL:   http://%s/api/sql?q=<sql_query>\n", addr)
	fmt.Fprintf(os.Stdout, "  - MCP RPC:    http://%s/mcp\n", addr)

	return http.ListenAndServe(addr, mux)
}

func enableCorsHeaders(w http.ResponseWriter) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
}

func handleMcpRPC(
	ctx context.Context,
	method string,
	params map[string]interface{},
	id interface{},
	catalogUC *usecases.DiscoverCatalogUseCase,
	dataProductUC *usecases.ResolveDataProductUseCase,
	queryUC *usecases.QueryDataProductUseCase,
) map[string]interface{} {
	switch method {
	case "initialize":
		return map[string]interface{}{
			"jsonrpc": "2.0",
			"id":      id,
			"result": map[string]interface{}{
				"protocolVersion": "2024-11-05",
				"serverInfo": map[string]interface{}{
					"name":    "datamesh-sovereign-server",
					"version": "0.2.0",
				},
				"capabilities": map[string]interface{}{
					"tools": map[string]interface{}{},
				},
			},
		}

	case "tools/list":
		return map[string]interface{}{
			"jsonrpc": "2.0",
			"id":      id,
			"result": map[string]interface{}{
				"tools": []map[string]interface{}{
					{
						"name":        "datamesh_discover_catalogs",
						"description": "Discovers and lists sovereign open data products across configured federated catalogs or a specified llms.txt URL.",
						"inputSchema": map[string]interface{}{
							"type": "object",
							"properties": map[string]interface{}{
								"catalog_url": map[string]interface{}{"type": "string", "description": "Optional catalog URL. If omitted, discovers across all configured sovereign catalogs."},
							},
						},
					},
					{
						"name":        "datamesh_search_catalog",
						"description": "Searches data products across sovereign catalogs by keyword matching title, description, or domain.",
						"inputSchema": map[string]interface{}{
							"type": "object",
							"properties": map[string]interface{}{
								"keyword":     map[string]interface{}{"type": "string", "description": "Search keyword (e.g. 'elecciones', 'creditos', 'aire')."},
								"catalog_url": map[string]interface{}{"type": "string", "description": "Optional catalog URL to scope search to."},
							},
							"required": []string{"keyword"},
						},
					},
					{
						"name":        "datamesh_get_dataproduct",
						"description": "Resolves an OKF v0.2 Data Product manifest and description from a node URI or URL.",
						"inputSchema": map[string]interface{}{
							"type": "object",
							"properties": map[string]interface{}{
								"uri": map[string]interface{}{"type": "string", "description": "Data product node URI or HTTP URL."},
							},
							"required": []string{"uri"},
						},
					},
					{
						"name":        "datamesh_query_resource",
						"description": "Queries a tabular CSV/TSV data product resource with column equality filters and row limits.",
						"inputSchema": map[string]interface{}{
							"type": "object",
							"properties": map[string]interface{}{
								"resource_uri": map[string]interface{}{"type": "string", "description": "Direct HTTP URL or local file path to the tabular file."},
								"filters":      map[string]interface{}{"type": "object", "description": "Key-value map of column names and filter values."},
								"limit":        map[string]interface{}{"type": "integer", "description": "Maximum number of rows to return."},
							},
							"required": []string{"resource_uri"},
						},
					},
					{
						"name":        "datamesh_sql_query",
						"description": "Executes full ANSI SQL queries with canonical triad table names 'catalogo:dataset:resource' or direct URLs.",
						"inputSchema": map[string]interface{}{
							"type": "object",
							"properties": map[string]interface{}{
								"sql_query": map[string]interface{}{"type": "string", "description": "Full ANSI SQL query."},
								"sql":       map[string]interface{}{"type": "string", "description": "Alternative alias for sql_query."},
							},
							"required": []string{"sql_query"},
						},
					},
					{
						"name":        "read_resource",
						"description": "Read remote or cached dataset resource through backend proxy",
						"inputSchema": map[string]interface{}{
							"type": "object",
							"properties": map[string]interface{}{
								"uri": map[string]interface{}{"type": "string"},
							},
							"required": []string{"uri"},
						},
					},
				},
			},
		}

	case "tools/call":
		toolName, _ := params["name"].(string)
		args, _ := params["arguments"].(map[string]interface{})
		if args == nil {
			args = make(map[string]interface{})
		}

		if toolName == "datamesh_sql_query" || toolName == "query_sql" {
			sqlQ, _ := args["sql_query"].(string)
			if sqlQ == "" {
				sqlQ, _ = args["sql"].(string)
			}
			res, err := queryUC.ExecuteSQL(ctx, sqlQ)
			if err != nil {
				return map[string]interface{}{
					"jsonrpc": "2.0",
					"id":      id,
					"result": map[string]interface{}{
						"isError": true,
						"content": []map[string]interface{}{
							{"type": "text", "text": fmt.Sprintf("SQL Error: %s", err.Error())},
						},
					},
				}
			}
			bytes, _ := json.Marshal(res)
			return map[string]interface{}{
				"jsonrpc": "2.0",
				"id":      id,
				"result": map[string]interface{}{
					"isError": false,
					"content": []map[string]interface{}{
						{"type": "text", "text": string(bytes)},
					},
				},
			}
		}

		if toolName == "datamesh_discover_catalogs" {
			catURL, _ := args["catalog_url"].(string)
			var cat *domain.Catalog
			var err error
			if catURL != "" {
				cat, err = catalogUC.Discover(ctx, catURL)
			} else {
				cat, err = catalogUC.DiscoverAll(ctx)
			}
			if err != nil {
				return map[string]interface{}{
					"jsonrpc": "2.0",
					"id":      id,
					"result": map[string]interface{}{
						"isError": true,
						"content": []map[string]interface{}{
							{"type": "text", "text": err.Error()},
						},
					},
				}
			}
			bytes, _ := json.Marshal(cat)
			return map[string]interface{}{
				"jsonrpc": "2.0",
				"id":      id,
				"result": map[string]interface{}{
					"isError": false,
					"content": []map[string]interface{}{
						{"type": "text", "text": string(bytes)},
					},
				},
			}
		}

		if toolName == "datamesh_search_catalog" {
			keyword, _ := args["keyword"].(string)
			catURL, _ := args["catalog_url"].(string)
			results, err := catalogUC.Search(ctx, catURL, keyword)
			if err != nil {
				return map[string]interface{}{
					"jsonrpc": "2.0",
					"id":      id,
					"result": map[string]interface{}{
						"isError": true,
						"content": []map[string]interface{}{
							{"type": "text", "text": err.Error()},
						},
					},
				}
			}
			bytes, _ := json.Marshal(results)
			return map[string]interface{}{
				"jsonrpc": "2.0",
				"id":      id,
				"result": map[string]interface{}{
					"isError": false,
					"content": []map[string]interface{}{
						{"type": "text", "text": string(bytes)},
					},
				},
			}
		}

		if toolName == "datamesh_get_dataproduct" {
			uri, _ := args["uri"].(string)
			dp, err := dataProductUC.Resolve(ctx, uri)
			if err != nil {
				return map[string]interface{}{
					"jsonrpc": "2.0",
					"id":      id,
					"result": map[string]interface{}{
						"isError": true,
						"content": []map[string]interface{}{
							{"type": "text", "text": err.Error()},
						},
					},
				}
			}
			bytes, _ := json.Marshal(dp)
			return map[string]interface{}{
				"jsonrpc": "2.0",
				"id":      id,
				"result": map[string]interface{}{
					"isError": false,
					"content": []map[string]interface{}{
						{"type": "text", "text": string(bytes)},
					},
				},
			}
		}

		if toolName == "datamesh_query_resource" {
			resURI, _ := args["resource_uri"].(string)
			limit := 0
			if lVal, ok := args["limit"].(float64); ok {
				limit = int(lVal)
			}
			filters := make(map[string]string)
			if fMap, ok := args["filters"].(map[string]interface{}); ok {
				for k, v := range fMap {
					filters[k] = fmt.Sprintf("%v", v)
				}
			}
			qRes, err := queryUC.Query(ctx, domain.QueryRequest{
				ResourceURI: resURI,
				Filters:     filters,
				Limit:       limit,
			})
			if err != nil {
				return map[string]interface{}{
					"jsonrpc": "2.0",
					"id":      id,
					"result": map[string]interface{}{
						"isError": true,
						"content": []map[string]interface{}{
							{"type": "text", "text": err.Error()},
						},
					},
				}
			}
			bytes, _ := json.Marshal(qRes)
			return map[string]interface{}{
				"jsonrpc": "2.0",
				"id":      id,
				"result": map[string]interface{}{
					"isError": false,
					"content": []map[string]interface{}{
						{"type": "text", "text": string(bytes)},
					},
				},
			}
		}

		if toolName == "read_resource" {
			uri, _ := args["uri"].(string)
			client := &http.Client{Timeout: 30 * time.Second}
			resp, err := client.Get(uri)
			if err != nil {
				return map[string]interface{}{
					"jsonrpc": "2.0",
					"id":      id,
					"result": map[string]interface{}{
						"isError": true,
						"content": []map[string]interface{}{
							{"type": "text", "text": err.Error()},
						},
					},
				}
			}
			defer resp.Body.Close()
			bodyBytes, _ := io.ReadAll(resp.Body)
			return map[string]interface{}{
				"jsonrpc": "2.0",
				"id":      id,
				"result": map[string]interface{}{
					"isError": false,
					"content": []map[string]interface{}{
						{"type": "text", "text": string(bodyBytes)},
					},
				},
			}
		}

		return map[string]interface{}{
			"jsonrpc": "2.0",
			"id":      id,
			"error": map[string]interface{}{
				"code":    -32601,
				"message": fmt.Sprintf("Tool not found: %s", toolName),
			},
		}

	case "ping":
		return map[string]interface{}{
			"jsonrpc": "2.0",
			"id":      id,
			"result":  "pong",
		}

	default:
		return map[string]interface{}{
			"jsonrpc": "2.0",
			"id":      id,
			"error": map[string]interface{}{
				"code":    -32601,
				"message": fmt.Sprintf("Method not found: %s", method),
			},
		}
	}
}
