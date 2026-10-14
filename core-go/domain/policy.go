package domain

import (
	"encoding/json"
	"errors"
	"fmt"
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

// PolicyRule defines a fine-grained access constraint on a dataset, its rows, or specific columns.
type PolicyRule struct {
	ID            string   `json:"id" yaml:"id"`
	Description   string   `json:"description,omitempty" yaml:"description,omitempty"`
	AppliesTo     []string `json:"applies_to,omitempty" yaml:"applies_to,omitempty"` // Roles or trust tiers affected (e.g. ["public", "unverified"])
	AggregateOnly bool     `json:"aggregate_only,omitempty" yaml:"aggregate_only,omitempty"`
	HiddenColumns []string `json:"hidden_columns,omitempty" yaml:"hidden_columns,omitempty"`
	HashedColumns []string `json:"hashed_columns,omitempty" yaml:"hashed_columns,omitempty"`
	RowFilters    []string `json:"row_filters,omitempty" yaml:"row_filters,omitempty"` // e.g. ["año >= 2026", "fecha >= '2026-01-01'"]
	DenyAccess    bool     `json:"deny_access,omitempty" yaml:"deny_access,omitempty"`
}

// GranularPolicy represents an extensible policy comprising multiple rules.
type GranularPolicy struct {
	Name  string       `json:"name" yaml:"name"`
	Rules []PolicyRule `json:"rules" yaml:"rules"`
}

// EffectivePolicyProfile is the personalized subset of rules and constraints that apply to a caller.
type EffectivePolicyProfile struct {
	DatasetID     string   `json:"dataset_id,omitempty"`
	UserDID       string   `json:"user_did,omitempty"`
	Role          string   `json:"role"`
	TrustTier     string   `json:"trust_tier"`
	Allowed       bool     `json:"allowed"`
	Reason        string   `json:"reason,omitempty"`
	AggregateOnly bool     `json:"aggregate_only"`
	HiddenColumns []string `json:"hidden_columns"`
	HashedColumns []string `json:"hashed_columns"`
	RowFilters    []string `json:"row_filters"`
	ActiveRuleIDs []string `json:"active_rule_ids"`
}

// ParseGranularPolicy parses a JSON string or resolves standard policy shorthand keywords ("allow_all", "zero_microdata", "deny").
func ParseGranularPolicy(policyStr string) (GranularPolicy, error) {
	trimmed := strings.TrimSpace(policyStr)
	if strings.HasPrefix(trimmed, "{") {
		var gp GranularPolicy
		if err := json.Unmarshal([]byte(trimmed), &gp); err == nil && (len(gp.Rules) > 0 || gp.Name != "") {
			return gp, nil
		}
	}

	norm := strings.ToLower(trimmed)
	switch norm {
	case "zero_microdata":
		return GranularPolicy{
			Name: "zero_microdata",
			Rules: []PolicyRule{
				{
					ID:            "rule_zero_microdata",
					Description:   "Zero-microdata protection: raw row queries prohibited without privileged credentials",
					AppliesTo:     []string{"public", "unverified"},
					AggregateOnly: true,
				},
			},
		}, nil
	case "deny":
		return GranularPolicy{
			Name: "deny",
			Rules: []PolicyRule{
				{
					ID:          "rule_deny_access",
					Description: "General dataset access restriction",
					AppliesTo:   []string{"public", "unverified", "analyst"},
					DenyAccess:  true,
				},
			},
		}, nil
	case "", "allow_all":
		return GranularPolicy{
			Name:  "allow_all",
			Rules: []PolicyRule{},
		}, nil
	default:
		return GranularPolicy{
			Name:  norm,
			Rules: []PolicyRule{},
		}, nil
	}
}

// ComputeEffectivePolicy evaluates which rules in a policy apply to the specific UserIdentity.
func ComputeEffectivePolicy(policy GranularPolicy, identity UserIdentity) EffectivePolicyProfile {
	profile := EffectivePolicyProfile{
		UserDID:       identity.ID,
		Role:          identity.Role,
		TrustTier:     identity.TrustTier,
		Allowed:       true,
		HiddenColumns: make([]string, 0),
		HashedColumns: make([]string, 0),
		RowFilters:    make([]string, 0),
		ActiveRuleIDs: make([]string, 0),
	}

	normRole := strings.ToLower(strings.TrimSpace(identity.Role))
	if normRole == "" {
		normRole = "public"
	}
	normTrust := strings.ToLower(strings.TrimSpace(identity.TrustTier))
	if normTrust == "" {
		normTrust = "unverified"
	}

	isAdmin := normRole == "admin"

	for _, rule := range policy.Rules {
		applies := false
		if len(rule.AppliesTo) == 0 {
			applies = true
		} else {
			for _, target := range rule.AppliesTo {
				nt := strings.ToLower(strings.TrimSpace(target))
				if nt == "all" || nt == "*" || nt == normRole || nt == normTrust {
					applies = true
					break
				}
			}
		}

		if !applies {
			continue
		}

		profile.ActiveRuleIDs = append(profile.ActiveRuleIDs, rule.ID)

		if rule.DenyAccess {
			if !isAdmin {
				profile.Allowed = false
				profile.Reason = fmt.Sprintf("Access denied by rule '%s': %s", rule.ID, rule.Description)
				return profile
			}
		}

		if rule.AggregateOnly && !isAdmin {
			profile.AggregateOnly = true
		}

		if !isAdmin {
			profile.HiddenColumns = appendUniqueStrings(profile.HiddenColumns, rule.HiddenColumns...)
			profile.HashedColumns = appendUniqueStrings(profile.HashedColumns, rule.HashedColumns...)
			profile.RowFilters = appendUniqueStrings(profile.RowFilters, rule.RowFilters...)
		}
	}

	return profile
}

func appendUniqueStrings(existing []string, items ...string) []string {
	seen := make(map[string]bool, len(existing))
	for _, s := range existing {
		seen[s] = true
	}
	for _, item := range items {
		clean := strings.TrimSpace(item)
		if clean != "" && !seen[clean] {
			existing = append(existing, clean)
			seen[clean] = true
		}
	}
	return existing
}

// EvaluateQueryWithProfile validates whether an ANSI SQL query complies with an EffectivePolicyProfile.
func EvaluateQueryWithProfile(profile EffectivePolicyProfile, sqlQuery string) PolicyDecision {
	if !profile.Allowed {
		return PolicyDecision{
			Allowed: false,
			Policy:  PolicyDeny,
			Reason:  profile.Reason,
		}
	}

	// 1. Check for access to hidden/restricted columns
	for _, col := range profile.HiddenColumns {
		if col == "" {
			continue
		}
		pattern := regexp.MustCompile(`(?i)\b` + regexp.QuoteMeta(col) + `\b`)
		if pattern.MatchString(sqlQuery) {
			return PolicyDecision{
				Allowed: false,
				Policy:  PolicyDeny,
				Reason:  fmt.Sprintf("Query rejected: Column '%s' is hidden/restricted for your identity tier.", col),
			}
		}
	}

	// 2. Check aggregate only constraint
	if profile.AggregateOnly {
		isAggOnly, selectsRaw := ClassifyQueryIntent(sqlQuery)
		if !isAggOnly || selectsRaw {
			return PolicyDecision{
				Allowed:           false,
				Policy:            PolicyZeroMicrodata,
				Reason:            "Dataset access restricted under 'zero_microdata' policy. Raw individual row access (e.g. SELECT *) is prohibited. Query must contain statistical aggregations (COUNT, SUM, AVG, MIN, MAX, GROUP BY) or provide authorized digital signature/credentials.",
				RequiresSignature: true,
			}
		}
	}

	return PolicyDecision{
		Allowed:            true,
		Policy:             PolicyAllowAll,
		GrantedPermissions: []Permission{PermissionReadAggregate, PermissionReadRaw},
	}
}

// EvaluateQueryAccess performs unified policy arbitration across Go Core, Python, and Servers.
func EvaluateQueryAccess(policy string, identity UserIdentity, sqlQuery string) PolicyDecision {
	trimmedPolicy := strings.TrimSpace(policy)
	if strings.HasPrefix(trimmedPolicy, "{") {
		var gp GranularPolicy
		if err := json.Unmarshal([]byte(trimmedPolicy), &gp); err == nil && len(gp.Rules) > 0 {
			profile := ComputeEffectivePolicy(gp, identity)
			return EvaluateQueryWithProfile(profile, sqlQuery)
		}
	}

	normPolicy := PolicyType(strings.ToLower(trimmedPolicy))
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
