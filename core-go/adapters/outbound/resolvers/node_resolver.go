package resolvers

import (
	"context"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
	"github.com/datosbolivia/datamesh-sdk/core-go/ports/outbound"
)

// NodeDataProductResolver fetches and parses OKF v0.2 Markdown files and package
// manifests by delegating to the UnifiedMetadataReader port. Depending on the
// port (instead of the concrete manifests adapter) keeps outbound adapters
// decoupled from each other and lets the composition root inject any reader.
type NodeDataProductResolver struct {
	reader outbound.UnifiedMetadataReaderPort
}

// NewNodeDataProductResolver initializes the node resolver with a metadata reader port.
func NewNodeDataProductResolver(reader outbound.UnifiedMetadataReaderPort) *NodeDataProductResolver {
	return &NodeDataProductResolver{reader: reader}
}

// FetchDataProduct retrieves node data (index.md, datapackage.json/yaml/yml, or node directory)
// and constructs a DataProduct aggregate.
func (r *NodeDataProductResolver) FetchDataProduct(ctx context.Context, resolvedURL string) (*domain.DataProduct, error) {
	return r.reader.ReadNode(ctx, resolvedURL)
}
