package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"

	"github.com/datosbolivia/datamesh-sdk/core-go/adapters/outbound/config"
	"github.com/datosbolivia/datamesh-sdk/core-go/adapters/outbound/resolvers"
	"github.com/datosbolivia/datamesh-sdk/core-go/adapters/outbound/storage"
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

	catalogUC := usecases.NewDiscoverCatalogUseCase(catalogResolver, cfg)
	dataProductUC := usecases.NewResolveDataProductUseCase(nodeResolver, fileStorage, cfg)

	ctx := context.Background()
	command := os.Args[1]

	switch command {
	case "catalog":
		targetURL := ""
		if len(os.Args) > 2 {
			targetURL = os.Args[2]
		}
		cat, err := catalogUC.Discover(ctx, targetURL)
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
	fmt.Println("  datamesh catalog [url]          Discover sovereign catalog (default: llms.txt)")
	fmt.Println("  datamesh search <keyword> [url] Search catalog entries")
	fmt.Println("  datamesh get <url_or_path>      Resolve and validate OKF v0.2 Data Product")
	fmt.Println("  datamesh config                 Print active merged configuration")
}
