package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"

	"github.com/datosbolivia/datamesh-sdk/core-go/adapters/outbound/config"
	"github.com/datosbolivia/datamesh-sdk/core-go/adapters/outbound/engine"
	"github.com/datosbolivia/datamesh-sdk/core-go/adapters/outbound/resolvers"
	"github.com/datosbolivia/datamesh-sdk/core-go/adapters/outbound/storage"
	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
	"github.com/datosbolivia/datamesh-sdk/core-go/usecases"
)

func main() {
	if len(os.Args) < 2 {
		printUsage()
		os.Exit(1)
	}

	// 1. Initialize Configuration
	cfgLoader := config.NewConfigLoader()
	cfg, err := cfgLoader.Load("")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error loading configuration: %v\n", err)
		os.Exit(1)
	}

	// 2. Wire Hexagonal Architecture
	catalogResolver := resolvers.NewLLMSTxtCatalogResolver(cfg.Base.Timeout)
	nodeResolver := resolvers.NewNodeDataProductResolver(cfg.Base.Timeout)
	fileStorage, err := storage.NewFileStorage(cfg.Base.StoragePath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error initializing storage: %v\n", err)
		os.Exit(1)
	}
	tabularEngine := engine.NewInMemTabularQueryEngine()

	catalogUC := usecases.NewDiscoverCatalogUseCase(catalogResolver, cfg)
	dataProductUC := usecases.NewResolveDataProductUseCase(nodeResolver, fileStorage, cfg)
	queryUC := usecases.NewQueryDataProductUseCase(tabularEngine, fileStorage)

	ctx := context.Background()
	command := os.Args[1]

	switch command {
	case "catalog":
		targetURL := ""
		if len(os.Args) > 2 {
			targetURL = os.Args[2]
		}
		var cat *domain.Catalog
		if targetURL != "" {
			cat, err = catalogUC.Discover(ctx, targetURL)
		} else {
			cat, err = catalogUC.DiscoverAll(ctx)
		}
		if err != nil {
			fmt.Fprintf(os.Stderr, "Catalog discovery failed: %v\n", err)
			os.Exit(1)
		}
		out, _ := json.MarshalIndent(cat, "", "  ")
		fmt.Println(string(out))

	case "search":
		if len(os.Args) < 3 {
			fmt.Fprintln(os.Stderr, "Usage: datamesh search <keyword> [catalog_url]")
			os.Exit(1)
		}
		keyword := os.Args[2]
		targetURL := ""
		if len(os.Args) > 3 {
			targetURL = os.Args[3]
		}
		results, err := catalogUC.Search(ctx, targetURL, keyword)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Search failed: %v\n", err)
			os.Exit(1)
		}
		out, _ := json.MarshalIndent(results, "", "  ")
		fmt.Println(string(out))

	case "get":
		if len(os.Args) < 3 {
			fmt.Fprintln(os.Stderr, "Usage: datamesh get <uri_or_url>")
			os.Exit(1)
		}
		dp, err := dataProductUC.Resolve(ctx, os.Args[2])
		if err != nil {
			fmt.Fprintf(os.Stderr, "Failed to resolve Data Product: %v\n", err)
			os.Exit(1)
		}
		out, _ := json.MarshalIndent(dp, "", "  ")
		fmt.Println(string(out))

	case "query":
		if len(os.Args) < 3 {
			fmt.Fprintln(os.Stderr, "Usage: datamesh query <resource_uri> [--filter key=val] [--limit N]")
			os.Exit(1)
		}
		resourceURI := os.Args[2]
		filters := make(map[string]string)
		limit := 0

		for i := 3; i < len(os.Args); i++ {
			if os.Args[i] == "--filter" && i+1 < len(os.Args) {
				kv := strings.SplitN(os.Args[i+1], "=", 2)
				if len(kv) == 2 {
					filters[kv[0]] = kv[1]
				}
				i++
			} else if os.Args[i] == "--limit" && i+1 < len(os.Args) {
				if l, err := strconv.Atoi(os.Args[i+1]); err == nil {
					limit = l
				}
				i++
			}
		}

		res, err := queryUC.Query(ctx, domain.QueryRequest{
			ResourceURI: resourceURI,
			Filters:     filters,
			Limit:       limit,
		})
		if err != nil {
			fmt.Fprintf(os.Stderr, "Query failed: %v\n", err)
			os.Exit(1)
		}
		out, _ := json.MarshalIndent(res, "", "  ")
		fmt.Println(string(out))

	case "config":
		out, _ := json.MarshalIndent(cfg, "", "  ")
		fmt.Println(string(out))

	default:
		printUsage()
		os.Exit(1)
	}
}

func printUsage() {
	fmt.Println("DataMesh Core CLI (Go)")
	fmt.Println("Usage:")
	fmt.Println("  datamesh catalog [url]                       Discover federated sovereign catalogs")
	fmt.Println("  datamesh search <keyword> [url]              Search catalog entries across catalogs")
	fmt.Println("  datamesh get <url_or_path>                   Resolve and validate OKF v0.2 Data Product")
	fmt.Println("  datamesh query <uri> [--filter k=v] [--limit N] Query tabular resource")
	fmt.Println("  datamesh config                              Print active merged configuration")
}
