package domain

import (
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"strings"
)

var (
	ErrInvalidHexKey       = errors.New("invalid hex-encoded public key")
	ErrInvalidHexSignature = errors.New("invalid hex-encoded signature")
	ErrInvalidKeyLength    = errors.New("ed25519 public key must be exactly 32 bytes (64 hex characters)")
	ErrInvalidSigLength    = errors.New("ed25519 signature must be exactly 64 bytes (128 hex characters)")
)

// ComputeSHA256 returns standard lowercase hex sha256 checksum.
func ComputeSHA256(data []byte) string {
	h := sha256.Sum256(data)
	return hex.EncodeToString(h[:])
}

// VerifySHA256 checks if data matches expected hex hash (with optional 'sha256:' prefix).
func VerifySHA256(data []byte, expectedHash string) bool {
	cleanExpected := strings.ToLower(strings.TrimSpace(expectedHash))
	cleanExpected = strings.TrimPrefix(cleanExpected, "sha256:")
	computed := ComputeSHA256(data)
	return computed == cleanExpected
}

// VerifyEd25519Signature validates digital authorship of message against an Ed25519 public key.
func VerifyEd25519Signature(publicKeyHex string, message []byte, signatureHex string) (bool, error) {
	cleanPubKey := strings.TrimSpace(publicKeyHex)
	pubBytes, err := hex.DecodeString(cleanPubKey)
	if err != nil {
		return false, ErrInvalidHexKey
	}
	if len(pubBytes) != ed25519.PublicKeySize {
		return false, ErrInvalidKeyLength
	}

	cleanSig := strings.TrimSpace(signatureHex)
	sigBytes, err := hex.DecodeString(cleanSig)
	if err != nil {
		return false, ErrInvalidHexSignature
	}
	if len(sigBytes) != ed25519.SignatureSize {
		return false, ErrInvalidSigLength
	}

	valid := ed25519.Verify(pubBytes, message, sigBytes)
	return valid, nil
}
