package orchestrator

import (
	"testing"
	"time"

	"fieldkit/workflow-engine/internal/model"
	"github.com/google/uuid"
)

func TestOrchestrator_InitialScheduling(t *testing.T) {
	runID := uuid.New()
	def := &model.WorkflowDefinition{
		Name:    "test-pipeline",
		Version: "1.0.0",
		Steps: []model.StepDefinition{
			{ID: "step_1", Type: model.StepTypeHTTP},
			{ID: "step_2", Type: model.StepTypeHTTP, DependsOn: []string{"step_1"}},
		},
	}

	events := []model.WorkflowEvent{
		{
			RunID:     runID,
			Seq:       1,
			Type:      model.EventWorkflowStarted,
			Timestamp: time.Now().UTC(),
		},
	}

	actions := ComputeNextActions(events, def)

	if actions.Status != model.RunStatusRunning {
		t.Fatalf("expected status RUNNING, got %s", actions.Status)
	}
	if len(actions.TasksToSchedule) != 1 {
		t.Fatalf("expected 1 task to schedule, got %d", len(actions.TasksToSchedule))
	}
	if actions.TasksToSchedule[0].StepID != "step_1" {
		t.Errorf("expected step_1 to be scheduled, got %s", actions.TasksToSchedule[0].StepID)
	}
}

func TestOrchestrator_SequentialProgressionAndCompletion(t *testing.T) {
	runID := uuid.New()
	def := &model.WorkflowDefinition{
		Name:    "test-pipeline",
		Version: "1.0.0",
		Steps: []model.StepDefinition{
			{ID: "step_1", Type: model.StepTypeHTTP},
			{ID: "step_2", Type: model.StepTypeHTTP, DependsOn: []string{"step_1"}},
		},
	}

	// Step 1 completed
	events := []model.WorkflowEvent{
		{RunID: runID, Seq: 1, Type: model.EventWorkflowStarted, Timestamp: time.Now().UTC()},
		{RunID: runID, Seq: 2, Type: model.EventStepScheduled, Payload: map[string]any{"step_id": "step_1"}, Timestamp: time.Now().UTC()},
		{RunID: runID, Seq: 3, Type: model.EventStepCompleted, Payload: map[string]any{"step_id": "step_1", "output": map[string]any{"count": 42}}, Timestamp: time.Now().UTC()},
	}

	actions := ComputeNextActions(events, def)

	if actions.Status != model.RunStatusRunning {
		t.Fatalf("expected status RUNNING, got %s", actions.Status)
	}
	if len(actions.TasksToSchedule) != 1 {
		t.Fatalf("expected 1 task to schedule (step_2), got %d", len(actions.TasksToSchedule))
	}
	if actions.TasksToSchedule[0].StepID != "step_2" {
		t.Errorf("expected step_2 scheduled, got %s", actions.TasksToSchedule[0].StepID)
	}

	// Now step 2 completes -> entire workflow should be COMPLETED
	events = append(events,
		model.WorkflowEvent{RunID: runID, Seq: 4, Type: model.EventStepScheduled, Payload: map[string]any{"step_id": "step_2"}, Timestamp: time.Now().UTC()},
		model.WorkflowEvent{RunID: runID, Seq: 5, Type: model.EventStepCompleted, Payload: map[string]any{"step_id": "step_2", "output": map[string]any{"status": "ok"}}, Timestamp: time.Now().UTC()},
	)

	actionsComplete := ComputeNextActions(events, def)

	if actionsComplete.Status != model.RunStatusCompleted {
		t.Fatalf("expected status COMPLETED, got %s", actionsComplete.Status)
	}
	if len(actionsComplete.TasksToSchedule) != 0 {
		t.Fatalf("expected 0 tasks to schedule on completion, got %d", len(actionsComplete.TasksToSchedule))
	}
}

