package domain

import (
	"errors"
	"regexp"
	"strings"
)

// PolicyType represents static access governance policies on datasets or resources.
type PolicyType string

const (
	PolicyAllowAll      PolicyType = "allow_all"
	PolicyZeroMicrodata PolicyType = "zero_microdata"
	PolicyDeny          PolicyType = "deny"
)

// Permission represents specific data access capabilities.
type Permission string

const (
	PermissionReadRaw       Permission = "read_raw"
	PermissionReadAggregate Permission = "read_aggregate"
	PermissionExport        Permission = "export"
	PermissionAdmin         Permission = "admin"
)

// UserIdentity models an authenticated or public caller with cryptographic credentials.
type UserIdentity struct {
	ID        string `json:"id"`
	Role      string `json:"role"`       // public, analyst, auditor, admin
	PublicKey string `json:"public_key"` // ed25519 hex or ssh-ed25519 public key
	Signature string `json:"signature"`  // cryptographic challenge signature
	TrustTier string `json:"trust_tier"` // unverified, machine-confirmed, human-reviewed, official
}

// PolicyDecision encapsulates the access enforcement outcome.
type PolicyDecision struct {
	Allowed            bool         `json:"allowed"`
	Policy             PolicyType   `json:"policy"`
	Reason             string       `json:"reason,omitempty"`
	GrantedPermissions []Permission `json:"granted_permissions"`
	RequiresSignature  bool         `json:"requires_signature"`
}

var (
	aggregateFuncRegex = regexp.MustCompile(`(?i)\b(COUNT|SUM|AVG|MIN|MAX|MEDIAN|STDDEV|VARIANCE|APPROX_COUNT_DISTINCT)\s*\(`)
	groupByRegex       = regexp.MustCompile(`(?i)\bGROUP\s+BY\b`)
	selectStarRegex    = regexp.MustCompile(`(?i)\bSELECT\s+(?:DISTINCT\s+)?\*\s+FROM\b`)
)

// ClassifyQueryIntent inspects an ANSI SQL statement to determine if it is an aggregate query.
func ClassifyQueryIntent(sqlQuery string) (isAggregateOnly bool, selectsRawRows bool) {
	cleanSQL := strings.TrimSpace(sqlQuery)
	if cleanSQL == "" {
		return false, true
	}

	hasAggFunc := aggregateFuncRegex.MatchString(cleanSQL)
	hasGroupBy := groupByRegex.MatchString(cleanSQL)
	hasSelectStar := selectStarRegex.MatchString(cleanSQL)

	if hasSelectStar {
		return false, true
	}

	if hasAggFunc && !hasSelectStar {
		return true, false
	}

	if hasGroupBy && !hasSelectStar {
		return true, false
	}

	return false, true
}

// EvaluateQueryAccess performs unified policy arbitration across Go Core, Python, and Servers.
func EvaluateQueryAccess(policy string, identity UserIdentity, sqlQuery string) PolicyDecision {
	normPolicy := PolicyType(strings.ToLower(strings.TrimSpace(policy)))
	if normPolicy == "" {
		normPolicy = PolicyAllowAll
	}

	switch normPolicy {
	case PolicyAllowAll:
		return PolicyDecision{
			Allowed:            true,
			Policy:             PolicyAllowAll,
			GrantedPermissions: []Permission{PermissionReadRaw, PermissionReadAggregate, PermissionExport},
		}

	case PolicyDeny:
		if strings.EqualFold(identity.Role, "admin") {
			return PolicyDecision{
				Allowed:            true,
				Policy:             PolicyDeny,
				GrantedPermissions: []Permission{PermissionAdmin, PermissionReadRaw, PermissionReadAggregate},
			}
		}
		return PolicyDecision{
			Allowed:            false,
			Policy:             PolicyDeny,
			Reason:             "Access explicitly denied by 'deny' policy. Requires administrative role.",
			GrantedPermissions: []Permission{},
			RequiresSignature:  true,
		}

	case PolicyZeroMicrodata:
		// Privileged trust tiers or authorized analyst/admin roles obtain full raw access
		if strings.EqualFold(identity.Role, "admin") ||
			strings.EqualFold(identity.Role, "analyst") ||
			strings.EqualFold(identity.TrustTier, "official") ||
			strings.EqualFold(identity.TrustTier, "human-reviewed") {
			return PolicyDecision{
				Allowed:            true,
				Policy:             PolicyZeroMicrodata,
				GrantedPermissions: []Permission{PermissionReadRaw, PermissionReadAggregate},
			}
		}

		// Public or unverified callers MUST use aggregate queries
		isAggOnly, selectsRaw := ClassifyQueryIntent(sqlQuery)
		if isAggOnly && !selectsRaw {
			return PolicyDecision{
				Allowed:            true,
				Policy:             PolicyZeroMicrodata,
				GrantedPermissions: []Permission{PermissionReadAggregate},
			}
		}

		return PolicyDecision{
			Allowed:            false,
			Policy:             PolicyZeroMicrodata,
			Reason:             "Dataset access restricted under 'zero_microdata' policy. Raw individual row access (e.g. SELECT *) is prohibited for unverified identities. Query must contain statistical aggregations (COUNT, SUM, AVG, MIN, MAX, GROUP BY) or provide authorized digital signature/credentials.",
			GrantedPermissions: []Permission{},
			RequiresSignature:  true,
		}

	default:
		return PolicyDecision{
			Allowed:            false,
			Policy:             normPolicy,
			Reason:             "Unknown or unsupported policy: " + string(normPolicy),
			GrantedPermissions: []Permission{},
		}
	}
}

// ErrPolicyViolation represents access rejection due to policy invariants.
var ErrPolicyViolation = errors.New("policy violation: unauthorized query on protected resource")
