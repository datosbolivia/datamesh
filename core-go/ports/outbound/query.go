package outbound

import (
	"context"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

// QueryEnginePort abstracts execution of tabular and SQL queries on heterogeneous data formats.
type QueryEnginePort interface {
	Name() string
	SupportsFormat(format string) bool
	SupportsCrossFormatJoin() bool
	Execute(ctx context.Context, req domain.QueryRequest, rawData []byte, format string) (*domain.QueryResult, error)
	ExecuteSQL(ctx context.Context, req domain.SQLQueryRequest) (*domain.QueryResult, error)
	RegisterTable(ctx context.Context, table domain.TableBinding) error
}

// QueryEngineRegistryPort defines a repository and selector of specialized query engines.
type QueryEngineRegistryPort interface {
	RegisterEngine(engine QueryEnginePort)
	GetEngine(name string) (QueryEnginePort, bool)
	SelectEngine(preferred string, formats []string) (QueryEnginePort, error)
}
