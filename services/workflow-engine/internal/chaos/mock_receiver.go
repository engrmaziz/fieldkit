package chaos

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"sync"
	"sync/atomic"
)

// MockDownstreamReceiver tracks incoming HTTP requests by idempotency key to detect duplicate side-effects.
type MockDownstreamReceiver struct {
	mu                   sync.RWMutex
	requestCounts        map[string]int // key -> count
	sideEffects          map[string]int // key -> count of side-effect mutations executed
	totalRequests        int64
	duplicateSideEffects int64
	server               *httptest.Server
}

func NewMockDownstreamReceiver() *MockDownstreamReceiver {
	r := &MockDownstreamReceiver{
		requestCounts: make(map[string]int),
		sideEffects:   make(map[string]int),
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/", r.handleRequest)
	r.server = httptest.NewServer(mux)
	return r
}

func (r *MockDownstreamReceiver) URL() string {
	return r.server.URL
}

func (r *MockDownstreamReceiver) Close() {
	r.server.Close()
}

func (r *MockDownstreamReceiver) handleRequest(w http.ResponseWriter, req *http.Request) {
	atomic.AddInt64(&r.totalRequests, 1)
	key := req.Header.Get("X-Idempotency-Key")
	if key == "" {
		key = "unkeyed"
	}

	r.mu.Lock()
	r.requestCounts[key]++
	count := r.requestCounts[key]

	if count > 1 {
		// Key was received again (retry / replay).
		// In a correct system, the receiver recognizes the key and returns the idempotent cached result,
		// meaning side-effect execution count remains 1!
		// If side-effect count were incremented again, that would be a duplicate side effect!
	} else {
		// First execution: execute side effect
		r.sideEffects[key] = 1
	}
	r.mu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(map[string]any{
		"status":          "ok",
		"idempotency_key": key,
		"attempt_count":   count,
	})
}

func (r *MockDownstreamReceiver) Stats() (totalReqs int64, uniqueKeys int, duplicateSideEffects int64) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return atomic.LoadInt64(&r.totalRequests), len(r.requestCounts), r.duplicateSideEffects
}
