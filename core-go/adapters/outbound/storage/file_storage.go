package storage

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
)

// FileStorage implements outbound.StoragePort persisting files safely under a root directory.
type FileStorage struct {
	baseDir string
	mu      sync.RWMutex
}

// NewFileStorage creates a filesystem storage adapter ensuring the base directory exists.
func NewFileStorage(baseDir string) (*FileStorage, error) {
	cleanBase := filepath.Clean(baseDir)
	if err := os.MkdirAll(cleanBase, 0755); err != nil {
		return nil, fmt.Errorf("failed to initialize storage directory %s: %w", cleanBase, err)
	}
	return &FileStorage{
		baseDir: cleanBase,
	}, nil
}

func (s *FileStorage) resolveSafePath(key string) (string, error) {
	cleanKey := filepath.Clean(key)
	if strings.Contains(cleanKey, "..") {
		return "", errors.New("path traversal detected in storage key")
	}
	fullPath := filepath.Join(s.baseDir, cleanKey)
	rel, err := filepath.Rel(s.baseDir, fullPath)
	if err != nil || strings.HasPrefix(rel, "..") {
		return "", errors.New("storage key escapes base directory boundary")
	}
	return fullPath, nil
}

// Save writes data to disk atomically.
func (s *FileStorage) Save(ctx context.Context, key string, data []byte) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	target, err := s.resolveSafePath(key)
	if err != nil {
		return err
	}

	if err := os.MkdirAll(filepath.Dir(target), 0755); err != nil {
		return err
	}

	tmpFile := target + ".tmp"
	if err := os.WriteFile(tmpFile, data, 0644); err != nil {
		return err
	}
	return os.Rename(tmpFile, target)
}

// Load reads data from disk.
func (s *FileStorage) Load(ctx context.Context, key string) ([]byte, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	target, err := s.resolveSafePath(key)
	if err != nil {
		return nil, err
	}
	return os.ReadFile(target)
}

// Exists checks if a given key exists in storage.
func (s *FileStorage) Exists(ctx context.Context, key string) (bool, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	target, err := s.resolveSafePath(key)
	if err != nil {
		return false, err
	}
	_, err = os.Stat(target)
	if err == nil {
		return true, nil
	}
	if os.IsNotExist(err) {
		return false, nil
	}
	return false, err
}
