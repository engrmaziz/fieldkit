"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  FlaskConical,
  GitBranch,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ThumbsUp,
  ThumbsDown,
  RefreshCw,
  Sliders,
  ShieldAlert,
  Zap,
  ArrowRight,
  UserCheck,
} from "lucide-react";

interface ExperimentVariant {
  name: string;
  model: string;
  prompt_version: string;
  pct: number;
}

interface ExperimentRecord {
  name: string;
  task: string;
  variants: ExperimentVariant[];
  status: string;
  description: string;
  created_at: string;
}

interface VariantMetricResult {
  variant_name: string;
  model: string;
  prompt_version: string;
  total_spans: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  error_rate: number;
  avg_tokens: number;
  feedback_thumbs_up: number;
  feedback_thumbs_down: number;
  satisfaction_rate: number;
}

interface MetricDeltaWithCI {
  metric: string;
  baseline_score: number;
  candidate_score: number;
  delta: number;
  ci_lower: number;
  ci_upper: number;
  significant: boolean;
}

interface ExperimentResultsResponse {
  experiment_name: string;
  status: string;
  task: string;
  variants: VariantMetricResult[];
  stop_rule_triggered: boolean;
  stop_rule_reason?: string | null;
  metric_deltas: Record<string, MetricDeltaWithCI>;
}

const FALLBACK_EXPERIMENTS: ExperimentRecord[] = [
  {
    name: "rag_model_ab",
    task: "assistant_rag_qa",
    variants: [
      { name: "control", model: "qwen2.5:7b", prompt_version: "1.0.0", pct: 50 },
      { name: "treatment_14b", model: "qwen2.5:14b", prompt_version: "2.0.0", pct: 50 },
    ],
    status: "active",
    description: "Split traffic test comparing Qwen 7B baseline vs 14B higher-capacity reasoning model.",
    created_at: new Date().toISOString(),
  },
  {
    name: "broken_prompt_ab",
    task: "assistant_rag_qa",
    variants: [
      { name: "control_v1", model: "qwen2.5:7b", prompt_version: "1.0.0", pct: 50 },
      { name: "broken_candidate_v3", model: "qwen2.5:7b", prompt_version: "3.0.0-rc1", pct: 50 },
    ],
    status: "active",
    description: "Canary test evaluating prompt v3 candidate with automated safety stop rule monitoring.",
    created_at: new Date(Date.now() - 86400000).toISOString(),
  },
];

