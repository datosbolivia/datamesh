package main

/*
#include <stdlib.h>
*/
import "C"
import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"sync"
	"unsafe"

	"github.com/datosbolivia/datamesh-sdk/core-go/adapters/outbound/config"
	"github.com/datosbolivia/datamesh-sdk/core-go/adapters/outbound/engine"
	"github.com/datosbolivia/datamesh-sdk/core-go/adapters/outbound/manifests"
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
	queryUC       *usecases.QueryDataProductUseCase
	validateUC    *usecases.ValidateUseCase
	inmemEngine   *engine.InMemTabularQueryEngine
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
	unifiedReader := manifests.NewUnifiedMetadataReader(cfg.Base.CatalogURL, cfg.Base.Timeout)
	catalogResolver := resolvers.NewLLMSTxtCatalogResolver(cfg.Base.Timeout)
	nodeResolver := resolvers.NewNodeDataProductResolver(cfg.Base.Timeout)
	fileStorage, err := storage.NewFileStorage(cfg.Base.StoragePath)
	if err != nil {
		return err
	}

	catalogUC = usecases.NewDiscoverCatalogUseCase(catalogResolver, cfg)
	dataProductUC = usecases.NewResolveDataProductUseCase(nodeResolver, fileStorage, cfg)
	inmemEngine = engine.NewInMemTabularQueryEngine()
	queryUC = usecases.NewQueryDataProductUseCase(inmemEngine, fileStorage, unifiedReader)
	validateUC = usecases.NewValidateUseCase(cfg.Base.Timeout)
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

//export DataMeshSearchCatalog
func DataMeshSearchCatalog(keyword *C.char, catalogURL *C.char) *C.char {
	ensureInit()
	if keyword == nil {
		return makeJSONResponse(nil, errors.New("empty search keyword"))
	}
	kw := C.GoString(keyword)
	var urlStr string
	if catalogURL != nil {
		urlStr = C.GoString(catalogURL)
	}

	entries, err := catalogUC.Search(context.Background(), urlStr, kw)
	return makeJSONResponse(entries, err)
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

//export DataMeshQueryResource
func DataMeshQueryResource(resourceURI *C.char, queryOptionsJSON *C.char) *C.char {
	ensureInit()
	if resourceURI == nil {
		return makeJSONResponse(nil, errors.New("empty resource URI"))
	}
	resURI := C.GoString(resourceURI)

	var req domain.QueryRequest
	req.ResourceURI = resURI
	if queryOptionsJSON != nil {
		optsStr := C.GoString(queryOptionsJSON)
		if strings.TrimSpace(optsStr) != "" {
			_ = json.Unmarshal([]byte(optsStr), &req)
		}
	}

	res, err := queryUC.Query(context.Background(), req)
	return makeJSONResponse(res, err)
}

//export DataMeshExecuteSQL
func DataMeshExecuteSQL(sqlQuery *C.char, optionsJSON *C.char) *C.char {
	ensureInit()
	if sqlQuery == nil {
		return makeJSONResponse(nil, errors.New("empty SQL query"))
	}
	queryStr := C.GoString(sqlQuery)

	var opts domain.QueryOptions
	if optionsJSON != nil {
		optsStr := C.GoString(optionsJSON)
		if strings.TrimSpace(optsStr) != "" {
			_ = json.Unmarshal([]byte(optsStr), &opts)
		}
	}

	res, err := queryUC.ExecuteSQLWithOptions(context.Background(), queryStr, opts)
	return makeJSONResponse(res, err)
}

//export DataMeshValidate
func DataMeshValidate(target *C.char) *C.char {
	ensureInit()
	if target == nil {
		return makeJSONResponse(nil, errors.New("empty validation target"))
	}
	targetStr := C.GoString(target)
	report, err := validateUC.Validate(context.Background(), targetStr)
	return makeJSONResponse(report, err)
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
