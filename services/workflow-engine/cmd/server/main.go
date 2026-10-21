package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"syscall"
	"time"

	"fieldkit/workflow-engine/internal/api"
	"fieldkit/workflow-engine/internal/engine"
	"fieldkit/workflow-engine/internal/executor"
	"fieldkit/workflow-engine/internal/parser"
	"fieldkit/workflow-engine/internal/storage"
)

func main() {
	// Configure structured JSON logging
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))
	slog.SetDefault(logger)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8008"
	}

	workerCount := 4
	if cStr := os.Getenv("WORKER_CONCURRENCY"); cStr != "" {
		if c, err := strconv.Atoi(cStr); err == nil && c > 0 {
			workerCount = c
		}
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Initialize Storage & Engine
	store := storage.NewMemoryStorage()
	exec := executor.NewDefaultExecutor()
	eng := engine.NewEngine(store, exec, workerCount)

	// Pre-load shipped workflows from workflows/ directory if present
	workflowsDir := os.Getenv("WORKFLOWS_DIR")
	if workflowsDir == "" {
		workflowsDir = "workflows"
	}
	if matches, err := filepath.Glob(filepath.Join(workflowsDir, "*.yaml")); err == nil {
		for _, file := range matches {
			if data, err := os.ReadFile(file); err == nil {
				if def, err := parser.ParseWorkflowYAML(data); err == nil {
					_ = store.SaveDefinition(ctx, def)
					slog.Info("registered workflow definition", "name", def.Name, "version", def.Version, "file", file)
				}
			}
		}
	}

	eng.Start(ctx)

	router := api.NewRouter(store, eng)
	server := &http.Server{
		Addr:         ":" + port,
		Handler:      router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	go func() {
		slog.Info("starting Fieldkit workflow engine HTTP server", "port", port)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("server fatal error", "error", err)
			os.Exit(1)
		}
	}()

	// Graceful shutdown on SIGINT / SIGTERM
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, os.Interrupt, syscall.SIGTERM)
	<-sigCh

	slog.Info("shutting down workflow engine server gracefully...")
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer shutdownCancel()

	eng.Stop()
	if err := server.Shutdown(shutdownCtx); err != nil {
		slog.Error("server forced to shutdown", "error", err)
	}
	slog.Info("workflow engine exited cleanly")
}
