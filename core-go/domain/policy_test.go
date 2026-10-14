package domain

import (
	"testing"
)

func TestEvaluateQueryAccess_AllowAll(t *testing.T) {
	decision := EvaluateQueryAccess("allow_all", UserIdentity{Role: "public"}, "SELECT * FROM 'censo'")
	if !decision.Allowed {
		t.Fatalf("expected allowed=true for allow_all, got false with reason %s", decision.Reason)
	}
}

func TestEvaluateQueryAccess_ZeroMicrodata_RejectsSelectStar(t *testing.T) {
	decision := EvaluateQueryAccess("zero_microdata", UserIdentity{Role: "public"}, "SELECT * FROM 'censo'")
	if decision.Allowed {
		t.Fatalf("expected allowed=false for SELECT * on zero_microdata")
	}
	if decision.Policy != PolicyZeroMicrodata {
		t.Fatalf("expected policy=zero_microdata, got %s", decision.Policy)
	}
}

func TestEvaluateQueryAccess_ZeroMicrodata_AllowsAggregations(t *testing.T) {
	decision := EvaluateQueryAccess("zero_microdata", UserIdentity{Role: "public"}, "SELECT departamento, COUNT(*) FROM 'censo' GROUP BY departamento")
	if !decision.Allowed {
		t.Fatalf("expected allowed=true for COUNT/GROUP BY query, got false with reason %s", decision.Reason)
	}
	if len(decision.GrantedPermissions) != 1 || decision.GrantedPermissions[0] != PermissionReadAggregate {
		t.Fatalf("expected granted=[read_aggregate], got %v", decision.GrantedPermissions)
	}
}

func TestEvaluateQueryAccess_ZeroMicrodata_AllowsPrivilegedAnalyst(t *testing.T) {
	decision := EvaluateQueryAccess("zero_microdata", UserIdentity{Role: "analyst", TrustTier: "human-reviewed"}, "SELECT * FROM 'censo'")
	if !decision.Allowed {
		t.Fatalf("expected allowed=true for authorized analyst, got false: %s", decision.Reason)
	}
}

func TestEvaluateQueryAccess_Deny(t *testing.T) {
	decisionPublic := EvaluateQueryAccess("deny", UserIdentity{Role: "public"}, "SELECT 1")
	if decisionPublic.Allowed {
		t.Fatalf("expected deny policy to reject public user")
	}

	decisionAdmin := EvaluateQueryAccess("deny", UserIdentity{Role: "admin"}, "SELECT 1")
	if !decisionAdmin.Allowed {
		t.Fatalf("expected deny policy to allow admin user")
	}
}

func TestComputeEffectivePolicy_GranularRules(t *testing.T) {
	policy := GranularPolicy{
		Name: "censo_governance",
		Rules: []PolicyRule{
			{
				ID:            "rule_privacy",
				Description:   "Hide personal IDs and hash email",
				AppliesTo:     []string{"public", "unverified"},
				HiddenColumns: []string{"ci", "nombres"},
				HashedColumns: []string{"email"},
				RowFilters:    []string{"gestion >= 2026"},
				AggregateOnly: true,
			},
			{
				ID:            "rule_admin_all",
				Description:   "Allow all to admin",
				AppliesTo:     []string{"admin"},
				AggregateOnly: false,
			},
		},
	}

	// 1. Public user
	publicIdentity := UserIdentity{ID: "did:github:publicuser", Role: "public", TrustTier: "unverified"}
	profile := ComputeEffectivePolicy(policy, publicIdentity)

	if !profile.Allowed {
		t.Fatalf("expected allowed=true")
	}
	if !profile.AggregateOnly {
		t.Fatalf("expected AggregateOnly=true for public user")
	}
	if len(profile.HiddenColumns) != 2 || profile.HiddenColumns[0] != "ci" {
		t.Fatalf("expected hidden columns [ci, nombres], got %v", profile.HiddenColumns)
	}
	if len(profile.HashedColumns) != 1 || profile.HashedColumns[0] != "email" {
		t.Fatalf("expected hashed columns [email], got %v", profile.HashedColumns)
	}
	if len(profile.RowFilters) != 1 || profile.RowFilters[0] != "gestion >= 2026" {
		t.Fatalf("expected row filters [gestion >= 2026], got %v", profile.RowFilters)
	}
	if profile.UserDID != "did:github:publicuser" {
		t.Fatalf("expected user DID to be preserved")
	}

	// 2. Admin user
	adminIdentity := UserIdentity{ID: "did:github:adminuser", Role: "admin"}
	adminProfile := ComputeEffectivePolicy(policy, adminIdentity)
	if !adminProfile.Allowed {
		t.Fatalf("expected admin to be allowed")
	}
	if adminProfile.AggregateOnly {
		t.Fatalf("expected admin not to be restricted by AggregateOnly")
	}
	if len(adminProfile.HiddenColumns) != 0 {
		t.Fatalf("expected admin to have 0 hidden columns")
	}
}

func TestEvaluateQueryWithProfile_HiddenColumns(t *testing.T) {
	profile := EffectivePolicyProfile{
		Allowed:       true,
		HiddenColumns: []string{"ci", "salario"},
		AggregateOnly: false,
	}

	// Query with hidden column should be rejected
	query := "SELECT ci, departamento FROM censo"
	decision := EvaluateQueryWithProfile(profile, query)
	if decision.Allowed {
		t.Fatalf("expected query referencing hidden column 'ci' to be rejected")
	}

	// Query without hidden column should be allowed
	validQuery := "SELECT departamento, COUNT(*) FROM censo GROUP BY departamento"
	validDecision := EvaluateQueryWithProfile(profile, validQuery)
	if !validDecision.Allowed {
		t.Fatalf("expected query without hidden column to be allowed, got: %s", validDecision.Reason)
	}
}

