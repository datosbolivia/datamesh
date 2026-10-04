package usecases

import (
	"context"
	"testing"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

type mockPublisher struct {
	targetName string
}

func (m *mockPublisher) Name() string { return m.targetName }
func (m *mockPublisher) CanPublish(target string) bool { return target == m.targetName }
func (m *mockPublisher) Publish(ctx context.Context, manifest *domain.PackageManifest, datasetPath string, options map[string]interface{}) (domain.PublicationTargetResult, error) {
	return domain.PublicationTargetResult{
		Target:         m.targetName,
		Success:        true,
		DestinationURI: "file:///mock/destination",
		Message:        "published successfully",
	}, nil
}

func TestPublishDatasetUseCase(t *testing.T) {
	pub := &mockPublisher{targetName: "local"}
	uc := NewPublishDatasetUseCase(nil, pub)

	results, err := uc.Publish(context.Background(), "my-dataset", []string{"local", "kaggle"}, nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if len(results) != 2 {
		t.Fatalf("expected 2 results, got %d", len(results))
	}

	if !results[0].Success || results[0].Target != "local" {
		t.Errorf("expected local target success, got %+v", results[0])
	}

	if results[1].Success || results[1].Target != "kaggle" {
		t.Errorf("expected kaggle target failure (no adapter), got %+v", results[1])
	}
}

func TestSemanticAlignmentUseCase(t *testing.T) {
	uc := NewSemanticAlignmentUseCase()
	mapping := domain.SemanticFieldMapping{
		FieldName:  "cod_dep",
		ConceptRef: "concepts/departamentos.md",
		ValueMapping: map[string]string{
			"LPZ": "concept:departamentos:la_paz",
			"SCZ": "concept:departamentos:santa_cruz",
		},
	}

	expr := uc.GenerateCaseExpression(mapping, "t")
	if expr == "" {
		t.Fatalf("expected non-empty CASE expression")
	}
	if expr != "(CASE WHEN t.cod_dep = 'LPZ' THEN 'concept:departamentos:la_paz' WHEN t.cod_dep = 'SCZ' THEN 'concept:departamentos:santa_cruz' ELSE t.cod_dep END)" &&
		expr != "(CASE WHEN t.cod_dep = 'SCZ' THEN 'concept:departamentos:santa_cruz' WHEN t.cod_dep = 'LPZ' THEN 'concept:departamentos:la_paz' ELSE t.cod_dep END)" {
		t.Errorf("unexpected CASE expression output: %s", expr)
	}
}