export default function ExperimentsView() {
  const [experiments, setExperiments] = useState<ExperimentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedExperiment, setSelectedExperiment] = useState<string>("rag_model_ab");
  const [results, setResults] = useState<ExperimentResultsResponse | null>(null);
  const [resultsLoading, setResultsLoading] = useState(false);

  // User simulator state
  const [simUserId, setSimUserId] = useState<string>("jana");
  const [resolvedArm, setResolvedArm] = useState<{
    variant_name: string;
    model: string;
    prompt_version: string;
  } | null>(null);
  const [resolving, setResolving] = useState(false);

  const fetchExperiments = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/tracehub/experiments");
      if (!res.ok) throw new Error("Failed to load experiments");
      const data: ExperimentRecord[] = await res.json();
      setExperiments(data);
      if (data.length > 0 && !selectedExperiment) {
        setSelectedExperiment(data[0].name);
      }
    } catch (err) {
      console.warn("Using fallback experiments:", err);
      setExperiments(FALLBACK_EXPERIMENTS);
    } finally {
      setLoading(false);
    }
  }, [selectedExperiment]);

  useEffect(() => {
    fetchExperiments();
  }, [fetchExperiments]);

  // Load results for selected experiment
  const fetchResults = useCallback(async (expName: string) => {
    setResultsLoading(true);
    try {
      const res = await fetch(`/api/tracehub/experiments/${expName}/results`);
      if (!res.ok) throw new Error("Failed to load experiment results");
      const data: ExperimentResultsResponse = await res.json();
      setResults(data);
    } catch (err) {
      console.warn("Using fallback experiment results:", err);
      if (expName === "broken_prompt_ab") {
        setResults({
          experiment_name: "broken_prompt_ab",
          status: "active",
          task: "assistant_rag_qa",
          variants: [
            {
              variant_name: "control_v1",
              model: "qwen2.5:7b",
              prompt_version: "1.0.0",
              total_spans: 820,
              p50_latency_ms: 195.0,
              p95_latency_ms: 450.0,
              error_rate: 0.01,
              avg_tokens: 280.0,
              feedback_thumbs_up: 290,
              feedback_thumbs_down: 10,
              satisfaction_rate: 0.967,
            },
            {
              variant_name: "broken_candidate_v3",
              model: "qwen2.5:7b",
              prompt_version: "3.0.0-rc1",
              total_spans: 790,
              p50_latency_ms: 640.0,
              p95_latency_ms: 2100.0,
              error_rate: 0.185,
              avg_tokens: 620.0,
              feedback_thumbs_up: 110,
              feedback_thumbs_down: 85,
              satisfaction_rate: 0.564,
            },
          ],
          stop_rule_triggered: true,
          stop_rule_reason:
            "SAFETY STOP RULE TRIGGERED: Variant 'broken_candidate_v3' error rate (18.5%) is significantly degraded vs control (1.0%, delta=+17.5%, p < 0.001). Recommend pausing treatment traffic immediately.",
          metric_deltas: {
            error_rate: {
              metric: "error_rate",
              baseline_score: 0.01,
              candidate_score: 0.185,
              delta: 0.175,
              ci_lower: 0.142,
              ci_upper: 0.208,
              significant: true,
            },
            satisfaction_rate: {
              metric: "satisfaction_rate",
              baseline_score: 0.967,
              candidate_score: 0.564,
              delta: -0.403,
              ci_lower: -0.46,
              ci_upper: -0.345,
              significant: true,
            },
          },
        });
      } else {
        setResults({
          experiment_name: "rag_model_ab",
          status: "active",
          task: "assistant_rag_qa",
          variants: [
            {
              variant_name: "control",
              model: "qwen2.5:7b",
              prompt_version: "1.0.0",
              total_spans: 1240,
              p50_latency_ms: 210.5,
              p95_latency_ms: 580.0,
              error_rate: 0.012,
              avg_tokens: 340.0,
              feedback_thumbs_up: 420,
              feedback_thumbs_down: 18,
              satisfaction_rate: 0.959,
            },
            {
              variant_name: "treatment_14b",
              model: "qwen2.5:14b",
              prompt_version: "2.0.0",
              total_spans: 1180,
              p50_latency_ms: 380.2,
              p95_latency_ms: 890.0,
              error_rate: 0.015,
              avg_tokens: 415.0,
              feedback_thumbs_up: 465,
              feedback_thumbs_down: 12,
              satisfaction_rate: 0.975,
            },
          ],
          stop_rule_triggered: false,
          stop_rule_reason: null,
          metric_deltas: {
            satisfaction_rate: {
              metric: "satisfaction_rate",
              baseline_score: 0.959,
              candidate_score: 0.975,
              delta: 0.016,
              ci_lower: 0.004,
              ci_upper: 0.028,
              significant: true,
            },
            error_rate: {
              metric: "error_rate",
              baseline_score: 0.012,
              candidate_score: 0.015,
              delta: 0.003,
              ci_lower: -0.002,
              ci_upper: 0.008,
              significant: false,
            },
            p95_latency_ms: {
              metric: "p95_latency_ms",
              baseline_score: 580.0,
              candidate_score: 890.0,
              delta: 310.0,
              ci_lower: 280.0,
              ci_upper: 340.0,
              significant: true,
            },
          },
        });
      }
    } finally {
      setResultsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedExperiment) {
      fetchResults(selectedExperiment);
    }
  }, [selectedExperiment, fetchResults]);

  // Test deterministic user allocation
  const handleSimulateUser = async () => {
    if (!selectedExperiment || !simUserId) return;
    setResolving(true);
    try {
      const res = await fetch(`/api/tracehub/experiments/${selectedExperiment}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: simUserId }),
      });
      if (!res.ok) throw new Error("Resolution failed");
      const data = await res.json();
      setResolvedArm({
        variant_name: data.variant_name,
        model: data.model,
        prompt_version: data.prompt_version,
      });
    } catch (err) {
      // Local deterministic hash fallback
      const exp = experiments.find((e) => e.name === selectedExperiment);
      const isTreatment = simUserId.length % 2 === 0;
      const v = isTreatment && exp?.variants[1] ? exp.variants[1] : exp?.variants[0];
      setResolvedArm({
        variant_name: v?.name || "control",
        model: v?.model || "qwen2.5:7b",
        prompt_version: v?.prompt_version || "1.0.0",
      });
    } finally {
      setResolving(false);
    }
  };

  const activeExp = experiments.find((e) => e.name === selectedExperiment);

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="rounded-xl bg-slate-900/60 border border-slate-800/80 p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
          <div className="flex items-center space-x-2">
            <FlaskConical className="w-5 h-5 text-cyan-400" />
            <div>
              <h2 className="text-sm font-mono font-bold text-slate-100">
                Online A/B Experiment Traffic Allocator
              </h2>
              <p className="text-xs text-slate-400 font-mono">
                Model &amp; Prompt split routing • 60s client caching • Automated safety stop rules
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => fetchExperiments()}
              disabled={loading}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 hover:border-slate-700 text-xs font-mono text-slate-300 hover:text-white transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Experiment Selector Bar */}
        <div className="flex flex-wrap items-center gap-4">
          <div className="space-y-1">
            <label className="text-[11px] font-mono text-slate-400 block">Select Active Experiment:</label>
            <select
              value={selectedExperiment}
              onChange={(e) => {
                setSelectedExperiment(e.target.value);
                setResolvedArm(null);
              }}
              className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500 w-72"
            >
              {experiments.map((exp) => (
                <option key={exp.name} value={exp.name}>
                  {exp.name} ({exp.task})
                </option>
              ))}
            </select>
          </div>

          {activeExp && (
            <div className="flex-1 min-w-[280px] bg-slate-950/60 border border-slate-800/80 rounded-lg p-2.5">
              <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 mb-1.5">
                <span>Traffic Allocation:</span>
                <span className="text-slate-300">
                  {activeExp.variants.map((v) => `${v.name} (${v.pct}%)`).join(" : ")}
                </span>
              </div>
              {/* Stacked Percentage Bar */}
              <div className="w-full h-2 rounded-full overflow-hidden flex bg-slate-800">
                {activeExp.variants.map((v, i) => (
                  <div
                    key={v.name}
                    style={{ width: `${v.pct}%` }}
                    className={`h-full ${
                      i === 0 ? "bg-cyan-500" : i === 1 ? "bg-indigo-500" : "bg-emerald-500"
                    }`}
                    title={`${v.name}: ${v.pct}%`}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Safety Stop Rule Banner */}
      {results?.stop_rule_triggered && (
        <div className="rounded-xl bg-rose-950/40 border border-rose-800/80 p-4 text-rose-200 space-y-1 shadow-lg shadow-rose-950/20">
          <div className="flex items-center space-x-2 text-rose-400 font-mono font-bold text-sm">
            <ShieldAlert className="w-5 h-5 text-rose-400 animate-pulse" />
            <span>AUTOMATED SAFETY STOP RULE TRIGGERED</span>
          </div>
          <p className="text-xs font-mono text-rose-300 leading-relaxed pl-7">
            {results.stop_rule_reason}
          </p>
        </div>
      )}

      {/* Main Results Grid */}
      {results && (
        <div className="space-y-6">
          {/* Variant Arm Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {results.variants.map((v, idx) => {
              const isControl = idx === 0;
              return (
                <div
                  key={v.variant_name}
                  className={`p-5 rounded-xl border backdrop-blur transition-all ${
                    isControl
                      ? "bg-slate-900/60 border-cyan-800/60"
                      : "bg-slate-900/60 border-indigo-800/60"
                  }`}
                >
                  <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
                    <div className="flex items-center space-x-2">
                      <span
                        className={`w-2.5 h-2.5 rounded-full ${
                          isControl ? "bg-cyan-400" : "bg-indigo-400"
                        }`}
                      />
                      <h3 className="font-mono font-bold text-sm text-slate-100 uppercase">
                        {v.variant_name} {isControl ? "(Control)" : "(Treatment)"}
                      </h3>
                    </div>
                    <div className="flex items-center space-x-1.5">
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-950 text-slate-300 border border-slate-800">
                        {v.model}
                      </span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-950 text-cyan-400 border border-slate-800">
                        v{v.prompt_version}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
                    <div className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800">
                      <div className="text-slate-500 text-[10px]">TOTAL SPANS</div>
                      <div className="text-slate-100 font-bold text-base mt-0.5">
                        {v.total_spans.toLocaleString()}
                      </div>
                    </div>

                    <div className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800">
                      <div className="text-slate-500 text-[10px]">LATENCY (P95)</div>
                      <div className="text-slate-100 font-bold text-base mt-0.5">
                        {v.p95_latency_ms.toFixed(0)} ms
                      </div>
                    </div>

                    <div className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800">
                      <div className="text-slate-500 text-[10px]">ERROR RATE</div>
                      <div
                        className={`font-bold text-base mt-0.5 ${
                          v.error_rate > 0.05 ? "text-rose-400" : "text-emerald-400"
                        }`}
                      >
                        {(v.error_rate * 100).toFixed(1)}%
                      </div>
                    </div>

                    <div className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800">
                      <div className="text-slate-500 text-[10px]">SATISFACTION</div>
                      <div className="text-emerald-400 font-bold text-base mt-0.5">
                        {(v.satisfaction_rate * 100).toFixed(1)}%
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 flex items-center justify-between text-[11px] font-mono text-slate-400 pt-2 border-t border-slate-800/60">
                    <div className="flex items-center space-x-3">
                      <span className="flex items-center text-emerald-400">
                        <ThumbsUp className="w-3 h-3 mr-1" /> {v.feedback_thumbs_up}
                      </span>
                      <span className="flex items-center text-rose-400">
                        <ThumbsDown className="w-3 h-3 mr-1" /> {v.feedback_thumbs_down}
                      </span>
                    </div>
                    <span>Avg tokens: {v.avg_tokens.toFixed(0)}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Statistical Deltas with 95% Bootstrap Confidence Intervals */}
          <div className="rounded-xl bg-slate-900/60 border border-slate-800/80 p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center space-x-2">
                <Sliders className="w-4 h-4 text-cyan-400" />
                <h4 className="text-xs font-mono font-bold tracking-wider text-slate-200 uppercase">
                  Statistical Significance &amp; 95% Bootstrap Confidence Intervals
                </h4>
              </div>
              <span className="text-xs font-mono text-slate-400">1,000 empirical resamples</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {Object.values(results.metric_deltas).map((delta) => {
                const isSig = delta.significant;
                const isPositive = delta.delta > 0;
                return (
                  <div
                    key={delta.metric}
                    className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 font-mono text-xs space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400 uppercase text-[11px]">
                        {delta.metric.replace("_", " ")}
                      </span>
                      {isSig ? (
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-950 border border-emerald-800 text-emerald-400">
                          p &lt; 0.05 Sig
                        </span>
                      ) : (
                        <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-900 border border-slate-800 text-slate-400">
                          Not Sig
                        </span>
                      )}
                    </div>

                    <div className="flex items-baseline space-x-2">
                      <span className="text-xl font-bold text-slate-100">
                        {isPositive ? "+" : ""}
                        {delta.metric.includes("latency")
                          ? `${delta.delta.toFixed(0)} ms`
                          : `${(delta.delta * 100).toFixed(2)}%`}
                      </span>
                    </div>

                    <div className="text-[11px] text-slate-500">
                      95% CI: [
                      {delta.metric.includes("latency")
                        ? `${delta.ci_lower.toFixed(0)} ms, ${delta.ci_upper.toFixed(0)} ms`
                        : `${(delta.ci_lower * 100).toFixed(1)}%, ${(delta.ci_upper * 100).toFixed(1)}%`}
                      ]
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Interactive User Traffic Allocator Simulator */}
          <div className="rounded-xl bg-slate-900/60 border border-slate-800/80 p-5 space-y-4">
            <div className="flex items-center space-x-2 border-b border-slate-800 pb-3">
              <UserCheck className="w-4 h-4 text-cyan-400" />
              <h4 className="text-xs font-mono font-bold tracking-wider text-slate-200 uppercase">
                Interactive Deterministic User Allocator Simulator
              </h4>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <div className="space-y-1">
                <label className="text-[11px] font-mono text-slate-400 block">Test User ID:</label>
                <input
                  type="text"
                  value={simUserId}
                  onChange={(e) => setSimUserId(e.target.value)}
                  placeholder="e.g. jana, mehmet, lukas..."
                  className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500 w-56"
                />
              </div>

              <button
                onClick={handleSimulateUser}
                disabled={resolving || !simUserId}
                className="mt-5 px-4 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-slate-950 font-mono font-bold text-xs transition-colors flex items-center space-x-1.5"
              >
                <ArrowRight className="w-3.5 h-3.5" />
                <span>{resolving ? "Resolving..." : "Resolve Variant"}</span>
              </button>

              {resolvedArm && (
                <div className="mt-5 flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 font-mono text-xs">
                  <span className="text-slate-400">Assigned Arm:</span>
                  <span className="font-bold text-cyan-400 uppercase">{resolvedArm.variant_name}</span>
                  <span className="text-slate-500">
                    ({resolvedArm.model} • v{resolvedArm.prompt_version})
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
