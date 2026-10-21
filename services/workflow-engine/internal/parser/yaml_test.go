package parser

import (
	"os"
	"testing"
)

func TestParseWorkflowYAML_Valid(t *testing.T) {
	yamlStr := `
name: nightly-ingest
version: 1.0.0
description: "P1 nightly ingest and ER pipeline"
schedule: "0 2 * * *"
steps:
  - id: step_ingest
    type: http
    url: "http://localhost:8001/ingest"
    method: "POST"
  - id: step_drift
    type: http
    depends_on: ["step_ingest"]
    url: "http://localhost:8001/drift"
    method: "POST"
  - id: step_approval
    type: human_approval
    depends_on: ["step_drift"]
    signal_name: "promote_approved"
`

	def, err := ParseWorkflowYAML([]byte(yamlStr))
	if err != nil {
		t.Fatalf("unexpected error parsing valid YAML: %v", err)
	}

	if def.Name != "nightly-ingest" {
		t.Errorf("expected name 'nightly-ingest', got '%s'", def.Name)
	}
	if def.Version != "1.0.0" {
		t.Errorf("expected version '1.0.0', got '%s'", def.Version)
	}
	if len(def.Steps) != 3 {
		t.Errorf("expected 3 steps, got %d", len(def.Steps))
	}
	if def.ContentHash == "" {
		t.Errorf("expected non-empty content hash")
	}
}

func TestParseWorkflowYAML_MissingFields(t *testing.T) {
	tests := []struct {
		name    string
		yamlStr string
	}{
		{"missing name", "version: 1.0.0\nsteps:\n  - id: a\n    type: wait"},
		{"missing version", "name: test\nsteps:\n  - id: a\n    type: wait"},
		{"missing steps", "name: test\nversion: 1.0.0\nsteps: []"},
		{"empty step id", "name: test\nversion: 1.0.0\nsteps:\n  - type: wait"},
		{"invalid step type", "name: test\nversion: 1.0.0\nsteps:\n  - id: a\n    type: unknown_type"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := ParseWorkflowYAML([]byte(tt.yamlStr))
			if err == nil {
				t.Errorf("expected validation error for %s, got nil", tt.name)
			}
		})
	}
}

func TestParseWorkflowYAML_CyclesAndMissingDeps(t *testing.T) {
	// Test cycle: a -> b -> a
	cycleYAML := `
name: cycle-test
version: 1.0.0
steps:
  - id: step_a
    type: wait
    depends_on: ["step_b"]
  - id: step_b
    type: wait
    depends_on: ["step_a"]
`
	_, err := ParseWorkflowYAML([]byte(cycleYAML))
	if err == nil {
		t.Errorf("expected error for circular dependency, got nil")
	}

	// Test missing dependency
	missingDepYAML := `
name: missing-dep
version: 1.0.0
steps:
  - id: step_a
    type: wait
    depends_on: ["non_existent_step"]
`
	_, err = ParseWorkflowYAML([]byte(missingDepYAML))
	if err == nil {
		t.Errorf("expected error for non-existent dependency, got nil")
	}

	// Test duplicate step ID
	dupYAML := `
name: dup-steps
version: 1.0.0
steps:
  - id: step_a
    type: wait
  - id: step_a
    type: http
`
	_, err = ParseWorkflowYAML([]byte(dupYAML))
	if err == nil {
		t.Errorf("expected error for duplicate step IDs, got nil")
	}
}

func TestParseShippedWorkflows(t *testing.T) {
	shipped := []string{
		"../../../../workflows/nightly-ingest.yaml",
		"../../../../workflows/retrain-promote.yaml",
		"../../../../workflows/weekly-insights.yaml",
		"../../../../workflows/nightly-evals.yaml",
		"../../../../workflows/daily-backup.yaml",
	}

	for _, path := range shipped {
		t.Run(path, func(t *testing.T) {
			data, err := os.ReadFile(path)
			if err != nil {
				t.Fatalf("failed to read workflow file %s: %v", path, err)
			}
			def, err := ParseWorkflowYAML(data)
			if err != nil {
				t.Fatalf("failed to parse shipped workflow %s: %v", path, err)
			}
			if def.Name == "" || def.Version == "" || len(def.Steps) == 0 {
				t.Fatalf("invalid parsed workflow definition for %s: %+v", path, def)
			}
		})
	}
}
