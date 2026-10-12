package resolvers

import (
	"context"
	"errors"
	"testing"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
	"github.com/datosbolivia/datamesh-sdk/core-go/ports/outbound"
)

// fakeReader is a minimal UnifiedMetadataReaderPort that records the URI it was
// asked to read and returns a prepared DataProduct, proving the resolver only
// depends on the port and not on the concrete manifests adapter.
type fakeReader struct {
	dp     *domain.DataProduct
	err    error
	gotURL string
}

func (f *fakeReader) RegisterParser(parser outbound.ManifestParserPort) {}

func (f *fakeReader) ReadPackage(ctx context.Context, uriOrPath string) (*domain.PackageManifest, error) {
	return nil, errors.New("not implemented in test fake")
}

func (f *fakeReader) ReadNode(ctx context.Context, uriOrPath string) (*domain.DataProduct, error) {
	f.gotURL = uriOrPath
	return f.dp, f.err
}

func (f *fakeReader) ReadCatalog(ctx context.Context, uriOrPath string) (*domain.Catalog, error) {
	return nil, errors.New("not implemented in test fake")
}

func TestNodeDataProductResolver(t *testing.T) {
	want, _ := domain.NewDataProduct(
		"air_quality",
		domain.Manifest{
			Type:       "dataset",
			Title:      "Atlas Electoral y Elecciones Generales de Bolivia (1979-2025)",
			Dimensions: []string{"a", "b", "c", "d"},
		},
		"desc",
		nil,
	)
	reader := &fakeReader{dp: want}
	resolver := NewNodeDataProductResolver(reader)

	got, err := resolver.FetchDataProduct(context.Background(), "file:///tmp/node/index.md")
	if err != nil {
		t.Fatalf("unexpected error resolving node: %v", err)
	}
	if got != want {
		t.Fatalf("resolver did not delegate to the reader port: got %p want %p", got, want)
	}
	if reader.gotURL != "file:///tmp/node/index.md" {
		t.Errorf("resolved URL not forwarded to reader: %q", reader.gotURL)
	}
}
