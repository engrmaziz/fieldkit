package api

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"fieldkit/workflow-engine/internal/engine"
	"fieldkit/workflow-engine/internal/executor"
	"fieldkit/workflow-engine/internal/storage"
)

func setupTestRouter() (http.Handler, *engine.Engine, storage.Storage) {
	store := storage.NewMemoryStorage()
	exec := executor.NewDefaultExecutor()
	eng := engine.NewEngine(store, exec, 2)
	eng.Start(context.Background())
	handler := NewRouter(store, eng)
	return handler, eng, store
}

func TestRouter_HealthAndReady(t *testing.T) {
	handler, eng, _ := setupTestRouter()
	defer eng.Stop()

	// /healthz
	req := httptest.NewRequest("GET", "/healthz", nil)
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200 on /healthz, got %d", w.Code)
	}

	// /readyz
	req = httptest.NewRequest("GET", "/readyz", nil)
	w = httptest.NewRecorder()
	handler.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200 on /readyz, got %d", w.Code)
	}
}

func TestRouter_RegisterAndRunWorkflow(t *testing.T) {
	handler, eng, _ := setupTestRouter()
	defer eng.Stop()

	yamlWorkflow := `
name: pipeline-quick
version: 1.0.0
description: "Quick test pipeline"
steps:
  - id: step_one
    type: wait
    wait_duration_sec: 0
  - id: step_two
    type: wait
    depends_on: ["step_one"]
    wait_duration_sec: 0
`
	// 1. Register definition
	req := httptest.NewRequest("POST", "/definitions", bytes.NewBufferString(yamlWorkflow))
	req.Header.Set("Content-Type", "application/yaml")
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, req)
	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201 on POST /definitions, got %d: %s", w.Code, w.Body.String())
	}

	// 2. Start run
	startReqBody := `{"def_name": "pipeline-quick", "def_version": "1.0.0", "input": {"key": "val"}}`
	req = httptest.NewRequest("POST", "/runs", bytes.NewBufferString(startReqBody))
	req.Header.Set("Content-Type", "application/json")
	w = httptest.NewRecorder()
	handler.ServeHTTP(w, req)
	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201 on POST /runs, got %d: %s", w.Code, w.Body.String())
	}

	var runResp map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &runResp); err != nil {
		t.Fatalf("failed to decode run response: %v", err)
	}
	runID := runResp["id"].(string)

	// Wait for workers to complete the 2 wait steps
	time.Sleep(150 * time.Millisecond)

	// 3. Inspect run status
	req = httptest.NewRequest("GET", "/runs/"+runID, nil)
	w = httptest.NewRecorder()
	handler.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200 on GET /runs/{id}, got %d", w.Code)
	}

	var getRunResp map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &getRunResp)
	if getRunResp["status"] != "COMPLETED" {
		t.Errorf("expected run status COMPLETED, got %v", getRunResp["status"])
	}

	// 4. Inspect events
	req = httptest.NewRequest("GET", "/runs/"+runID+"/events", nil)
	w = httptest.NewRecorder()
	handler.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200 on GET /runs/{id}/events, got %d", w.Code)
	}
}

func TestRouter_SignalApprovalGate(t *testing.T) {
	handler, eng, _ := setupTestRouter()
	defer eng.Stop()

	approvalYAML := `
name: gate-pipeline
version: 1.0.0
description: "Human approval gate test"
steps:
  - id: step_gate
    type: human_approval
    signal_name: "admin_approved"
`
	req := httptest.NewRequest("POST", "/definitions", bytes.NewBufferString(approvalYAML))
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, req)

	// Start run
	req = httptest.NewRequest("POST", "/runs", bytes.NewBufferString(`{"def_name": "gate-pipeline", "def_version": "1.0.0"}`))
	w = httptest.NewRecorder()
	handler.ServeHTTP(w, req)
	var runResp map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &runResp)
	runID := runResp["id"].(string)

	time.Sleep(60 * time.Millisecond)

	// Check that run is SUSPENDED
	req = httptest.NewRequest("GET", "/runs/"+runID, nil)
	w = httptest.NewRecorder()
	handler.ServeHTTP(w, req)
	var checkRun map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &checkRun)
	if checkRun["status"] != "SUSPENDED" {
		t.Fatalf("expected SUSPENDED, got %v", checkRun["status"])
	}

	// Deliver signal
	req = httptest.NewRequest("POST", "/runs/"+runID+"/signals/admin_approved", bytes.NewBufferString(`{"approved_by": "mehmet"}`))
	w = httptest.NewRecorder()
	handler.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200 on deliver signal, got %d", w.Code)
	}

	time.Sleep(60 * time.Millisecond)

	// Check that run progressed to COMPLETED
	req = httptest.NewRequest("GET", "/runs/"+runID, nil)
	w = httptest.NewRecorder()
	handler.ServeHTTP(w, req)
	var finalRun map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &finalRun)
	if finalRun["status"] != "COMPLETED" {
		t.Errorf("expected COMPLETED after signal, got %v", finalRun["status"])
	}
}
