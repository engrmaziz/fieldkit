package parser

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"time"

	"fieldkit/workflow-engine/internal/model"
	"gopkg.in/yaml.v3"
)

// ParseWorkflowYAML parses, validates, and computes the content hash of a workflow definition YAML.
func ParseWorkflowYAML(data []byte) (*model.WorkflowDefinition, error) {
	var def model.WorkflowDefinition
	if err := yaml.Unmarshal(data, &def); err != nil {
		return nil, fmt.Errorf("failed to unmarshal workflow yaml: %w", err)
	}

	if def.Name == "" {
		return nil, fmt.Errorf("workflow name is required")
	}
	if def.Version == "" {
		return nil, fmt.Errorf("workflow version is required")
	}
	if len(def.Steps) == 0 {
		return nil, fmt.Errorf("workflow must contain at least one step")
	}

	// Validate step IDs, types, and dependencies
	stepIDs := make(map[string]bool)
	for _, step := range def.Steps {
		if step.ID == "" {
			return nil, fmt.Errorf("step ID cannot be empty")
		}
		if stepIDs[step.ID] {
			return nil, fmt.Errorf("duplicate step ID detected: '%s'", step.ID)
		}
		stepIDs[step.ID] = true

		switch step.Type {
		case model.StepTypeHTTP, model.StepTypeWait, model.StepTypeBranch, model.StepTypeMap, model.StepTypeHumanApproval:
			// valid
		default:
			return nil, fmt.Errorf("invalid step type '%s' on step '%s'", step.Type, step.ID)
		}
	}

	// Validate dependencies exist
	for _, step := range def.Steps {
		for _, dep := range step.DependsOn {
			if !stepIDs[dep] {
				return nil, fmt.Errorf("step '%s' depends on unknown step '%s'", step.ID, dep)
			}
			if dep == step.ID {
				return nil, fmt.Errorf("step '%s' cannot depend on itself", step.ID)
			}
		}
	}

	// Cycle detection using Kahn's algorithm (Topological sort)
	inDegree := make(map[string]int)
	graph := make(map[string][]string) // dep -> dependents

	for _, step := range def.Steps {
		inDegree[step.ID] = len(step.DependsOn)
		for _, dep := range step.DependsOn {
			graph[dep] = append(graph[dep], step.ID)
		}
	}

	var queue []string
	for id, deg := range inDegree {
		if deg == 0 {
			queue = append(queue, id)
		}
	}

	visitedCount := 0
	for len(queue) > 0 {
		curr := queue[0]
		queue = queue[1:]
		visitedCount++

		for _, dependent := range graph[curr] {
			inDegree[dependent]--
			if inDegree[dependent] == 0 {
				queue = append(queue, dependent)
			}
		}
	}

	if visitedCount != len(def.Steps) {
		return nil, fmt.Errorf("circular dependency detected in workflow steps")
	}

	// Compute SHA-256 fingerprint
	h := sha256.New()
	h.Write(data)
	def.ContentHash = hex.EncodeToString(h.Sum(nil))
	def.YAMLContent = string(data)
	if def.CreatedAt.IsZero() {
		def.CreatedAt = time.Now().UTC()
	}

	return &def, nil
}
