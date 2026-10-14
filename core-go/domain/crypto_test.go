package domain

import (
	"crypto/ed25519"
	"crypto/rand"
	"encoding/hex"
	"testing"
)

func TestVerifyEd25519Signature_Valid(t *testing.T) {
	pubKey, privKey, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatalf("failed to generate key: %v", err)
	}

	msg := []byte("manifest_hash:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
	sig := ed25519.Sign(privKey, msg)

	pubHex := hex.EncodeToString(pubKey)
	sigHex := hex.EncodeToString(sig)

	valid, err := VerifyEd25519Signature(pubHex, msg, sigHex)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !valid {
		t.Fatalf("expected signature to be valid")
	}
}

func TestVerifyEd25519Signature_TamperedMessage(t *testing.T) {
	pubKey, privKey, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatalf("failed to generate key: %v", err)
	}

	msg := []byte("original message")
	sig := ed25519.Sign(privKey, msg)

	pubHex := hex.EncodeToString(pubKey)
	sigHex := hex.EncodeToString(sig)

	tamperedMsg := []byte("tampered message")
	valid, err := VerifyEd25519Signature(pubHex, tamperedMsg, sigHex)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if valid {
		t.Fatalf("expected tampered message signature to be invalid")
	}
}

func TestVerifySHA256(t *testing.T) {
	data := []byte("test content")
	hash := ComputeSHA256(data)
	if !VerifySHA256(data, hash) {
		t.Fatalf("expected sha256 to verify")
	}
	if !VerifySHA256(data, "sha256:"+hash) {
		t.Fatalf("expected sha256 with prefix to verify")
	}
}
