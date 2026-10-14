package domain

import (
	"bytes"
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"encoding/binary"
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

func TestParseOpenSSHEd25519PublicKey_Valid(t *testing.T) {
	pubKey, _, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatalf("failed to generate key: %v", err)
	}

	var buf []byte
	var typeLen [4]byte
	binary.BigEndian.PutUint32(typeLen[:], 11)
	buf = append(buf, typeLen[:]...)
	buf = append(buf, []byte("ssh-ed25519")...)

	var keyLen [4]byte
	binary.BigEndian.PutUint32(keyLen[:], uint32(len(pubKey)))
	buf = append(buf, keyLen[:]...)
	buf = append(buf, pubKey...)

	b64Key := base64.StdEncoding.EncodeToString(buf)
	line := "ssh-ed25519 " + b64Key + " testuser@github"

	parsedKey, hexStr, err := ParseOpenSSHEd25519PublicKey(line)
	if err != nil {
		t.Fatalf("failed to parse openssh key: %v", err)
	}

	if !bytes.Equal(parsedKey, pubKey) {
		t.Fatalf("parsed key does not match original pubKey")
	}

	expectedHex := hex.EncodeToString(pubKey)
	if hexStr != expectedHex {
		t.Fatalf("expected hex %s, got %s", expectedHex, hexStr)
	}

	matches, matchedHex := MatchesGitHubSSHKey(line, line)
	if !matches || matchedHex != expectedHex {
		t.Fatalf("expected github key match")
	}

	matchesBlob, _ := MatchesGitHubSSHKey(b64Key, line)
	if !matchesBlob {
		t.Fatalf("expected github key match using base64 blob")
	}
}

func TestVerifyGitHubDID(t *testing.T) {
	pubKey, _, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatalf("failed to generate key: %v", err)
	}

	var buf []byte
	var typeLen [4]byte
	binary.BigEndian.PutUint32(typeLen[:], 11)
	buf = append(buf, typeLen[:]...)
	buf = append(buf, []byte("ssh-ed25519")...)

	var keyLen [4]byte
	binary.BigEndian.PutUint32(keyLen[:], uint32(len(pubKey)))
	buf = append(buf, keyLen[:]...)
	buf = append(buf, pubKey...)

	b64Key := base64.StdEncoding.EncodeToString(buf)
	line := "ssh-ed25519 " + b64Key + " octocat@github"
	expectedHex := hex.EncodeToString(pubKey)

	// 1. Valid DID and matching key
	matched, username, hexKey, err := VerifyGitHubDID("did:github:octocat", line, line)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !matched || username != "octocat" || hexKey != expectedHex {
		t.Fatalf("expected valid match for octocat, got matched=%v, user=%s, hex=%s", matched, username, hexKey)
	}

	// 2. Mismatched key
	matchedMismatch, _, _, err := VerifyGitHubDID("did:github:octocat", "ssh-ed25519 AAAAC3dummykey octocat@github", line)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if matchedMismatch {
		t.Fatalf("expected false for mismatched key")
	}

	// 3. Invalid DID scheme
	_, _, _, err = VerifyGitHubDID("did:key:12345", line, line)
	if err == nil {
		t.Fatalf("expected error for non-github DID scheme")
	}

	// 4. Invalid username characters
	_, _, _, err = VerifyGitHubDID("did:github:invalid_user!", line, line)
	if err == nil {
		t.Fatalf("expected error for invalid username characters")
	}
}

