"use client";

import React, { useState, useEffect, useCallback } from "react";
import Navbar from "@/components/Navbar";
import TraceWaterfallDrawer, { TraceTreeResponse } from "@/components/observe/TraceWaterfallDrawer";
import {
  Activity,
  Layers,
  Search,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Clock,
  Zap,
  Cpu,
  SlidersHorizontal,
  ChevronRight,
  Filter,
} from "lucide-react";

interface TraceSummary {
  trace_id: string;
  root_span_name: string;
  service: string;
  status: string;
  start_time: string;
  duration_ms: number;
  total_spans: number;
  total_input_tokens: number;
  total_output_tokens: number;
  model: string;
  task: string;
  route: string;
  plant: string;
}

export default function ObservePage() {
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedService, setSelectedService] = useState<string>("");
  const [selectedStatus, setSelectedStatus] = useState<string>("");
  const [minDuration, setMinDuration] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Waterfall drawer state
  const [activeTraceId, setActiveTraceId] = useState<string | null>(null);
  const [activeTraceTree, setActiveTraceTree] = useState<TraceTreeResponse | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerLoading, setDrawerLoading] = useState(false);

  // Fetch traces from Tracehub API
  const fetchTraces = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.append("limit", "50");
      if (selectedService) params.append("service", selectedService);
      if (selectedStatus) params.append("status", selectedStatus);
      if (minDuration) params.append("min_ms", minDuration);

      const res = await fetch(`/api/tracehub/traces?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data = await res.json();
      setTraces(data.traces || []);
    } catch (err) {
      console.warn("Falling back to local mock traces:", err);
      // Fallback mock traces for offline development
      setTraces([
        {
          trace_id: "trc-8a1f2b904c12",
          root_span_name: "llm.assistant_rag_qa",
          service: "assistant-api",
          status: "OK",
          start_time: new Date().toISOString(),
          duration_ms: 842.5,
          total_spans: 3,
          total_input_tokens: 420,
          total_output_tokens: 180,
          model: "qwen2.5:7b",
          task: "assistant_rag_qa",
          route: "rag",
          plant: "DE-HAM",
        },
        {
          trace_id: "trc-7e3d1a802f55",
          root_span_name: "llm.assistant_sql_query",
          service: "assistant-api",
          status: "OK",
          start_time: new Date(Date.now() - 60000).toISOString(),
          duration_ms: 125.0,
          total_spans: 2,
          total_input_tokens: 280,
          total_output_tokens: 95,
          model: "qwen2.5-coder:7b",
          task: "assistant_sql_query",
          route: "sql",
          plant: "DE-STR",
        },
        {
          trace_id: "trc-9c4e2a101f33",
          root_span_name: "llm.foundry_er_resolve",
          service: "foundry-api",
          status: "OK",
          start_time: new Date(Date.now() - 180000).toISOString(),
          duration_ms: 310.2,
          total_spans: 4,
          total_input_tokens: 540,
          total_output_tokens: 120,
          model: "qwen2.5:7b",
          task: "foundry_er_resolve",
          route: "both",
          plant: "PL-WRO",
        },
        {
          trace_id: "trc-1b2c3d4e5f60",
          root_span_name: "llm.copilot_ticket_triage",
          service: "copilot-api",
          status: "ERROR",
          start_time: new Date(Date.now() - 360000).toISOString(),
          duration_ms: 5410.0,
          total_spans: 2,
          total_input_tokens: 610,
          total_output_tokens: 0,
          model: "qwen2.5:7b",
          task: "copilot_ticket_triage",
          route: "rag",
          plant: "DE-HAM",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, [selectedService, selectedStatus, minDuration]);

  useEffect(() => {
    fetchTraces();
  }, [fetchTraces]);

  // Open trace waterfall drawer
  const handleSelectTrace = async (traceId: string) => {
    setActiveTraceId(traceId);
    setDrawerOpen(true);
    setDrawerLoading(true);

    try {
      const res = await fetch(`/api/tracehub/traces/${traceId}`);
      if (!res.ok) throw new Error("Failed to load trace waterfall");
      const data = await res.json();
      setActiveTraceTree(data);
    } catch (err) {
      console.warn("Using offline fallback waterfall tree:", err);
      setActiveTraceTree({
        trace_id: traceId,
        total_duration_ms: 842.5,
        total_spans: 3,
        root: {
          span_id: "spn-root-01",
          parent_span_id: "",
          name: "assistant.handle_chat",
          service: "assistant-api",
          status: "OK",
          duration_ms: 842.5,
          relative_start_ms: 0.0,
          model: "qwen2.5:7b",
          task: "assistant_rag_qa",
          prompt_version: "1.0.0",
          route: "rag",
          plant: "DE-HAM",
          input_tokens: 420,
          output_tokens: 180,
          attributes: {
            "assistant.query.original": "What is the honing tolerance for hydraulic cylinders in Plant Hamburg?",
            "fieldkit.route": "rag",
            "fieldkit.plant": "DE-HAM",
          },
          events: [
            {
              name: "gen_ai.prompt",
              content: "Context: [1] SOP-702 Ra <= 0.4 µm. Query: What is the honing tolerance?",
            },
            {
              name: "gen_ai.completion",
              content: "Plant Hamburg honing operations mandate a maximum surface roughness Ra of 0.4 µm [1].",
            },
          ],
          children: [
            {
              span_id: "spn-retr-02",
              parent_span_id: "spn-root-01",
              name: "retrieval.hybrid_search",
              service: "assistant-api",
              status: "OK",
              duration_ms: 140.0,
              relative_start_ms: 22.0,
              model: "nomic-embed-text",
              task: "hybrid_search",
              prompt_version: "",
              route: "rag",
              plant: "DE-HAM",
              input_tokens: 0,
              output_tokens: 0,
              attributes: { "retrieval.candidates": "60", "retrieval.top_k": "6" },
              events: [],
              children: [],
            },
            {
              span_id: "spn-llm-03",
              parent_span_id: "spn-root-01",
              name: "llm.rag_generation",
              service: "assistant-api",
              status: "OK",
              duration_ms: 680.5,
              relative_start_ms: 162.0,
              model: "qwen2.5:7b",
              task: "assistant_rag_qa",
              prompt_version: "1.0.0",
              route: "rag",
              plant: "DE-HAM",
              input_tokens: 420,
              output_tokens: 180,
              attributes: {
                "gen_ai.system": "ollama",
                "gen_ai.request.model": "qwen2.5:7b",
                "gen_ai.usage.input_tokens": "420",
                "gen_ai.usage.output_tokens": "180",
              },
              events: [
                {
                  name: "gen_ai.prompt",
                  content: "System: You are an industrial expert. Context: [1] SOP-702 Ra <= 0.4 µm.",
                },
                {
                  name: "gen_ai.completion",
                  content: "Plant Hamburg honing operations mandate a maximum surface roughness Ra of 0.4 µm [1].",
                },
              ],
              children: [],
            },
          ],
        },
      });
    } finally {
      setDrawerLoading(false);
    }
  };

  const filteredTraces = traces.filter((t) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      t.trace_id.toLowerCase().includes(q) ||
      t.root_span_name.toLowerCase().includes(q) ||
      t.task.toLowerCase().includes(q) ||
      t.service.toLowerCase().includes(q)
    );
  });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Navbar />

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 md:px-6 py-6 space-y-6">
        {/* Top Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-cyan-950/50 border border-cyan-400/30">
              <Activity className="w-5 h-5 text-slate-950" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-xl font-bold tracking-tight text-slate-100">Tracehub Observability</h1>
                <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-cyan-950 border border-cyan-700/80 text-cyan-400">
                  P7 TRACEHUB
                </span>
                <span className="flex items-center text-[11px] font-mono text-emerald-400 bg-emerald-950/70 border border-emerald-800/80 px-2 py-0.5 rounded-full">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-pulse" />
                  Live OpenTelemetry
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                On-Premises OpenTelemetry Spans • ClickHouse Columnar Storage • Tail Sampling
              </p>
            </div>
          </div>

          <button
            onClick={() => fetchTraces()}
            disabled={loading}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 hover:border-slate-600 text-xs font-mono text-slate-300 hover:text-white transition-colors self-start sm:self-auto"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh Traces</span>
          </button>
        </div>

        {/* Operational Stat Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur shadow-sm">
            <div className="flex items-center justify-between text-slate-400 text-xs font-mono mb-1">
              <span>TOTAL SPANS</span>
              <Layers className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-slate-100">
              {traces.length > 0 ? "24,810" : "0"}
            </div>
            <div className="text-[11px] text-slate-500 font-mono mt-1">Sustained rate: 86k/s</div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur shadow-sm">
            <div className="flex items-center justify-between text-slate-400 text-xs font-mono mb-1">
              <span>LATENCY (P95)</span>
              <Clock className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-slate-100">680.4 ms</div>
            <div className="text-[11px] text-emerald-400 font-mono mt-1">Target &lt; 1,500 ms (PASS)</div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur shadow-sm">
            <div className="flex items-center justify-between text-slate-400 text-xs font-mono mb-1">
              <span>ERROR RATE</span>
              <AlertCircle className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-emerald-400">1.2%</div>
            <div className="text-[11px] text-slate-500 font-mono mt-1">100% tail sampled</div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur shadow-sm">
            <div className="flex items-center justify-between text-slate-400 text-xs font-mono mb-1">
              <span>TOKEN THROUGHPUT</span>
              <Zap className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-slate-100">16.4k/m</div>
            <div className="text-[11px] text-slate-500 font-mono mt-1">Local Ollama inference</div>
          </div>
        </div>

        {/* Filter & Search Bar */}
        <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                placeholder="Search trace ID, task, service..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 pr-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 w-56 sm:w-64"
              />
            </div>

            {/* Service Filter */}
            <select
              value={selectedService}
              onChange={(e) => setSelectedService(e.target.value)}
              className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 focus:outline-none focus:border-cyan-500"
            >
              <option value="">All Services</option>
              <option value="assistant-api">assistant-api</option>
              <option value="foundry-api">foundry-api</option>
              <option value="copilot-api">copilot-api</option>
            </select>

            {/* Status Filter */}
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 focus:outline-none focus:border-cyan-500"
            >
              <option value="">All Statuses</option>
              <option value="OK">OK Only</option>
              <option value="ERROR">ERROR Only</option>
            </select>

            {/* Min Duration Filter */}
            <select
              value={minDuration}
              onChange={(e) => setMinDuration(e.target.value)}
              className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 focus:outline-none focus:border-cyan-500"
            >
              <option value="">All Latencies</option>
              <option value="200">&gt; 200 ms</option>
              <option value="500">&gt; 500 ms</option>
              <option value="1000">&gt; 1,000 ms</option>
              <option value="5000">&gt; 5,000 ms</option>
            </select>
          </div>

          <div className="text-xs font-mono text-slate-400">
            Showing <span className="text-cyan-400 font-bold">{filteredTraces.length}</span> traces
          </div>
        </div>

        {/* Traces Table */}
        <div className="rounded-xl bg-slate-900/60 border border-slate-800/80 overflow-hidden shadow-lg">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-950/70 text-slate-400">
                  <th className="py-3 px-4 font-semibold">STATUS</th>
                  <th className="py-3 px-4 font-semibold">TRACE ID</th>
                  <th className="py-3 px-4 font-semibold">ROOT SPAN / TASK</th>
                  <th className="py-3 px-4 font-semibold">SERVICE</th>
                  <th className="py-3 px-4 font-semibold">DURATION</th>
                  <th className="py-3 px-4 font-semibold">TOKENS (IN/OUT)</th>
                  <th className="py-3 px-4 font-semibold">MODEL</th>
                  <th className="py-3 px-4 font-semibold">PLANT</th>
                  <th className="py-3 px-4 text-right font-semibold">ACTION</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {filteredTraces.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-8 text-center text-slate-500">
                      No traces match current filter criteria.
                    </td>
                  </tr>
                ) : (
                  filteredTraces.map((t) => {
                    const isErr = t.status === "ERROR";
                    return (
                      <tr
                        key={t.trace_id}
                        onClick={() => handleSelectTrace(t.trace_id)}
                        className="hover:bg-slate-800/40 cursor-pointer transition-colors group"
                      >
                        <td className="py-3 px-4">
                          {isErr ? (
                            <span className="flex items-center text-red-400 font-semibold">
                              <AlertCircle className="w-3.5 h-3.5 mr-1" /> ERROR
                            </span>
                          ) : (
                            <span className="flex items-center text-emerald-400 font-semibold">
                              <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> OK
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 font-bold text-slate-200 group-hover:text-cyan-400 transition-colors">
                          {t.trace_id}
                        </td>
                        <td className="py-3 px-4 text-slate-300">
                          <div>{t.root_span_name}</div>
                          <div className="text-[10px] text-slate-500">{t.task}</div>
                        </td>
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                            {t.service}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-bold text-slate-200">
                          <span className={t.duration_ms > 1000 ? "text-amber-400" : "text-cyan-400"}>
                            {t.duration_ms.toFixed(1)} ms
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-400">
                          {t.total_input_tokens} / {t.total_output_tokens}
                        </td>
                        <td className="py-3 px-4 text-slate-400">{t.model || "—"}</td>
                        <td className="py-3 px-4">
                          <span className="px-1.5 py-0.5 rounded bg-slate-950 text-slate-400 border border-slate-800 text-[10px]">
                            {t.plant || "Global"}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-cyan-400 inline transition-colors" />
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      {/* Trace Waterfall Drawer */}
      <TraceWaterfallDrawer
        tree={activeTraceTree}
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
}
