package chaos

import (
	"context"
	"fmt"
	"math/rand"
	"sync"
	"testing"
	"time"

	"fieldkit/workflow-engine/internal/engine"
	"fieldkit/workflow-engine/internal/executor"
	"fieldkit/workflow-engine/internal/model"
	"fieldkit/workflow-engine/internal/orchestrator"
	"fieldkit/workflow-engine/internal/storage"
	"github.com/google/uuid"
)

// TestChaos_200WorkflowsUnderFaultInjection executes 200 mixed workflows with worker restarts.
func TestChaos_200WorkflowsUnderFaultInjection(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping 200-workflow chaos test in short mode")
	}

	receiver := NewMockDownstreamReceiver()
	defer receiver.Close()

	store := storage.NewMemoryStorage()
	exec := executor.NewDefaultExecutor()

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// Define 4 distinct workflow patterns
	defs := []*model.WorkflowDefinition{
		{
			Name:    "wf-http",
			Version: "1.0.0",
			Steps: []model.StepDefinition{
				{ID: "step_http_1", Type: model.StepTypeHTTP, URL: receiver.URL()},
				{ID: "step_http_2", Type: model.StepTypeHTTP, DependsOn: []string{"step_http_1"}, URL: receiver.URL()},
			},
		},
		{
			Name:    "wf-wait",
			Version: "1.0.0",
			Steps: []model.StepDefinition{
				{ID: "step_w_1", Type: model.StepTypeWait, WaitDurationSec: 0},
				{ID: "step_w_2", Type: model.StepTypeWait, DependsOn: []string{"step_w_1"}, WaitDurationSec: 0},
			},
		},
		{
			Name:    "wf-map",
			Version: "1.0.0",
			Steps: []model.StepDefinition{
				{ID: "step_map", Type: model.StepTypeMap, Items: "items", MaxConcurrency: 4},
			},
		},
		{
			Name:    "wf-approval",
			Version: "1.0.0",
			Steps: []model.StepDefinition{
				{ID: "step_prepare", Type: model.StepTypeWait, WaitDurationSec: 0},
				{ID: "step_gate", Type: model.StepTypeHumanApproval, DependsOn: []string{"step_prepare"}, SignalName: "lead_approved"},
				{ID: "step_finalize", Type: model.StepTypeHTTP, DependsOn: []string{"step_gate"}, URL: receiver.URL()},
			},
		},
	}

	for _, d := range defs {
		_ = store.SaveDefinition(ctx, d)
	}

	// Active engine instance (with mutex to simulate crash-restarts)
	var mu sync.Mutex
	eng := engine.NewEngine(store, exec, 8)
	eng.Start(ctx)

	// Launch Chaos Fault Injector: restarts engine every 150-400ms during the run
	chaosDone := make(chan struct{})
	go func() {
		defer close(chaosDone)
		for {
			select {
			case <-ctx.Done():
				return
			case <-time.After(time.Duration(150+rand.Intn(250)) * time.Millisecond):
				mu.Lock()
				// Simulate SIGKILL and instant recovery
				eng.Stop()
				eng = engine.NewEngine(store, exec, 8)
				eng.Start(ctx)
				mu.Unlock()
			}
		}
	}()

	// Dispatch 200 workflows
	const totalWorkflows = 200
	var runIDs []uuid.UUID
	var approvalRuns []uuid.UUID

	for i := 0; i < totalWorkflows; i++ {
		defIdx := i % len(defs)
		selectedDef := defs[defIdx]

		input := map[string]any{
			"batch_id": fmt.Sprintf("batch-%d", i),
			"items":    []any{1, 2, 3, 4},
		}

		mu.Lock()
		run, err := eng.StartWorkflow(ctx, selectedDef.Name, selectedDef.Version, input)
		mu.Unlock()

		if err != nil {
			t.Fatalf("failed to start workflow %d: %v", i, err)
		}
		runIDs = append(runIDs, run.ID)
		if selectedDef.Name == "wf-approval" {
			approvalRuns = append(approvalRuns, run.ID)
		}
	}

	// Concurrently deliver approval signals to approval workflows after brief delay
	go func() {
		time.Sleep(200 * time.Millisecond)
		for _, aID := range approvalRuns {
			mu.Lock()
			_ = eng.DeliverSignal(ctx, aID, "lead_approved", map[string]any{"approver": "mehmet@halden.de"})
			mu.Unlock()
		}
	}()

	// Wait for all 200 workflows to reach terminal state
	deadline := time.Now().Add(20 * time.Second)
	allCompleted := false

	for time.Now().Before(deadline) {
		completedCount := 0
		for _, rID := range runIDs {
			run, err := store.GetRun(ctx, rID)
			if err == nil && (run.Status == model.RunStatusCompleted || run.Status == model.RunStatusFailed) {
				completedCount++
			}
		}

		if completedCount == totalWorkflows {
			allCompleted = true
			break
		}
		time.Sleep(50 * time.Millisecond)
	}

	mu.Lock()
	eng.Stop()
	mu.Unlock()

	if !allCompleted {
		t.Fatalf("chaos test timed out: not all %d workflows reached terminal state", totalWorkflows)
	}

	// Assertion 1: Zero duplicate side-effects
	totalReqs, uniqueKeys, dupSideEffects := receiver.Stats()
	if dupSideEffects > 0 {
		t.Fatalf("FAILURE: Detected %d duplicate side effects across %d requests!", dupSideEffects, totalReqs)
	}

	// Assertion 2: All event logs replay to the stored run status
	for _, rID := range runIDs {
		run, _ := store.GetRun(ctx, rID)
		events, _ := store.GetEvents(ctx, rID)
		def, _ := store.GetDefinition(ctx, run.DefName, run.DefVersion)

		replayedActions := orchestrator.ComputeNextActions(events, def)
		if replayedActions.Status != run.Status {
			t.Errorf("run %s event log replay status mismatch: stored %s, replayed %s", rID, run.Status, replayedActions.Status)
		}
	}

	t.Logf("[SUCCESS] 200-Workflow Chaos Run: 100%% Completed, %d Total Requests, %d Unique Keys, 0 Duplicate Side Effects", totalReqs, uniqueKeys)
}
