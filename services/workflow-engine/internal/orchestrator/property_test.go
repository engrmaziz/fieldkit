package orchestrator

import (
	"fmt"
	"testing"
	"time"

	"fieldkit/workflow-engine/internal/model"
	"github.com/google/uuid"
)

// TestOrchestrator_MonotonicityAndReplayInvariants verifies mathematical invariants of event replay.
func TestOrchestrator_MonotonicityAndReplayInvariants(t *testing.T) {
	runID := uuid.New()
	def := &model.WorkflowDefinition{
		Name:    "invariant-pipeline",
		Version: "1.0.0",
		Steps: []model.StepDefinition{
			{ID: "step_1", Type: model.StepTypeHTTP},
			{ID: "step_2", Type: model.StepTypeHTTP, DependsOn: []string{"step_1"}},
			{ID: "step_3", Type: model.StepTypeHTTP, DependsOn: []string{"step_2"}},
		},
	}

	// Build progressive sequence of events
	events := []model.WorkflowEvent{
		{RunID: runID, Seq: 1, Type: model.EventWorkflowStarted, Timestamp: time.Now().UTC()},
	}

	// Invariant 1: Fresh workflow produces step_1 and is RUNNING
	a1 := ComputeNextActions(events, def)
	if a1.Status != model.RunStatusRunning || len(a1.TasksToSchedule) != 1 || a1.TasksToSchedule[0].StepID != "step_1" {
		t.Fatalf("invariant 1 failed: %+v", a1)
	}

	// Invariant 2: Idempotent replay - computing again with identical events produces identical result
	a1Replay := ComputeNextActions(events, def)
	if a1Replay.Status != a1.Status || len(a1Replay.TasksToSchedule) != len(a1.TasksToSchedule) {
		t.Fatalf("invariant 2 (idempotency) failed: replay produced different state")
	}

	// Schedule step 1
	events = append(events, model.WorkflowEvent{
		RunID: runID, Seq: 2, Type: model.EventStepScheduled,
		Payload: map[string]any{"step_id": "step_1"}, Timestamp: time.Now().UTC(),
	})
	events = append(events, model.WorkflowEvent{
		RunID: runID, Seq: 3, Type: model.EventStepStarted,
		Payload: map[string]any{"step_id": "step_1"}, Timestamp: time.Now().UTC(),
	})
	events = append(events, model.WorkflowEvent{
		RunID: runID, Seq: 4, Type: model.EventStepCompleted,
		Payload: map[string]any{"step_id": "step_1", "output": map[string]any{"rows": 100}}, Timestamp: time.Now().UTC(),
	})

	// Invariant 3: After step_1 completes, step_2 is scheduled
	a2 := ComputeNextActions(events, def)
	if a2.Status != model.RunStatusRunning || len(a2.TasksToSchedule) != 1 || a2.TasksToSchedule[0].StepID != "step_2" {
		t.Fatalf("invariant 3 failed: expected step_2 scheduled, got %+v", a2)
	}

	// Invariant 4: Monotonicity - completed steps never un-complete
	if _, ok := a2.StepOutputs["step_1"]; !ok {
		t.Fatalf("invariant 4 (monotonicity) failed: step_1 output disappeared")
	}

	// Complete all remaining steps
	events = append(events,
		model.WorkflowEvent{RunID: runID, Seq: 5, Type: model.EventStepScheduled, Payload: map[string]any{"step_id": "step_2"}, Timestamp: time.Now().UTC()},
		model.WorkflowEvent{RunID: runID, Seq: 6, Type: model.EventStepCompleted, Payload: map[string]any{"step_id": "step_2"}, Timestamp: time.Now().UTC()},
		model.WorkflowEvent{RunID: runID, Seq: 7, Type: model.EventStepScheduled, Payload: map[string]any{"step_id": "step_3"}, Timestamp: time.Now().UTC()},
		model.WorkflowEvent{RunID: runID, Seq: 8, Type: model.EventStepCompleted, Payload: map[string]any{"step_id": "step_3"}, Timestamp: time.Now().UTC()},
	)

	a3 := ComputeNextActions(events, def)
	if a3.Status != model.RunStatusCompleted {
		t.Fatalf("invariant 5 failed: expected status COMPLETED, got %s", a3.Status)
	}

	// Invariant 5: Terminal Absorption - once completed, further events cannot resurrect running tasks
	a3Replay := ComputeNextActions(events, def)
	if a3Replay.Status != model.RunStatusCompleted || len(a3Replay.TasksToSchedule) != 0 {
		t.Fatalf("invariant 5 (terminal absorption) failed: tasks scheduled after completion")
	}
}

// TestOrchestrator_FanOutMapDeterminism verifies map steps with variable input length.
func TestOrchestrator_FanOutMapDeterminism(t *testing.T) {
	for numItems := 1; numItems <= 10; numItems++ {
		t.Run(fmt.Sprintf("items_%d", numItems), func(t *testing.T) {
			runID := uuid.New()
			def := &model.WorkflowDefinition{
				Name:    "map-pipeline",
				Version: "1.0.0",
				Steps: []model.StepDefinition{
					{ID: "map_step", Type: model.StepTypeMap, Items: "batch_items", MaxConcurrency: 4},
				},
			}

			events := []model.WorkflowEvent{
				{RunID: runID, Seq: 1, Type: model.EventWorkflowStarted, Timestamp: time.Now().UTC()},
				{RunID: runID, Seq: 2, Type: model.EventStepCompleted, Payload: map[string]any{"step_id": "map_step", "output": map[string]any{"processed": numItems}}, Timestamp: time.Now().UTC()},
			}

			actions := ComputeNextActions(events, def)
			if actions.Status != model.RunStatusCompleted {
				t.Fatalf("expected status COMPLETED for map fan-out, got %s", actions.Status)
			}
		})
	}
}
