package usecases

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/datosbolivia/datamesh-sdk/core-go/validator"
)

type ValidateUseCase struct {
	httpClient *http.Client
}

func NewValidateUseCase(timeout time.Duration) *ValidateUseCase {
	if timeout <= 0 {
		timeout = 5 * time.Second
	}
	return &ValidateUseCase{
		httpClient: &http.Client{Timeout: timeout},
	}
}

// Validate inspects a path (file or bundle directory), URL, or triad string.
func (uc *ValidateUseCase) Validate(ctx context.Context, target string) (*validator.ValidationReport, error) {
	trimmed := strings.TrimSpace(target)
	if trimmed == "" {
		return nil, fmt.Errorf("target to validate cannot be empty")
	}

	// 1. HTTP/HTTPS URL
	if strings.HasPrefix(trimmed, "http://") || strings.HasPrefix(trimmed, "https://") {
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, trimmed, nil)
		if err != nil {
			return nil, fmt.Errorf("invalid url: %w", err)
		}
		req.Header.Set("User-Agent", "datamesh-sdk/0.2 (Go Validator)")
		resp, err := uc.httpClient.Do(req)
		if err != nil {
			return nil, fmt.Errorf("failed to fetch url: %w", err)
		}
		defer resp.Body.Close()

		bodyBytes, err := io.ReadAll(resp.Body)
		if err != nil {
			return nil, fmt.Errorf("failed to read response body: %w", err)
		}
		return validator.ValidateConceptContent(string(bodyBytes), trimmed), nil
	}

	// 2. Local filesystem path
	if fi, err := os.Stat(trimmed); err == nil {
		if fi.IsDir() {
			return validator.ValidateBundle(trimmed)
		}
		contentBytes, err := os.ReadFile(trimmed)
		if err != nil {
			return nil, fmt.Errorf("failed to read file '%s': %w", trimmed, err)
		}
		return validator.ValidateConceptContent(string(contentBytes), trimmed), nil
	}

	// 3. Fallback: check if it's a canonical triad
	if strings.Contains(trimmed, ":") || strings.Contains(trimmed, "/") {
		return validator.ValidateTriad(trimmed), nil
	}

	// 4. File not found
	return nil, fmt.Errorf("target '%s' not found as local file/directory or valid URL", trimmed)
}