func TestOrchestrator_HumanApprovalGate(t *testing.T) {
	runID := uuid.New()
	def := &model.WorkflowDefinition{
		Name:    "approval-pipeline",
		Version: "1.0.0",
		Steps: []model.StepDefinition{
			{ID: "step_train", Type: model.StepTypeHTTP},
			{ID: "gate_approval", Type: model.StepTypeHumanApproval, DependsOn: []string{"step_train"}, SignalName: "promote_approved"},
			{ID: "step_promote", Type: model.StepTypeHTTP, DependsOn: []string{"gate_approval"}},
		},
	}

	// Train completes, approval gate reached
	events := []model.WorkflowEvent{
		{RunID: runID, Seq: 1, Type: model.EventWorkflowStarted, Timestamp: time.Now().UTC()},
		{RunID: runID, Seq: 2, Type: model.EventStepCompleted, Payload: map[string]any{"step_id": "step_train"}, Timestamp: time.Now().UTC()},
	}

	actions := ComputeNextActions(events, def)

	if actions.Status != model.RunStatusSuspended {
		t.Fatalf("expected status SUSPENDED waiting for approval, got %s", actions.Status)
	}
	if actions.WaitingForSignal != "promote_approved" {
		t.Errorf("expected WaitingForSignal 'promote_approved', got '%s'", actions.WaitingForSignal)
	}

	// Operator grants approval signal
	events = append(events,
		model.WorkflowEvent{
			RunID:     runID,
			Seq:       3,
			Type:      model.EventSignalReceived,
			Payload:   map[string]any{"signal_name": "promote_approved", "approved_by": "mehmet@halden.de"},
			Timestamp: time.Now().UTC(),
		},
	)

	actionsApproved := ComputeNextActions(events, def)

	if actionsApproved.Status != model.RunStatusRunning {
		t.Fatalf("expected status RUNNING after approval signal, got %s", actionsApproved.Status)
	}
	if len(actionsApproved.TasksToSchedule) != 1 || actionsApproved.TasksToSchedule[0].StepID != "step_promote" {
		t.Fatalf("expected step_promote scheduled after approval, got %v", actionsApproved.TasksToSchedule)
	}
}

func TestOrchestrator_SagaCompensationOnFailure(t *testing.T) {
	runID := uuid.New()
	def := &model.WorkflowDefinition{
		Name:    "saga-pipeline",
		Version: "1.0.0",
		Steps: []model.StepDefinition{
			{ID: "step_reserve", Type: model.StepTypeHTTP, CompensateWith: "comp_cancel_reservation"},
			{ID: "step_charge", Type: model.StepTypeHTTP, DependsOn: []string{"step_reserve"}},
		},
		Compensations: []model.StepDefinition{
			{ID: "comp_cancel_reservation", Type: model.StepTypeHTTP, URL: "http://localhost:8001/cancel"},
		},
	}

	// Step reserve completed, but step charge failed
	events := []model.WorkflowEvent{
		{RunID: runID, Seq: 1, Type: model.EventWorkflowStarted, Timestamp: time.Now().UTC()},
		{RunID: runID, Seq: 2, Type: model.EventStepCompleted, Payload: map[string]any{"step_id": "step_reserve"}, Timestamp: time.Now().UTC()},
		{RunID: runID, Seq: 3, Type: model.EventStepFailed, Payload: map[string]any{"step_id": "step_charge", "error": "charge declined", "terminal": true}, Timestamp: time.Now().UTC()},
	}

	actions := ComputeNextActions(events, def)

	if actions.Status != model.RunStatusFailed {
		t.Fatalf("expected status FAILED, got %s", actions.Status)
	}
	if len(actions.CompensationsToSchedule) != 1 {
		t.Fatalf("expected 1 compensation task, got %d", len(actions.CompensationsToSchedule))
	}
	if actions.CompensationsToSchedule[0].StepID != "comp_cancel_reservation" {
		t.Errorf("expected comp_cancel_reservation scheduled, got %s", actions.CompensationsToSchedule[0].StepID)
	}
}
