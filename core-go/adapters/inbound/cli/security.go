package main

import (
	"fmt"
	"net"
	"net/url"
	"path/filepath"
	"strings"

	"github.com/datosbolivia/datamesh-sdk/core-go/domain"
)

// hostIsBlocked reports whether a host resolves to a loopback, private,
// link-local, multicast or unspecified address (SSRF guard for the outbound
// proxy and read_resource tool).
func hostIsBlocked(host string) bool {
	if strings.TrimSpace(host) == "" {
		return true
	}
	if strings.EqualFold(host, "localhost") {
		return true
	}
	ips, err := net.LookupIP(host)
	if err != nil || len(ips) == 0 {
		return true
	}
	for _, ip := range ips {
		if ip.IsLoopback() || ip.IsPrivate() || ip.IsLinkLocalUnicast() ||
			ip.IsLinkLocalMulticast() || ip.IsUnspecified() || ip.IsMulticast() {
			return true
		}
	}
	return false
}

// validateOutboundURL restricts outbound targets to http/https URLs pointing at
// non-private hosts.
func validateOutboundURL(raw string) (string, error) {
	parsed, err := url.Parse(raw)
	if err != nil {
		return "", fmt.Errorf("invalid target URL: %w", err)
	}
	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return "", fmt.Errorf("only http/https URLs are allowed")
	}
	if parsed.Hostname() == "" {
		return "", fmt.Errorf("target URL must include a host")
	}
	if hostIsBlocked(parsed.Hostname()) {
		return "", fmt.Errorf("host '%s' is not allowed by the outbound proxy policy", parsed.Hostname())
	}
	return raw, nil
}

// isRemoteOrTriad reports whether a resource reference is a remote http(s) URL
// or a canonical triad. Local filesystem paths are rejected at the MCP/HTTP
// boundary to prevent arbitrary local file reads.
func isRemoteOrTriad(ref string) bool {
	trimmed := strings.TrimSpace(ref)
	if strings.HasPrefix(trimmed, "http://") || strings.HasPrefix(trimmed, "https://") {
		return true
	}
	if isForbiddenLocalRef(trimmed) {
		return false
	}
	_, err := domain.ParseTriad(trimmed)
	return err == nil
}

// isForbiddenLocalRef reports whether a reference points at an arbitrary local
// file: absolute paths, file:// URIs, Windows drive-letter paths, dotted
// traversal, or shared-network UNC paths.
func isForbiddenLocalRef(ref string) bool {
	if ref == "" {
		return true
	}
	if strings.HasPrefix(ref, "file://") || strings.HasPrefix(ref, "\\\\") {
		return true
	}
	if filepath.IsAbs(ref) {
		return true
	}
	if len(ref) >= 2 && ref[1] == ':' {
		c := ref[0]
		if (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') {
			return true
		}
	}
	for _, seg := range strings.Split(strings.ReplaceAll(ref, "\\", "/"), "/") {
		if seg == ".." {
			return true
		}
	}
	return false
}
