package outbound

import (
	"context"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

// TriadResolverPort resolves a canonical 'catalogo:dataset:resource' triad into a physical URL and format.
type TriadResolverPort interface {
	ResolveTriad(ctx context.Context, triad domain.ResourceTriad) (*domain.ResolvedResource, error)
}
