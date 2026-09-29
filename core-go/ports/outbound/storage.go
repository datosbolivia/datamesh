package outbound

import (
	"context"
)

// StoragePort abstracts caching and reading binary or text payloads.
type StoragePort interface {
	Save(ctx context.Context, key string, data []byte) error
	Load(ctx context.Context, key string) ([]byte, error)
	Exists(ctx context.Context, key string) (bool, error)
}
