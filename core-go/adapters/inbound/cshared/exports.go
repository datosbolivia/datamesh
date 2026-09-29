package main

/*
#include <stdlib.h>
*/
import "C"
import (
	"context"
	"encoding/json"
	"strings"
	"sync"
	"unsafe"

	"github.com/datosbolivia/datamesh-sdk/core-go/adapters/outbound/config"
	"github.com/datosbolivia/datamesh-sdk/core-go/adapters/outbound/resolvers"
	"github.com/datosbolivia/datamesh-sdk/core-go/adapters/outbound/storage"
	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
	"github.com/datosbolivia/datamesh-sdk/core-go/usecases"
)

var (
	once          sync.Once
	activeConfig  domain.Config
	catalogUC     *usecases.DiscoverCatalogUseCase
	dataProductUC *usecases.ResolveDataProductUseCase
)

func initRuntime(configJSON string) error {
	cfgLoader := config.NewConfigLoader()
	cfg, err := cfgLoader.Load("")
	if err != nil {
		return err
	}

	if strings.TrimSpace(configJSON) != "" {
		var custom struct {
			CatalogURL  string                       `json:"catalog_url"`
			StoragePath string                       `json:"storage_path"`
			Adapters    map[string]map[string]string `json:"adapters"`
		}
		if err := json.Unmarshal([]byte(configJSON), &custom); err == nil {
			if custom.CatalogURL != "" {
				cfg.Base.CatalogURL = custom.CatalogURL
			}
			if custom.StoragePath != "" {
				cfg.Base.StoragePath = custom.StoragePath
			}
			if custom.Adapters != nil {
				for adp, kv := range custom.Adapters {
					k := strings.ToLower(adp)
					if cfg.Adapters[k] == nil {
						cfg.Adapters[k] = make(map[string]string)
					}
					for key, val := range kv {
						cfg.Adapters[k][strings.ToLower(key)] = val
					}
				}
			}
		}
	}

	activeConfig = cfg
	catalogResolver := resolvers.NewLLMSTxtCatalogResolver(cfg.Base.Timeout)
	nodeResolver := resolvers.NewNodeDataProductResolver(cfg.Base.Timeout)
	fileStorage, err := storage.NewFileStorage(cfg.Base.StoragePath)
	if err != nil {
		return err
	}

	catalogUC = usecases.NewDiscoverCatalogUseCase(catalogResolver, cfg)
	dataProductUC = usecases.NewResolveDataProductUseCase(nodeResolver, fileStorage, cfg)
	return nil
}

//export DataMeshInit
func DataMeshInit(configJSON *C.char) *C.char {
	var cfgStr string
	if configJSON != nil {
		cfgStr = C.GoString(configJSON)
	}

	var initErr error
	once.Do(func() {
		initErr = initRuntime(cfgStr)
	})

	if initErr != nil {
		return makeJSONResponse(nil, initErr)
	}
	return makeJSONResponse(map[string]interface{}{"status": "initialized", "config": activeConfig}, nil)
}

//export DataMeshDiscoverCatalog
func DataMeshDiscoverCatalog(catalogURL *C.char) *C.char {
	ensureInit()
	var urlStr string
	if catalogURL != nil {
		urlStr = C.GoString(catalogURL)
	}

	cat, err := catalogUC.Discover(context.Background(), urlStr)
	return makeJSONResponse(cat, err)
}

//export DataMeshResolveDataProduct
func DataMeshResolveDataProduct(uri *C.char) *C.char {
	ensureInit()
	if uri == nil {
		return makeJSONResponse(nil, domain.ErrInvalidCatalogURL)
	}

	dp, err := dataProductUC.Resolve(context.Background(), C.GoString(uri))
	return makeJSONResponse(dp, err)
}

//export DataMeshFreeString
func DataMeshFreeString(ptr *C.char) {
	if ptr != nil {
		C.free(unsafe.Pointer(ptr))
	}
}

func ensureInit() {
	once.Do(func() {
		_ = initRuntime("")
	})
}

func makeJSONResponse(data interface{}, err error) *C.char {
	resp := map[string]interface{}{
		"success": err == nil,
	}
	if err != nil {
		resp["error"] = err.Error()
	} else {
		resp["data"] = data
	}

	bytes, _ := json.Marshal(resp)
	return C.CString(string(bytes))
}

func main() {}
