package outbound

import (
	"context"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

// PublisherTargetPort defines the outbound adapter contract for publishing a dataset to a specific platform.
type PublisherTargetPort interface {
	Name() string
	CanPublish(target string) bool
	Publish(ctx context.Context, manifest *domain.PackageManifest, datasetPath string, options map[string]interface{}) (domain.PublicationTargetResult, error)
}
