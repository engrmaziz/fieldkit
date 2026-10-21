package storage

import (
	"context"
	"fmt"
	"sync"
	"time"

	"fieldkit/workflow-engine/internal/model"
	"github.com/google/uuid"
)

// Storage defines the persistence interface for workflow definitions, runs, events, and tasks.
type Storage interface {
	SaveDefinition(ctx context.Context, def *model.WorkflowDefinition) error
	GetDefinition(ctx context.Context, name, version string) (*model.WorkflowDefinition, error)
	ListDefinitions(ctx context.Context) ([]*model.WorkflowDefinition, error)

	CreateRun(ctx context.Context, run *model.WorkflowRun) error
	GetRun(ctx context.Context, id uuid.UUID) (*model.WorkflowRun, error)
	UpdateRun(ctx context.Context, run *model.WorkflowRun) error
	ListRuns(ctx context.Context) ([]*model.WorkflowRun, error)

	AppendEvents(ctx context.Context, runID uuid.UUID, events []model.WorkflowEvent) error
	GetEvents(ctx context.Context, runID uuid.UUID) ([]model.WorkflowEvent, error)

	EnqueueTasks(ctx context.Context, tasks []model.WorkflowTask) error
	LeaseTask(ctx context.Context, workerID string, leaseDuration time.Duration) (*model.WorkflowTask, error)
	HeartbeatTask(ctx context.Context, taskID uuid.UUID, workerID string, leaseDuration time.Duration) error
	CompleteTask(ctx context.Context, taskID uuid.UUID) error
	FailTask(ctx context.Context, taskID uuid.UUID, retryable bool, backoff time.Duration) error
}

// MemoryStorage is a thread-safe, in-memory implementation supporting transactional semantics.
type MemoryStorage struct {
	mu          sync.RWMutex
	definitions map[string]*model.WorkflowDefinition // "name:version" -> def
	runs        map[uuid.UUID]*model.WorkflowRun
	events      map[uuid.UUID][]model.WorkflowEvent
	tasks       map[uuid.UUID]*model.WorkflowTask
}

func NewMemoryStorage() *MemoryStorage {
	return &MemoryStorage{
		definitions: make(map[string]*model.WorkflowDefinition),
		runs:        make(map[uuid.UUID]*model.WorkflowRun),
		events:      make(map[uuid.UUID][]model.WorkflowEvent),
		tasks:       make(map[uuid.UUID]*model.WorkflowTask),
	}
}

func (s *MemoryStorage) SaveDefinition(ctx context.Context, def *model.WorkflowDefinition) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	key := fmt.Sprintf("%s:%s", def.Name, def.Version)
	s.definitions[key] = def
	return nil
}

func (s *MemoryStorage) GetDefinition(ctx context.Context, name, version string) (*model.WorkflowDefinition, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	key := fmt.Sprintf("%s:%s", name, version)
	def, exists := s.definitions[key]
	if !exists {
		return nil, fmt.Errorf("definition '%s:%s' not found", name, version)
	}
	return def, nil
}

func (s *MemoryStorage) ListDefinitions(ctx context.Context) ([]*model.WorkflowDefinition, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	list := make([]*model.WorkflowDefinition, 0, len(s.definitions))
	for _, def := range s.definitions {
		list = append(list, def)
	}
	return list, nil
}

func (s *MemoryStorage) CreateRun(ctx context.Context, run *model.WorkflowRun) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.runs[run.ID] = run
	return nil
}

func (s *MemoryStorage) GetRun(ctx context.Context, id uuid.UUID) (*model.WorkflowRun, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	run, exists := s.runs[id]
	if !exists {
		return nil, fmt.Errorf("run '%s' not found", id)
	}
	return run, nil
}

func (s *MemoryStorage) UpdateRun(ctx context.Context, run *model.WorkflowRun) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	run.UpdatedAt = time.Now().UTC()
	s.runs[run.ID] = run
	return nil
}

func (s *MemoryStorage) ListRuns(ctx context.Context) ([]*model.WorkflowRun, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	list := make([]*model.WorkflowRun, 0, len(s.runs))
	for _, run := range s.runs {
		list = append(list, run)
	}
	return list, nil
}

func (s *MemoryStorage) AppendEvents(ctx context.Context, runID uuid.UUID, events []model.WorkflowEvent) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	existing := s.events[runID]
	for i := range events {
		events[i].Seq = len(existing) + i + 1
		if events[i].Timestamp.IsZero() {
			events[i].Timestamp = time.Now().UTC()
		}
	}
	s.events[runID] = append(existing, events...)
	return nil
}

func (s *MemoryStorage) GetEvents(ctx context.Context, runID uuid.UUID) ([]model.WorkflowEvent, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	evs, exists := s.events[runID]
	if !exists {
		return []model.WorkflowEvent{}, nil
	}
	cp := make([]model.WorkflowEvent, len(evs))
	copy(cp, evs)
	return cp, nil
}

func (s *MemoryStorage) EnqueueTasks(ctx context.Context, tasks []model.WorkflowTask) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	for i := range tasks {
		if tasks[i].ID == uuid.Nil {
			tasks[i].ID = uuid.New()
		}
		if tasks[i].RunAfter.IsZero() {
			tasks[i].RunAfter = time.Now().UTC()
		}
		tasks[i].Status = model.TaskStatusQueued
		s.tasks[tasks[i].ID] = &tasks[i]
	}
	return nil
}

// LeaseTask mimics PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1`.
func (s *MemoryStorage) LeaseTask(ctx context.Context, workerID string, leaseDuration time.Duration) (*model.WorkflowTask, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	now := time.Now().UTC()

	for _, task := range s.tasks {
		if task.Status == model.TaskStatusQueued && task.RunAfter.Before(now) {
			task.Status = model.TaskStatusLeased
			task.LeaseOwner = workerID
			task.LeaseUntil = now.Add(leaseDuration)
			return task, nil
		}
		// Expired lease re-lease
		if task.Status == model.TaskStatusLeased && task.LeaseUntil.Before(now) {
			task.LeaseOwner = workerID
			task.LeaseUntil = now.Add(leaseDuration)
			task.Attempt++
			return task, nil
		}
	}
	return nil, nil // No task ready
}

func (s *MemoryStorage) HeartbeatTask(ctx context.Context, taskID uuid.UUID, workerID string, leaseDuration time.Duration) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	task, exists := s.tasks[taskID]
	if !exists {
		return fmt.Errorf("task '%s' not found", taskID)
	}
	if task.LeaseOwner != workerID {
		return fmt.Errorf("worker '%s' does not own task '%s'", workerID, taskID)
	}
	task.LeaseUntil = time.Now().UTC().Add(leaseDuration)
	return nil
}

func (s *MemoryStorage) CompleteTask(ctx context.Context, taskID uuid.UUID) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	task, exists := s.tasks[taskID]
	if !exists {
		return fmt.Errorf("task '%s' not found", taskID)
	}
	task.Status = model.TaskStatusCompleted
	delete(s.tasks, taskID)
	return nil
}

func (s *MemoryStorage) FailTask(ctx context.Context, taskID uuid.UUID, retryable bool, backoff time.Duration) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	task, exists := s.tasks[taskID]
	if !exists {
		return fmt.Errorf("task '%s' not found", taskID)
	}
	if retryable {
		task.Status = model.TaskStatusQueued
		task.LeaseOwner = ""
		task.RunAfter = time.Now().UTC().Add(backoff)
	} else {
		task.Status = model.TaskStatusFailed
		delete(s.tasks, taskID)
	}
	return nil
}
