//go:build js && wasm
// +build js,wasm

package main

import (
	"context"
	"encoding/json"
	"fmt"
	"syscall/js"
	"time"

	"github.com/datosbolivia/datamesh-sdk/core-go/adapters/outbound/config"
	"github.com/datosbolivia/datamesh-sdk/core-go/adapters/outbound/engine"
	"github.com/datosbolivia/datamesh-sdk/core-go/adapters/outbound/manifests"
	"github.com/datosbolivia/datamesh-sdk/core-go/adapters/outbound/resolvers"
	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
	"github.com/datosbolivia/datamesh-sdk/core-go/usecases"
)

func main() {
	c := make(chan struct{}, 0)

	cfgLoader := config.NewConfigLoader()
	cfg, _ := cfgLoader.Load("")

	catalogResolver := resolvers.NewLLMSTxtCatalogResolver(15 * time.Second)
	nodeResolver := resolvers.NewNodeDataProductResolver(15 * time.Second)
	inmemEngine := engine.NewInMemTabularQueryEngine()
	unifiedReader := manifests.NewUnifiedMetadataReader(cfg.Base.CatalogURL, 15*time.Second)

	catalogUC := usecases.NewDiscoverCatalogUseCase(catalogResolver, cfg)
	dataProductUC := usecases.NewResolveDataProductUseCase(nodeResolver, nil, cfg)
	queryUC := usecases.NewQueryDataProductUseCase(inmemEngine, nil, unifiedReader)

	dataMeshObj := js.Global().Get("Object").New()

	// Promise-based discover
	dataMeshObj.Set("discover", js.FuncOf(func(this js.Value, args []js.Value) interface{} {
		targetURL := ""
		if len(args) > 0 && !args[0].IsNull() && !args[0].IsUndefined() {
			targetURL = args[0].String()
		}

		handler := js.FuncOf(func(pThis js.Value, pArgs []js.Value) interface{} {
			resolve := pArgs[0]
			reject := pArgs[1]

			go func() {
				cat, err := catalogUC.Discover(context.Background(), targetURL)
				if err != nil {
					reject.Invoke(js.ValueOf(err.Error()))
					return
				}
				bytes, _ := json.Marshal(cat)
				parsed := js.Global().Get("JSON").Call("parse", string(bytes))
				resolve.Invoke(parsed)
			}()
			return nil
		})

		return js.Global().Get("Promise").New(handler)
	}))

	// Promise-based resolve
	dataMeshObj.Set("resolve", js.FuncOf(func(this js.Value, args []js.Value) interface{} {
		if len(args) == 0 {
			return js.ValueOf("missing URI")
		}
		targetURI := args[0].String()

		handler := js.FuncOf(func(pThis js.Value, pArgs []js.Value) interface{} {
			resolve := pArgs[0]
			reject := pArgs[1]

			go func() {
				dp, err := dataProductUC.Resolve(context.Background(), targetURI)
				if err != nil {
					reject.Invoke(js.ValueOf(err.Error()))
					return
				}
				bytes, _ := json.Marshal(dp)
				parsed := js.Global().Get("JSON").Call("parse", string(bytes))
				resolve.Invoke(parsed)
			}()
			return nil
		})

		return js.Global().Get("Promise").New(handler)
	}))

	// Promise-based executeSQL
	dataMeshObj.Set("executeSQL", js.FuncOf(func(this js.Value, args []js.Value) interface{} {
		if len(args) == 0 {
			return js.ValueOf("missing SQL query")
		}
		queryStr := args[0].String()
		var opts domain.QueryOptions
		if len(args) > 1 && !args[1].IsNull() && !args[1].IsUndefined() {
			optsJSON := args[1].String()
			_ = json.Unmarshal([]byte(optsJSON), &opts)
		}

		handler := js.FuncOf(func(pThis js.Value, pArgs []js.Value) interface{} {
			resolve := pArgs[0]
			reject := pArgs[1]

			go func() {
				res, err := queryUC.ExecuteSQLWithOptions(context.Background(), queryStr, opts)
				if err != nil {
					reject.Invoke(js.ValueOf(err.Error()))
					return
				}
				bytes, _ := json.Marshal(res)
				parsed := js.Global().Get("JSON").Call("parse", string(bytes))
				resolve.Invoke(parsed)
			}()
			return nil
		})

		return js.Global().Get("Promise").New(handler)
	}))

	// Synchronous config getter
	dataMeshObj.Set("getConfig", js.FuncOf(func(this js.Value, args []js.Value) interface{} {
		bytes, _ := json.Marshal(cfg)
		return js.Global().Get("JSON").Call("parse", string(bytes))
	}))

	js.Global().Set("DataMesh", dataMeshObj)
	fmt.Println("DataMesh Core WASM runtime initialized")

	<-c
}
