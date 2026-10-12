package main

import "testing"

func TestHostIsBlocked(t *testing.T) {
	blocked := []string{
		"127.0.0.1",
		"0.0.0.0",
		"localhost",
		"10.2.3.4",
		"192.168.1.1",
		"172.16.0.1",
		"169.254.169.254",
		"",
	}
	for _, host := range blocked {
		if !hostIsBlocked(host) {
			t.Errorf("hostIsBlocked(%q) = false, want true", host)
		}
	}
	if hostIsBlocked("8.8.8.8") {
		t.Error("hostIsBlocked(\"8.8.8.8\") = true, want false (public IP literal)")
	}
}

func TestValidateOutboundURL(t *testing.T) {
	rejected := map[string]string{
		"ftp://example.com/file.csv": "scheme",
		"http://127.0.0.1:8000/x":    "loopback",
		"http://10.0.0.1/x":          "private",
		"http:///path":               "host",
		"not-a-url":                  "scheme",
	}
	for raw, why := range rejected {
		if _, err := validateOutboundURL(raw); err == nil {
			t.Errorf("validateOutboundURL(%q) accepted, want rejection (%s)", raw, why)
		}
	}
	if _, err := validateOutboundURL("http://8.8.8.8/data.csv"); err != nil {
		t.Errorf("validateOutboundURL(public IP literal) failed: %v", err)
	}
}

func TestIsForbiddenLocalRef(t *testing.T) {
	refs := map[string]bool{
		"/etc/passwd":            true,
		"file:///etc/passwd":     true,
		"C:\\secrets\\token.txt": true,
		"../etc/passwd":          true,
		"":                       true,
		"cat:ds:res":             false,
		"ds:res":                 false,
		"datamesh://cat/ds/res":  false,
		"http://8.8.8.8/x":       false,
	}
	for ref, blocked := range refs {
		if got := isForbiddenLocalRef(ref); got != blocked {
			t.Errorf("isForbiddenLocalRef(%q) = %v, want %v", ref, got, blocked)
		}
	}
}

func TestIsRemoteOrTriad(t *testing.T) {
	remote := []string{"http://8.8.8.8/x.csv", "cat:ds:res", "ds:res", "datamesh://cat/ds/res"}
	for _, ref := range remote {
		if !isRemoteOrTriad(ref) {
			t.Errorf("isRemoteOrTriad(%q) = false, want true", ref)
		}
	}
	local := []string{"/etc/passwd", "file:///etc/passwd", "C:\\x\\y.csv", "../x", ".."}
	for _, ref := range local {
		if isRemoteOrTriad(ref) {
			t.Errorf("isRemoteOrTriad(%q) = true, want false", ref)
		}
	}
}
