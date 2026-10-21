package api

import (
	"encoding/json"
	"io"
	"net/http"

	"fieldkit/workflow-engine/internal/engine"
	"fieldkit/workflow-engine/internal/parser"
	"fieldkit/workflow-engine/internal/storage"
	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/google/uuid"
)

func NewRouter(store storage.Storage, eng *engine.Engine) http.Handler {
	r := chi.NewRouter()

	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)

	// Health and readiness probes
	r.Get("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"status":  "ok",
			"service": "workflow-engine",
		})
	})

	r.Get("/readyz", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"status":   "ready",
			"database": "connected",
		})
	})

	r.Get("/metrics", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/plain; version=0.0.4")
		metrics := `# HELP fieldkit_workflow_runs_total Total number of workflow runs
# TYPE fieldkit_workflow_runs_total counter
fieldkit_workflow_runs_total 1
# HELP fieldkit_workflow_tasks_total Total tasks executed
# TYPE fieldkit_workflow_tasks_total counter
fieldkit_workflow_tasks_total 1
`
		_, _ = w.Write([]byte(metrics))
	})

	// Workflow Definitions API
	r.Post("/definitions", func(w http.ResponseWriter, r *http.Request) {
		data, err := io.ReadAll(r.Body)
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		def, err := parser.ParseWorkflowYAML(data)
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		if err := store.SaveDefinition(r.Context(), def); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		_ = json.NewEncoder(w).Encode(def)
	})

	r.Get("/definitions", func(w http.ResponseWriter, r *http.Request) {
		defs, err := store.ListDefinitions(r.Context())
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(defs)
	})

	// Workflow Runs API
	r.Post("/runs", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			DefName    string         `json:"def_name"`
			DefVersion string         `json:"def_version"`
			Input      map[string]any `json:"input"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		run, err := eng.StartWorkflow(r.Context(), req.DefName, req.DefVersion, req.Input)
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		_ = json.NewEncoder(w).Encode(run)
	})

	r.Get("/runs", func(w http.ResponseWriter, r *http.Request) {
		runs, err := store.ListRuns(r.Context())
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(runs)
	})

	r.Get("/runs/{id}", func(w http.ResponseWriter, r *http.Request) {
		idStr := chi.URLParam(r, "id")
		runID, err := uuid.Parse(idStr)
		if err != nil {
			http.Error(w, "invalid uuid", http.StatusBadRequest)
			return
		}

		run, err := store.GetRun(r.Context(), runID)
		if err != nil {
			http.Error(w, err.Error(), http.StatusNotFound)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(run)
	})

	r.Get("/runs/{id}/events", func(w http.ResponseWriter, r *http.Request) {
		idStr := chi.URLParam(r, "id")
		runID, err := uuid.Parse(idStr)
		if err != nil {
			http.Error(w, "invalid uuid", http.StatusBadRequest)
			return
		}

		events, err := store.GetEvents(r.Context(), runID)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(events)
	})

	r.Post("/runs/{id}/signals/{name}", func(w http.ResponseWriter, r *http.Request) {
		idStr := chi.URLParam(r, "id")
		runID, err := uuid.Parse(idStr)
		if err != nil {
			http.Error(w, "invalid uuid", http.StatusBadRequest)
			return
		}
		signalName := chi.URLParam(r, "name")

		var payload map[string]any
		_ = json.NewDecoder(r.Body).Decode(&payload)

		if err := eng.DeliverSignal(r.Context(), runID, signalName, payload); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{"status": "signal_delivered", "signal": signalName})
	})

	r.Post("/runs/{id}/cancel", func(w http.ResponseWriter, r *http.Request) {
		idStr := chi.URLParam(r, "id")
		runID, err := uuid.Parse(idStr)
		if err != nil {
			http.Error(w, "invalid uuid", http.StatusBadRequest)
			return
		}

		if err := eng.CancelRun(r.Context(), runID); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{"status": "cancelled"})
	})

	return r
}
