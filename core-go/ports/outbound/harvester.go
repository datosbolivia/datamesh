package outbound

import (
	"context"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

// AuthProviderPort defines outbound operations for injecting authentication headers into outgoing requests.
type AuthProviderPort interface {
	GetAuthHeaders(ctx context.Context) (map[string]string, error)
	GetAuthType() string
}

// WellKnownResolverPort defines outbound operations for discovering catalog configurations.
type WellKnownResolverPort interface {
	FetchWellKnown(ctx context.Context, targetURL string) (*domain.WellKnownDiscovery, error)
}

// CKANClientPort defines outbound operations for interacting with CKAN Action API v3.
type CKANClientPort interface {
	SearchPackages(ctx context.Context, baseURL string, query string, start, rows int, auth AuthProviderPort) ([]domain.CKANPackage, int, error)
	GetPackage(ctx context.Context, baseURL, packageID string, auth AuthProviderPort) (*domain.CKANPackage, error)
	GetDataStoreSchema(ctx context.Context, baseURL, resourceID string, auth AuthProviderPort) ([]domain.CKANDataStoreField, error)
}
