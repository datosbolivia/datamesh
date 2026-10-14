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
