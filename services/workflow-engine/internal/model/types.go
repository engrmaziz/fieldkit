package model

import (
	"time"

	"github.com/google/uuid"
)

type StepType string

const (
	StepTypeHTTP          StepType = "http"
	StepTypeWait          StepType = "wait"
	StepTypeBranch        StepType = "branch"
	StepTypeMap           StepType = "map"
	StepTypeHumanApproval StepType = "human_approval"
)

type RunStatus string

const (
	RunStatusPending   RunStatus = "PENDING"
	RunStatusRunning   RunStatus = "RUNNING"
	RunStatusSuspended RunStatus = "SUSPENDED"
	RunStatusCompleted RunStatus = "COMPLETED"
	RunStatusFailed    RunStatus = "FAILED"
	RunStatusCancelled RunStatus = "CANCELLED"
)

type TaskStatus string

const (
	TaskStatusQueued    TaskStatus = "QUEUED"
	TaskStatusLeased    TaskStatus = "LEASED"
	TaskStatusCompleted TaskStatus = "COMPLETED"
	TaskStatusFailed    TaskStatus = "FAILED"
)

type EventType string

const (
	EventWorkflowStarted      EventType = "WorkflowStarted"
	EventStepScheduled        EventType = "StepScheduled"
	EventStepStarted          EventType = "StepStarted"
	EventStepCompleted        EventType = "StepCompleted"
	EventStepFailed           EventType = "StepFailed"
	EventTimerFired           EventType = "TimerFired"
	EventSignalReceived       EventType = "SignalReceived"
	EventApprovalGranted      EventType = "ApprovalGranted"
	EventCompensationStarted  EventType = "CompensationStarted"
	EventWorkflowCompleted    EventType = "WorkflowCompleted"
	EventWorkflowFailed       EventType = "WorkflowFailed"
	EventWorkflowCancelled    EventType = "WorkflowCancelled"
)

// RetryPolicy defines backoff settings for task failures.
type RetryPolicy struct {
	MaxAttempts        int     `json:"max_attempts" yaml:"max_attempts"`
	InitialIntervalSec int     `json:"initial_interval_sec" yaml:"initial_interval_sec"`
	BackoffMultiplier  float64 `json:"backoff_multiplier" yaml:"backoff_multiplier"`
}

// StepDefinition represents a single node in the workflow DAG.
type StepDefinition struct {
	ID             string            `json:"id" yaml:"id"`
	Type           StepType          `json:"type" yaml:"type"`
	DependsOn      []string          `json:"depends_on,omitempty" yaml:"depends_on,omitempty"`
	URL            string            `json:"url,omitempty" yaml:"url,omitempty"`
	Method         string            `json:"method,omitempty" yaml:"method,omitempty"`
	Headers        map[string]string `json:"headers,omitempty" yaml:"headers,omitempty"`
	Body           map[string]any    `json:"body,omitempty" yaml:"body,omitempty"`
	WaitDurationSec int              `json:"wait_duration_sec,omitempty" yaml:"wait_duration_sec,omitempty"`
	Condition      string            `json:"condition,omitempty" yaml:"condition,omitempty"`       // Condition for branch/filter
	Items          string            `json:"items,omitempty" yaml:"items,omitempty"`               // Key in input for map fan-out
	MaxConcurrency int               `json:"max_concurrency,omitempty" yaml:"max_concurrency,omitempty"`
	SignalName     string            `json:"signal_name,omitempty" yaml:"signal_name,omitempty"`   // Signal name for human_approval
	TimeoutSec     int               `json:"timeout_sec,omitempty" yaml:"timeout_sec,omitempty"`
	RetryPolicy    *RetryPolicy      `json:"retry_policy,omitempty" yaml:"retry_policy,omitempty"`
	CompensateWith string            `json:"compensate_with,omitempty" yaml:"compensate_with,omitempty"` // Step ID of saga compensation
}

// WorkflowDefinition represents a complete versioned YAML workflow.
type WorkflowDefinition struct {
	Name          string           `json:"name" yaml:"name"`
	Version       string           `json:"version" yaml:"version"`
	Description   string           `json:"description" yaml:"description"`
	Schedule      string           `json:"schedule,omitempty" yaml:"schedule,omitempty"` // Cron expression
	Steps         []StepDefinition `json:"steps" yaml:"steps"`
	Compensations []StepDefinition `json:"compensations,omitempty" yaml:"compensations,omitempty"`
	YAMLContent   string           `json:"yaml_content,omitempty"`
	ContentHash   string           `json:"content_hash,omitempty"`
	CreatedAt     time.Time        `json:"created_at"`
}

// WorkflowRun captures the state of an executed workflow instance.
type WorkflowRun struct {
	ID         uuid.UUID      `json:"id"`
	DefName    string         `json:"def_name"`
	DefVersion string         `json:"def_version"`
	Status     RunStatus      `json:"status"`
	Input      map[string]any `json:"input"`
	Output     map[string]any `json:"output"`
	ErrorText  string         `json:"error_text,omitempty"`
	CreatedAt  time.Time      `json:"created_at"`
	UpdatedAt  time.Time      `json:"updated_at"`
}

// WorkflowEvent is an immutable append-only record in the event log.
type WorkflowEvent struct {
	RunID     uuid.UUID      `json:"run_id"`
	Seq       int            `json:"seq"`
	Type      EventType      `json:"type"`
	Payload   map[string]any `json:"payload"`
	Timestamp time.Time      `json:"timestamp"`
}

// WorkflowTask represents an active or queued worker execution unit.
type WorkflowTask struct {
	ID             uuid.UUID  `json:"id"`
	RunID          uuid.UUID  `json:"run_id"`
	StepID         string     `json:"step_id"`
	Attempt        int        `json:"attempt"`
	Status         TaskStatus `json:"status"`
	LeaseOwner     string     `json:"lease_owner,omitempty"`
	LeaseUntil     time.Time  `json:"lease_until"`
	RunAfter       time.Time  `json:"run_after"`
	IdempotencyKey string     `json:"idempotency_key"`
}
