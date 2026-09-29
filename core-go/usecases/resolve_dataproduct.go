package usecases

import (
	"context"
	"errors"
	"strings"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
	"github.com/datosbolivia/datamesh-sdk/core-go/ports/outbound"
)

var ErrInvalidDataProductURI = errors.New("invalid or empty data product URI")

// ResolveDataProductUseCase coordinates fetching and validating OKF Data Products.
type ResolveDataProductUseCase struct {
	resolver outbound.DataProductResolverPort
	storage  outbound.StoragePort
	config   domain.Config
}

// NewResolveDataProductUseCase creates an initialized data product use case.
func NewResolveDataProductUseCase(
	resolver outbound.DataProductResolverPort,
	storage outbound.StoragePort,
	cfg domain.Config,
) *ResolveDataProductUseCase {
	return &ResolveDataProductUseCase{
		resolver: resolver,
		storage:  storage,
		config:   cfg,
	}
}

// Resolve loads a DataProduct and enforces OKF v0.2 validation rules.
func (uc *ResolveDataProductUseCase) Resolve(ctx context.Context, uriOrURL string) (*domain.DataProduct, error) {
	trimmed := strings.TrimSpace(uriOrURL)
	if trimmed == "" {
		return nil, ErrInvalidDataProductURI
	}

	dp, err := uc.resolver.FetchDataProduct(ctx, trimmed)
	if err != nil {
		return nil, err
	}

	if err := dp.Validate(); err != nil {
		return nil, err
	}

	return dp, nil
}

// Validate executes domain verification logic on an existing DataProduct instance.
func (uc *ResolveDataProductUseCase) Validate(ctx context.Context, dp *domain.DataProduct) error {
	if dp == nil {
		return errors.New("data product cannot be nil")
	}
	return dp.Validate()
}
