package orchestrator

import (
	"fmt"
	"time"

	"fieldkit/workflow-engine/internal/model"
	"github.com/google/uuid"
)

// NextActions describes the decision computed by replaying events against the workflow definition.
type NextActions struct {
	Status                  model.RunStatus
	TasksToSchedule         []model.WorkflowTask
	CompensationsToSchedule []model.WorkflowTask
	StepOutputs             map[string]map[string]any
	WaitingForSignal        string
	TerminalError           string
}

// ComputeNextActions is a pure, deterministic function that evaluates the append-only event log.
func ComputeNextActions(events []model.WorkflowEvent, def *model.WorkflowDefinition) NextActions {
	if len(events) == 0 {
		return NextActions{Status: model.RunStatusPending}
	}

	runID := events[0].RunID
	completedSteps := make(map[string]map[string]any)
	scheduledSteps := make(map[string]bool)
	failedSteps := make(map[string]string)
	receivedSignals := make(map[string]map[string]any)
	var completedStepOrder []string

	isCancelled := false
	isTerminalFailed := false
	var terminalErrMsg string

	// Replay event history
	for _, ev := range events {
		switch ev.Type {
		case model.EventWorkflowCancelled:
			isCancelled = true

		case model.EventStepScheduled:
			if stepID, ok := ev.Payload["step_id"].(string); ok {
				scheduledSteps[stepID] = true
			}

		case model.EventStepCompleted:
			if stepID, ok := ev.Payload["step_id"].(string); ok {
				var out map[string]any
				if o, ok := ev.Payload["output"].(map[string]any); ok {
					out = o
				}
				completedSteps[stepID] = out
				completedStepOrder = append(completedStepOrder, stepID)
			}

		case model.EventStepFailed:
			if stepID, ok := ev.Payload["step_id"].(string); ok {
				errMsg, _ := ev.Payload["error"].(string)
				failedSteps[stepID] = errMsg
				if term, _ := ev.Payload["terminal"].(bool); term {
					isTerminalFailed = true
					terminalErrMsg = errMsg
				}
			}

		case model.EventSignalReceived:
			if sigName, ok := ev.Payload["signal_name"].(string); ok {
				receivedSignals[sigName] = ev.Payload
			}
		}
	}

	actions := NextActions{
		Status:      model.RunStatusRunning,
		StepOutputs: completedSteps,
	}

	if isCancelled {
		actions.Status = model.RunStatusCancelled
		return actions
	}

	if isTerminalFailed {
		actions.Status = model.RunStatusFailed
		actions.TerminalError = terminalErrMsg

		// Calculate Saga Compensations in reverse order of completed steps
		var compensations []model.WorkflowTask
		compDefs := make(map[string]model.StepDefinition)
		for _, comp := range def.Compensations {
			compDefs[comp.ID] = comp
		}

		for i := len(completedStepOrder) - 1; i >= 0; i-- {
			sID := completedStepOrder[i]
			// Find step in definition
			for _, step := range def.Steps {
				if step.ID == sID && step.CompensateWith != "" {
					if _, exists := compDefs[step.CompensateWith]; exists {
						compensations = append(compensations, model.WorkflowTask{
							ID:             uuid.New(),
							RunID:          runID,
							StepID:         step.CompensateWith,
							Attempt:        1,
							Status:         model.TaskStatusQueued,
							RunAfter:       time.Now().UTC(),
							IdempotencyKey: fmt.Sprintf("%s:comp:%s", runID.String(), step.CompensateWith),
						})
					}
				}
			}
		}
		actions.CompensationsToSchedule = compensations
		return actions
	}

	// Check for approval gates that have now received signals
	for _, step := range def.Steps {
		if step.Type == model.StepTypeHumanApproval {
			if _, done := completedSteps[step.ID]; !done {
				// Check if dependencies met
				allDepsDone := true
				for _, dep := range step.DependsOn {
					if _, ok := completedSteps[dep]; !ok {
						allDepsDone = false
						break
					}
				}
				if allDepsDone {
					if sigPayload, ok := receivedSignals[step.SignalName]; ok {
						completedSteps[step.ID] = sigPayload
						completedStepOrder = append(completedStepOrder, step.ID)
					}
				}
			}
		}
	}

	// Identify next runnable steps
	var readyTasks []model.WorkflowTask
	var pendingApprovalSignal string

	for _, step := range def.Steps {
		if _, done := completedSteps[step.ID]; done {
			continue
		}
		if scheduledSteps[step.ID] {
			continue
		}

		// Check dependencies
		depsMet := true
		for _, dep := range step.DependsOn {
			if _, ok := completedSteps[dep]; !ok {
				depsMet = false
				break
			}
		}

		if !depsMet {
			continue
		}

		// Step is ready!
		if step.Type == model.StepTypeHumanApproval {
			// Gate paused until signal
			if _, ok := receivedSignals[step.SignalName]; !ok {
				pendingApprovalSignal = step.SignalName
				continue
			}
		}

		readyTasks = append(readyTasks, model.WorkflowTask{
			ID:             uuid.New(),
			RunID:          runID,
			StepID:         step.ID,
			Attempt:        1,
			Status:         model.TaskStatusQueued,
			RunAfter:       time.Now().UTC(),
			IdempotencyKey: fmt.Sprintf("%s:%s", runID.String(), step.ID),
		})
	}

	// Check if all steps in definition are completed
	if len(completedSteps) == len(def.Steps) {
		actions.Status = model.RunStatusCompleted
		return actions
	}

	if pendingApprovalSignal != "" && len(readyTasks) == 0 {
		actions.Status = model.RunStatusSuspended
		actions.WaitingForSignal = pendingApprovalSignal
		return actions
	}

	actions.TasksToSchedule = readyTasks
	actions.Status = model.RunStatusRunning
	return actions
}
