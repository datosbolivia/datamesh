package domain

import (
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	"errors"
	"fmt"
	"regexp"
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

// ParseOpenSSHEd25519PublicKey parses an OpenSSH authorized_keys line (e.g. "ssh-ed25519 AAAAC3... user@host")
// and extracts the 32-byte Ed25519 public key and its hex representation.
func ParseOpenSSHEd25519PublicKey(authorizedKeyLine string) (ed25519.PublicKey, string, error) {
	clean := strings.TrimSpace(authorizedKeyLine)
	fields := strings.Fields(clean)
	if len(fields) < 2 {
		return nil, "", errors.New("invalid openssh key format: expected 'ssh-ed25519 <base64>'")
	}
	if fields[0] != "ssh-ed25519" {
		return nil, "", fmt.Errorf("unsupported key type '%s', only 'ssh-ed25519' is supported", fields[0])
	}

	raw, err := base64.StdEncoding.DecodeString(fields[1])
	if err != nil {
		return nil, "", fmt.Errorf("failed to base64-decode openssh key: %w", err)
	}

	// Wire format: [4 bytes type len] [11 bytes "ssh-ed25519"] [4 bytes key len] [32 bytes key]
	if len(raw) < 4+11+4+ed25519.PublicKeySize {
		return nil, "", errors.New("openssh public key wire buffer is too short")
	}

	typeLen := binary.BigEndian.Uint32(raw[0:4])
	if typeLen != 11 || string(raw[4:4+typeLen]) != "ssh-ed25519" {
		return nil, "", errors.New("mismatched key type inside ssh wire format")
	}

	offset := 4 + typeLen
	keyLen := binary.BigEndian.Uint32(raw[offset : offset+4])
	if int(keyLen) != ed25519.PublicKeySize {
		return nil, "", fmt.Errorf("expected ed25519 key length %d, got %d", ed25519.PublicKeySize, keyLen)
	}

	pubKeyBytes := raw[offset+4 : offset+4+keyLen]
	pubKeyHex := hex.EncodeToString(pubKeyBytes)
	return ed25519.PublicKey(pubKeyBytes), pubKeyHex, nil
}

// MatchesGitHubSSHKey checks if claimedPubKey (either full line, base64 blob, or hex)
// matches any of the user's public keys fetched from https://github.com/<username>.keys.
func MatchesGitHubSSHKey(claimedPubKey string, githubKeysRaw string) (bool, string) {
	cleanClaimed := strings.TrimSpace(claimedPubKey)
	claimedHex := ""
	if strings.HasPrefix(cleanClaimed, "ssh-ed25519 ") {
		if _, h, err := ParseOpenSSHEd25519PublicKey(cleanClaimed); err == nil {
			claimedHex = h
		}
	} else if len(cleanClaimed) == 64 {
		claimedHex = strings.ToLower(cleanClaimed)
	}

	lines := strings.Split(githubKeysRaw, "\n")
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "ssh-ed25519 ") {
			_, ghHex, err := ParseOpenSSHEd25519PublicKey(trimmed)
			if err == nil {
				if claimedHex != "" && strings.EqualFold(claimedHex, ghHex) {
					return true, ghHex
				}
				fields := strings.Fields(trimmed)
				if len(fields) >= 2 && cleanClaimed == fields[1] {
					return true, ghHex
				}
			}
		}
	}
	return false, ""
}

var githubUserRegex = regexp.MustCompile(`^[a-zA-Z0-9]([a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$`)

// VerifyGitHubDID validates a did:github:<username> URI against claimedPubKey and fetched githubKeysRaw.
func VerifyGitHubDID(did string, claimedPubKey string, githubKeysRaw string) (bool, string, string, error) {
	trimmed := strings.TrimSpace(did)
	if !strings.HasPrefix(trimmed, "did:github:") {
		return false, "", "", errors.New("invalid DID scheme: expected prefix 'did:github:'")
	}
	user := strings.TrimPrefix(trimmed, "did:github:")
	if !githubUserRegex.MatchString(user) || strings.Contains(user, "--") {
		return false, user, "", fmt.Errorf("invalid GitHub username '%s' in DID", user)
	}

	matches, hexKey := MatchesGitHubSSHKey(claimedPubKey, githubKeysRaw)
	return matches, user, hexKey, nil
}
