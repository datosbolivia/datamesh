package outbound

import (
	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

// ConfigLoaderPort abstracts reading configurations from files and environment variables.
type ConfigLoaderPort interface {
	Load(explicitFilePath string) (domain.Config, error)
}
