package outbound

import (
	"context"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

// QueryEnginePort abstracts execution of tabular queries on raw or cached resource bytes.
type QueryEnginePort interface {
	Execute(ctx context.Context, req domain.QueryRequest, rawData []byte, format string) (*domain.QueryResult, error)
	ExecuteSQL(ctx context.Context, req domain.SQLQueryRequest) (*domain.QueryResult, error)
}
