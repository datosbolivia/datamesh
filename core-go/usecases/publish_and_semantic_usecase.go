package usecases

import (
	"context"
	"fmt"
	"strings"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
	"github.com/datosbolivia/datamesh-sdk/core-go/ports/outbound"
)

// PublishDatasetUseCase orchestrates publishing an ODKF dataset to multiple platforms.
type PublishDatasetUseCase struct {
	reader     outbound.UnifiedMetadataReaderPort
	publishers []outbound.PublisherTargetPort
}

// NewPublishDatasetUseCase creates a new instance of PublishDatasetUseCase.
func NewPublishDatasetUseCase(reader outbound.UnifiedMetadataReaderPort, publishers ...outbound.PublisherTargetPort) *PublishDatasetUseCase {
	return &PublishDatasetUseCase{
		reader:     reader,
		publishers: publishers,
	}
}

// RegisterPublisher appends a new publisher adapter.
func (uc *PublishDatasetUseCase) RegisterPublisher(p outbound.PublisherTargetPort) {
	uc.publishers = append(uc.publishers, p)
}

// Publish executes publishing across the requested targets.
func (uc *PublishDatasetUseCase) Publish(
	ctx context.Context,
	datasetPath string,
	targets []string,
	options map[string]interface{},
) ([]domain.PublicationTargetResult, error) {
	if len(targets) == 0 {
		targets = []string{"local"}
	}

	var manifest *domain.PackageManifest
	var err error
	if uc.reader != nil {
		manifest, err = uc.reader.ReadPackage(ctx, datasetPath)
	}
	if err != nil || manifest == nil {
		// Fallback minimal manifest
		manifest = &domain.PackageManifest{
			Name:  datasetPath,
			Title: datasetPath,
		}
	}

	var results []domain.PublicationTargetResult
	for _, target := range targets {
		matched := false
		for _, pub := range uc.publishers {
			if pub.CanPublish(target) {
				matched = true
				res, pubErr := pub.Publish(ctx, manifest, datasetPath, options)
				if pubErr != nil {
					res.Success = false
					res.Error = pubErr.Error()
				}
				results = append(results, res)
				break
			}
		}
		if !matched {
			results = append(results, domain.PublicationTargetResult{
				Target:  target,
				Success: false,
				Error:   fmt.Sprintf("no publisher adapter registered for target '%s'", target),
			})
		}
	}

	return results, nil
}

// SemanticAlignmentUseCase provides concept alignment and SQL CASE expression generation.
type SemanticAlignmentUseCase struct{}

// NewSemanticAlignmentUseCase creates a new instance of SemanticAlignmentUseCase.
func NewSemanticAlignmentUseCase() *SemanticAlignmentUseCase {
	return &SemanticAlignmentUseCase{}
}

// GenerateCaseExpression builds a SQL CASE expression mapping raw codes to canonical concept IDs.
func (uc *SemanticAlignmentUseCase) GenerateCaseExpression(mapping domain.SemanticFieldMapping, tablePrefix string) string {
	col := mapping.FieldName
	if tablePrefix != "" {
		col = fmt.Sprintf("%s.%s", tablePrefix, mapping.FieldName)
	}
	if len(mapping.ValueMapping) == 0 {
		return col
	}

	var whenClauses []string
	for rawVal, conceptID := range mapping.ValueMapping {
		escapedVal := strings.ReplaceAll(rawVal, "'", "''")
		escapedConcept := strings.ReplaceAll(conceptID, "'", "''")
		whenClauses = append(whenClauses, fmt.Sprintf("WHEN %s = '%s' THEN '%s'", col, escapedVal, escapedConcept))
	}

	return fmt.Sprintf("(CASE %s ELSE %s END)", strings.Join(whenClauses, " "), col)
}
