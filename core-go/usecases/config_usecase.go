package usecases

import (
	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
	"github.com/datosbolivia/datamesh-sdk/core-go/ports/outbound"
)

// ConfigUseCase implements inbound.ConfigServicePort.
type ConfigUseCase struct {
	config domain.Config
}

// NewConfigUseCase initializes the config service using a loader or explicit config.
func NewConfigUseCase(loader outbound.ConfigLoaderPort, explicitPath string) (*ConfigUseCase, error) {
	cfg, err := loader.Load(explicitPath)
	if err != nil {
		return nil, err
	}
	if err := cfg.Validate(); err != nil {
		return nil, err
	}
	return &ConfigUseCase{config: cfg}, nil
}

// GetConfig returns the active immutable configuration snapshot.
func (uc *ConfigUseCase) GetConfig() domain.Config {
	return uc.config
}
