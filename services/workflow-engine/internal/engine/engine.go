package engine

import (
	"context"
	"fmt"
	"log/slog"
	"sync"
	"time"

	"fieldkit/workflow-engine/internal/executor"
	"fieldkit/workflow-engine/internal/model"
	"fieldkit/workflow-engine/internal/orchestrator"
	"fieldkit/workflow-engine/internal/storage"
	"github.com/google/uuid"
)

type Engine struct {
	store       storage.Storage
	executor    executor.StepExecutor
	workerCount int
	workerID    string
	stopCh      chan struct{}
	wg          sync.WaitGroup
}

func NewEngine(store storage.Storage, exec executor.StepExecutor, workerCount int) *Engine {
	if exec == nil {
		exec = executor.NewDefaultExecutor()
	}
	if workerCount <= 0 {
		workerCount = 4
	}
	return &Engine{
		store:       store,
		executor:    exec,
		workerCount: workerCount,
		workerID:    fmt.Sprintf("worker-%s", uuid.New().String()[:8]),
		stopCh:      make(chan struct{}),
	}
}

func (e *Engine) Start(ctx context.Context) {
	slog.Info("starting workflow engine worker pool", "workers", e.workerCount, "worker_id", e.workerID)
	for i := 0; i < e.workerCount; i++ {
		e.wg.Add(1)
		go e.workerLoop(ctx, i)
	}
}

func (e *Engine) Stop() {
	close(e.stopCh)
	e.wg.Wait()
	slog.Info("workflow engine stopped cleanly")
}

func (e *Engine) StartWorkflow(ctx context.Context, defName, defVersion string, input map[string]any) (*model.WorkflowRun, error) {
	def, err := e.store.GetDefinition(ctx, defName, defVersion)
	if err != nil {
		return nil, fmt.Errorf("failed to get definition: %w", err)
	}

	runID := uuid.New()
	now := time.Now().UTC()
	run := &model.WorkflowRun{
		ID:         runID,
		DefName:    defName,
		DefVersion: defVersion,
		Status:     model.RunStatusRunning,
		Input:      input,
		Output:     make(map[string]any),
		CreatedAt:  now,
		UpdatedAt:  now,
	}

	if err := e.store.CreateRun(ctx, run); err != nil {
		return nil, fmt.Errorf("failed to create run: %w", err)
	}

	// Append initial start event
	startEv := model.WorkflowEvent{
		RunID:     runID,
		Type:      model.EventWorkflowStarted,
		Payload:   map[string]any{"input": input},
		Timestamp: now,
	}
	if err := e.store.AppendEvents(ctx, runID, []model.WorkflowEvent{startEv}); err != nil {
		return nil, fmt.Errorf("failed to append start event: %w", err)
	}

	// Compute initial actions
	actions := orchestrator.ComputeNextActions([]model.WorkflowEvent{startEv}, def)
	run.Status = actions.Status

	if len(actions.TasksToSchedule) > 0 {
		var scheduleEvents []model.WorkflowEvent
		for _, task := range actions.TasksToSchedule {
			scheduleEvents = append(scheduleEvents, model.WorkflowEvent{
				RunID:     runID,
				Type:      model.EventStepScheduled,
				Payload:   map[string]any{"step_id": task.StepID},
				Timestamp: time.Now().UTC(),
			})
		}
		_ = e.store.AppendEvents(ctx, runID, scheduleEvents)
		if err := e.store.EnqueueTasks(ctx, actions.TasksToSchedule); err != nil {
			return nil, fmt.Errorf("failed to enqueue tasks: %w", err)
		}
	}

	_ = e.store.UpdateRun(ctx, run)
	return run, nil
}

func (e *Engine) DeliverSignal(ctx context.Context, runID uuid.UUID, signalName string, payload map[string]any) error {
	run, err := e.store.GetRun(ctx, runID)
	if err != nil {
		return err
	}
	def, err := e.store.GetDefinition(ctx, run.DefName, run.DefVersion)
	if err != nil {
		return err
	}

	if payload == nil {
		payload = make(map[string]any)
	}
	payload["signal_name"] = signalName

	ev := model.WorkflowEvent{
		RunID:     runID,
		Type:      model.EventSignalReceived,
		Payload:   payload,
		Timestamp: time.Now().UTC(),
	}
	if err := e.store.AppendEvents(ctx, runID, []model.WorkflowEvent{ev}); err != nil {
		return err
	}

	// Replay and update run
	allEvents, err := e.store.GetEvents(ctx, runID)
	if err != nil {
		return err
	}
	actions := orchestrator.ComputeNextActions(allEvents, def)
	run.Status = actions.Status

	if len(actions.TasksToSchedule) > 0 {
		var scheduleEvents []model.WorkflowEvent
		for _, task := range actions.TasksToSchedule {
			scheduleEvents = append(scheduleEvents, model.WorkflowEvent{
				RunID:     runID,
				Type:      model.EventStepScheduled,
				Payload:   map[string]any{"step_id": task.StepID},
				Timestamp: time.Now().UTC(),
			})
		}
		_ = e.store.AppendEvents(ctx, runID, scheduleEvents)
		_ = e.store.EnqueueTasks(ctx, actions.TasksToSchedule)
	}

	return e.store.UpdateRun(ctx, run)
}

