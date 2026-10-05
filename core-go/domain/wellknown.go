package domain

// WellKnownDiscovery defines the standardized catalog discovery document served at /.well-known/datamesh.json
type WellKnownDiscovery struct {
	SchemaVersion string             `json:"schema_version"`
	Catalog       CatalogMetadata    `json:"catalog"`
	Auth          AuthConfiguration  `json:"auth"`
	Capabilities  map[string]bool    `json:"capabilities"`
}

// CatalogMetadata holds high-level descriptive information about a catalog.
type CatalogMetadata struct {
	Name        string `json:"name"`
	Title       string `json:"title"`
	Description string `json:"description,omitempty"`
	Type        string `json:"type"` // "ckan", "okf", "dcat", "git"
	CatalogURL  string `json:"catalog_url"`
	APIEndpoint string `json:"api_endpoint,omitempty"`
	Version     string `json:"version,omitempty"`
	Maintainer  string `json:"maintainer,omitempty"`
}

// AuthConfiguration specifies authentication mechanisms supported or required by the catalog.
type AuthConfiguration struct {
	Type     string         `json:"type"` // "none", "api_key", "bearer", "oauth2", "keycloak"
	Required bool           `json:"required"`
	Keycloak *KeycloakAuth  `json:"keycloak,omitempty"`
	OAuth2   *OAuth2Auth    `json:"oauth2,omitempty"`
	APIKey   *APIKeyAuth    `json:"api_key,omitempty"`
}

// KeycloakAuth details OpenID Connect endpoints provided by Keycloak.
type KeycloakAuth struct {
	RealmURL              string   `json:"realm_url"`
	TokenEndpoint         string   `json:"token_endpoint"`
	AuthorizationEndpoint string   `json:"authorization_endpoint,omitempty"`
	ClientID              string   `json:"client_id,omitempty"`
	ScopesSupported       []string `json:"scopes_supported,omitempty"`
}

// OAuth2Auth details standard OAuth 2.0 client credentials token endpoints.
type OAuth2Auth struct {
	TokenEndpoint   string   `json:"token_endpoint"`
	ClientID        string   `json:"client_id,omitempty"`
	ScopesSupported []string `json:"scopes_supported,omitempty"`
}

// APIKeyAuth details token or key header name requirements.
type APIKeyAuth struct {
	HeaderName string `json:"header_name,omitempty"` // e.g. "X-CKAN-API-Key" or "Authorization"
	Prefix     string `json:"prefix,omitempty"`      // e.g. "Bearer" or empty
}