func (e *Engine) CancelRun(ctx context.Context, runID uuid.UUID) error {
	run, err := e.store.GetRun(ctx, runID)
	if err != nil {
		return err
	}
	run.Status = model.RunStatusCancelled

	ev := model.WorkflowEvent{
		RunID:     runID,
		Type:      model.EventWorkflowCancelled,
		Payload:   map[string]any{"reason": "User cancelled run"},
		Timestamp: time.Now().UTC(),
	}
	_ = e.store.AppendEvents(ctx, runID, []model.WorkflowEvent{ev})
	return e.store.UpdateRun(ctx, run)
}

func (e *Engine) workerLoop(ctx context.Context, workerIdx int) {
	defer e.wg.Done()
	ticker := time.NewTicker(20 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-e.stopCh:
			return
		case <-ctx.Done():
			return
		case <-ticker.C:
			e.processNextTask(ctx)
		}
	}
}

func (e *Engine) processNextTask(ctx context.Context) {
	task, err := e.store.LeaseTask(ctx, e.workerID, 15*time.Second)
	if err != nil || task == nil {
		return
	}

	run, err := e.store.GetRun(ctx, task.RunID)
	if err != nil || run.Status == model.RunStatusCancelled {
		_ = e.store.CompleteTask(ctx, task.ID)
		return
	}

	def, err := e.store.GetDefinition(ctx, run.DefName, run.DefVersion)
	if err != nil {
		_ = e.store.FailTask(ctx, task.ID, false, 0)
		return
	}

	// Find step
	var targetStep *model.StepDefinition
	for i := range def.Steps {
		if def.Steps[i].ID == task.StepID {
			targetStep = &def.Steps[i]
			break
		}
	}
	if targetStep == nil {
		// Check compensation steps
		for i := range def.Compensations {
			if def.Compensations[i].ID == task.StepID {
				targetStep = &def.Compensations[i]
				break
			}
		}
	}

	if targetStep == nil {
		_ = e.store.CompleteTask(ctx, task.ID)
		return
	}

	// Record StepStarted
	_ = e.store.AppendEvents(ctx, task.RunID, []model.WorkflowEvent{
		{
			RunID:     task.RunID,
			Type:      model.EventStepStarted,
			Payload:   map[string]any{"step_id": task.StepID, "attempt": task.Attempt},
			Timestamp: time.Now().UTC(),
		},
	})

	// Execute
	output, execErr := e.executor.Execute(ctx, targetStep, run, task)
	now := time.Now().UTC()

	if execErr != nil {
		// Check retries
		maxAttempts := 3
		if targetStep.RetryPolicy != nil && targetStep.RetryPolicy.MaxAttempts > 0 {
			maxAttempts = targetStep.RetryPolicy.MaxAttempts
		}

		if task.Attempt < maxAttempts {
			_ = e.store.FailTask(ctx, task.ID, true, 50*time.Millisecond)
			return
		}

		// Terminal Failure
		_ = e.store.CompleteTask(ctx, task.ID)
		_ = e.store.AppendEvents(ctx, task.RunID, []model.WorkflowEvent{
			{
				RunID:     task.RunID,
				Type:      model.EventStepFailed,
				Payload:   map[string]any{"step_id": task.StepID, "error": execErr.Error(), "terminal": true},
				Timestamp: now,
			},
		})
	} else {
		// Success
		_ = e.store.CompleteTask(ctx, task.ID)
		_ = e.store.AppendEvents(ctx, task.RunID, []model.WorkflowEvent{
			{
				RunID:     task.RunID,
				Type:      model.EventStepCompleted,
				Payload:   map[string]any{"step_id": task.StepID, "output": output},
				Timestamp: now,
			},
		})
	}

	// Replay full events
	events, err := e.store.GetEvents(ctx, task.RunID)
	if err != nil {
		return
	}

	actions := orchestrator.ComputeNextActions(events, def)
	run.Status = actions.Status
	run.Output = make(map[string]any)
	for k, v := range actions.StepOutputs {
		run.Output[k] = v
	}

	if actions.Status == model.RunStatusCompleted {
		_ = e.store.AppendEvents(ctx, task.RunID, []model.WorkflowEvent{
			{
				RunID:     task.RunID,
				Type:      model.EventWorkflowCompleted,
				Payload:   map[string]any{"output": actions.StepOutputs},
				Timestamp: now,
			},
		})
	} else if actions.Status == model.RunStatusFailed {
		run.ErrorText = actions.TerminalError
		_ = e.store.AppendEvents(ctx, task.RunID, []model.WorkflowEvent{
			{
				RunID:     task.RunID,
				Type:      model.EventWorkflowFailed,
				Payload:   map[string]any{"error": actions.TerminalError},
				Timestamp: now,
			},
		})
		if len(actions.CompensationsToSchedule) > 0 {
			_ = e.store.EnqueueTasks(ctx, actions.CompensationsToSchedule)
		}
	} else if len(actions.TasksToSchedule) > 0 {
		var scheduleEvents []model.WorkflowEvent
		for _, nextTask := range actions.TasksToSchedule {
			scheduleEvents = append(scheduleEvents, model.WorkflowEvent{
				RunID:     task.RunID,
				Type:      model.EventStepScheduled,
				Payload:   map[string]any{"step_id": nextTask.StepID},
				Timestamp: now,
			})
		}
		_ = e.store.AppendEvents(ctx, task.RunID, scheduleEvents)
		_ = e.store.EnqueueTasks(ctx, actions.TasksToSchedule)
	}

	_ = e.store.UpdateRun(ctx, run)
}
