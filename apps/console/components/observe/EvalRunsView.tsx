"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  BarChart3,
  TrendingDown,
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  ArrowRight,
  ExternalLink,
  Layers,
  Sparkles,
  GitBranch,
  RefreshCw,
} from "lucide-react";

interface EvalRunSummary {
  run_id: string;
  suite: string;
  model: string;
  prompt_versions: Record<string, string>;
  git_sha: string;
  total_items: number;
  aggregates: Record<string, number>;
  timestamp: string;
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

interface ItemRegression {
  item_id: string;
  question: string;
  metric: string;
  baseline_score: number;
  candidate_score: number;
  delta: number;
  trace_id: string;
}

interface EvalComparisonResponse {
  baseline_id: string;
  candidate_id: string;
  suite: string;
  metric_deltas: Record<string, MetricDeltaWithCI>;
  regressions: ItemRegression[];
  improvements: ItemRegression[];
  total_items_compared: number;
  total_regressions: number;
  total_improvements: number;
  total_unchanged: number;
}

interface EvalRunsViewProps {
  onSelectTrace: (traceId: string) => void;
}

const FALLBACK_RUNS: EvalRunSummary[] = [
  {
    run_id: "run-p2-v2-candidate",
    suite: "assistant_rag",
    model: "qwen2.5:7b",
    prompt_versions: { rag_answer: "2.0.0" },
    git_sha: "e16320f",
    total_items: 4,
    aggregates: { faithfulness: 0.8875, citation_accuracy: 0.925 },
    timestamp: new Date().toISOString(),
  },
  {
    run_id: "run-p2-v1-baseline",
    suite: "assistant_rag",
    model: "qwen2.5:7b",
    prompt_versions: { rag_answer: "1.0.0" },
    git_sha: "1e0fd9b",
    total_items: 4,
    aggregates: { faithfulness: 0.875, citation_accuracy: 0.875 },
    timestamp: new Date(Date.now() - 86400000).toISOString(),
  },
];

export default function EvalRunsView({ onSelectTrace }: EvalRunsViewProps) {
  const [runs, setRuns] = useState<EvalRunSummary[]>([]);
  const [loading, setLoading] = useState(true);

  // Comparison state
  const [baselineId, setBaselineId] = useState<string>("run-p2-v1-baseline");
  const [candidateId, setCandidateId] = useState<string>("run-p2-v2-candidate");
  const [comparison, setComparison] = useState<EvalComparisonResponse | null>(null);
  const [comparing, setComparing] = useState(false);

  const fetchRuns = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/tracehub/eval-runs");
      if (!res.ok) throw new Error("Failed to load eval runs");
      const data: EvalRunSummary[] = await res.json();
      setRuns(data);
      if (data.length >= 2) {
        setBaselineId(data[1].run_id);
        setCandidateId(data[0].run_id);
      }
    } catch (err) {
      console.warn("Using fallback eval runs:", err);
      setRuns(FALLBACK_RUNS);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  // Run statistical comparison
  const handleCompare = async () => {
    if (!baselineId || !candidateId) return;
    setComparing(true);
    try {
      const res = await fetch(
        `/api/tracehub/eval-runs/compare?baseline_id=${baselineId}&candidate_id=${candidateId}`
      );
      if (!res.ok) throw new Error("Failed to compare runs");
      const data: EvalComparisonResponse = await res.json();
      setComparison(data);
    } catch (err) {
      console.warn("Using fallback comparison:", err);
      setComparison({
        baseline_id: baselineId,
        candidate_id: candidateId,
        suite: "assistant_rag",
        metric_deltas: {
          citation_accuracy: {
            metric: "citation_accuracy",
            baseline_score: 0.875,
            candidate_score: 0.925,
            delta: 0.05,
            ci_lower: 0.0125,
            ci_upper: 0.0875,
            significant: true,
          },
          faithfulness: {
            metric: "faithfulness",
            baseline_score: 0.875,
            candidate_score: 0.8875,
            delta: 0.0125,
            ci_lower: -0.025,
            ci_upper: 0.05,
            significant: false,
          },
        },
        regressions: [
          {
            item_id: "q-003",
            question: "What are the confidential supplier audit penalties?",
            metric: "faithfulness",
            baseline_score: 0.85,
            candidate_score: 0.7,
            delta: -0.15,
            trace_id: "trc-9c4e2a101f33",
          },
        ],
        improvements: [
          {
            item_id: "q-004",
            question: "Explain emergency stop protocol for CNC lathe spindles.",
            metric: "citation_accuracy",
            baseline_score: 0.7,
            candidate_score: 1.0,
            delta: 0.3,
            trace_id: "trc-1b2c3d4e5f60",
          },
        ],
        total_items_compared: 4,
        total_regressions: 1,
        total_improvements: 1,
        total_unchanged: 2,
      });
    } finally {
      setComparing(false);
    }
  };

  // Run initial comparison on mount
  useEffect(() => {
    if (baselineId && candidateId) {
      handleCompare();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-6">
      {/* Comparison Selector Header */}
      <div className="rounded-xl bg-slate-900/60 border border-slate-800/80 p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
          <div className="flex items-center space-x-2">
            <BarChart3 className="w-5 h-5 text-cyan-400" />
            <div>
              <h2 className="text-sm font-mono font-bold text-slate-100">
                Evaluation Runs &amp; Statistical Regression Gate
              </h2>
              <p className="text-xs text-slate-400 font-mono">
                Item-by-item alignment • 95% Bootstrap Confidence Intervals • Direct trace inspection
              </p>
            </div>
          </div>

          <button
            onClick={() => fetchRuns()}
            disabled={loading}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 hover:border-slate-700 text-xs font-mono text-slate-300 hover:text-white transition-colors self-start sm:self-auto"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh Runs</span>
          </button>
        </div>

        {/* Run Selectors */}
        <div className="flex flex-wrap items-center gap-4">
          <div className="space-y-1">
            <label className="text-[11px] font-mono text-slate-400 block">Baseline Evaluation Run:</label>
            <select
              value={baselineId}
              onChange={(e) => setBaselineId(e.target.value)}
              className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500 w-64"
            >
              {runs.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id} ({r.model})
                </option>
              ))}
            </select>
          </div>

          <ArrowRight className="w-4 h-4 text-slate-600 hidden sm:block mt-5" />

          <div className="space-y-1">
            <label className="text-[11px] font-mono text-slate-400 block">Candidate Evaluation Run:</label>
            <select
              value={candidateId}
              onChange={(e) => setCandidateId(e.target.value)}
              className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500 w-64"
            >
              {runs.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id} ({r.model})
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleCompare}
            disabled={comparing || !baselineId || !candidateId}
            className="mt-5 px-4 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-slate-950 font-mono font-bold text-xs transition-colors flex items-center space-x-1.5"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>{comparing ? "Comparing..." : "Compare Runs"}</span>
          </button>
        </div>
      </div>

      {/* Comparison Results */}
      {comparison && (
        <div className="space-y-6">
          {/* Metric Delta Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {Object.values(comparison.metric_deltas).map((delta) => {
              const isPositive = delta.delta > 0;
              const isNegative = delta.delta < 0;
              return (
                <div
                  key={delta.metric}
                  className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur"
                >
                  <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-1">
                    <span className="uppercase">{delta.metric.replace("_", " ")}</span>
                    {delta.significant ? (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-950 border border-emerald-700 text-emerald-400">
                        p &lt; 0.05 Sig
                      </span>
                    ) : (
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 border border-slate-700">
                        No Sig Delta
                      </span>
                    )}
                  </div>

                  <div className="flex items-baseline space-x-2 mt-2">
                    <span className="text-2xl font-bold font-mono text-slate-100">
                      {(delta.candidate_score * 100).toFixed(1)}%
                    </span>
                    <span
                      className={`text-xs font-mono font-bold ${
                        isPositive ? "text-emerald-400" : isNegative ? "text-rose-400" : "text-slate-400"
                      }`}
                    >
                      {isPositive ? "+" : ""}
                      {(delta.delta * 100).toFixed(2)}%
                    </span>
                  </div>

                  <div className="text-[11px] font-mono text-slate-500 mt-2 flex justify-between">
                    <span>Base: {(delta.baseline_score * 100).toFixed(1)}%</span>
                    <span>
                      95% CI: [{(delta.ci_lower * 100).toFixed(1)}%, {(delta.ci_upper * 100).toFixed(1)}%]
                    </span>
                  </div>
                </div>
              );
            })}

            {/* Total Regressions Card */}
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur">
              <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-1">
                <span>REGRESSIONS ISOLATED</span>
                <TrendingDown className="w-4 h-4 text-rose-400" />
              </div>
              <div className="text-2xl font-bold font-mono text-rose-400">
                {comparison.total_regressions}
              </div>
              <div className="text-[11px] font-mono text-slate-500 mt-1">
                Out of {comparison.total_items_compared} aligned benchmark items
              </div>
            </div>

            {/* Total Improvements Card */}
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur">
              <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-1">
                <span>IMPROVEMENTS</span>
                <TrendingUp className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="text-2xl font-bold font-mono text-emerald-400">
                {comparison.total_improvements}
              </div>
              <div className="text-[11px] font-mono text-slate-500 mt-1">
                {comparison.total_unchanged} items unchanged
              </div>
            </div>
          </div>

          {/* Item Regression Drilldown Table */}
          <div className="rounded-xl bg-slate-900/60 border border-slate-800/80 overflow-hidden shadow-lg">
            <div className="p-4 bg-slate-950/70 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 text-rose-400" />
                <h3 className="text-xs font-mono font-bold tracking-wider text-slate-200 uppercase">
                  Item Regressions (Candidate &lt; Baseline)
                </h3>
              </div>
              <span className="text-xs font-mono text-slate-400">
                {comparison.regressions.length} item(s) dropped score
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-950 text-slate-400">
                    <th className="py-2.5 px-4 font-semibold">ITEM ID</th>
                    <th className="py-2.5 px-4 font-semibold">QUESTION / BENCHMARK PROMPT</th>
                    <th className="py-2.5 px-4 font-semibold">METRIC</th>
                    <th className="py-2.5 px-4 font-semibold">BASELINE</th>
                    <th className="py-2.5 px-4 font-semibold">CANDIDATE</th>
                    <th className="py-2.5 px-4 font-semibold">DELTA</th>
                    <th className="py-2.5 px-4 text-right font-semibold">TRACE LINK</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {comparison.regressions.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-6 text-center text-slate-500 font-mono">
                        Zero regressions detected! Candidate maintains or exceeds baseline scores.
                      </td>
                    </tr>
                  ) : (
                    comparison.regressions.map((reg) => (
                      <tr key={`${reg.item_id}-${reg.metric}`} className="hover:bg-slate-800/30">
                        <td className="py-3 px-4 font-bold text-slate-200">{reg.item_id}</td>
                        <td className="py-3 px-4 text-slate-300 max-w-md truncate" title={reg.question}>
                          {reg.question}
                        </td>
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                            {reg.metric}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-400">{reg.baseline_score.toFixed(2)}</td>
                        <td className="py-3 px-4 text-rose-300 font-bold">{reg.candidate_score.toFixed(2)}</td>
                        <td className="py-3 px-4 font-bold text-rose-400">
                          {reg.delta > 0 ? "+" : ""}
                          {reg.delta.toFixed(3)}
                        </td>
                        <td className="py-3 px-4 text-right">
                          {reg.trace_id ? (
                            <button
                              onClick={() => onSelectTrace(reg.trace_id)}
                              className="inline-flex items-center space-x-1 px-2 py-1 rounded bg-slate-950 border border-slate-800 hover:border-cyan-500 hover:text-cyan-400 text-slate-300 text-[11px] font-mono transition-colors"
                            >
                              <span>{reg.trace_id}</span>
                              <ExternalLink className="w-3 h-3" />
                            </button>
                          ) : (
                            <span className="text-slate-600">—</span>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Item Improvements Table */}
          {comparison.improvements.length > 0 && (
            <div className="rounded-xl bg-slate-900/60 border border-slate-800/80 overflow-hidden shadow-lg">
              <div className="p-4 bg-slate-950/70 border-b border-slate-800 flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-xs font-mono font-bold tracking-wider text-slate-200 uppercase">
                    Item Improvements (Candidate &gt; Baseline)
                  </h3>
                </div>
                <span className="text-xs font-mono text-slate-400">
                  {comparison.improvements.length} item(s) gained score
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="border-b border-slate-800 bg-slate-950 text-slate-400">
                      <th className="py-2.5 px-4 font-semibold">ITEM ID</th>
                      <th className="py-2.5 px-4 font-semibold">QUESTION / BENCHMARK PROMPT</th>
                      <th className="py-2.5 px-4 font-semibold">METRIC</th>
                      <th className="py-2.5 px-4 font-semibold">BASELINE</th>
                      <th className="py-2.5 px-4 font-semibold">CANDIDATE</th>
                      <th className="py-2.5 px-4 font-semibold">DELTA</th>
                      <th className="py-2.5 px-4 text-right font-semibold">TRACE LINK</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/50">
                    {comparison.improvements.map((imp) => (
                      <tr key={`${imp.item_id}-${imp.metric}`} className="hover:bg-slate-800/30">
                        <td className="py-3 px-4 font-bold text-slate-200">{imp.item_id}</td>
                        <td className="py-3 px-4 text-slate-300 max-w-md truncate" title={imp.question}>
                          {imp.question}
                        </td>
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                            {imp.metric}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-400">{imp.baseline_score.toFixed(2)}</td>
                        <td className="py-3 px-4 text-emerald-300 font-bold">{imp.candidate_score.toFixed(2)}</td>
                        <td className="py-3 px-4 font-bold text-emerald-400">
                          +{imp.delta.toFixed(3)}
                        </td>
                        <td className="py-3 px-4 text-right">
                          {imp.trace_id ? (
                            <button
                              onClick={() => onSelectTrace(imp.trace_id)}
                              className="inline-flex items-center space-x-1 px-2 py-1 rounded bg-slate-950 border border-slate-800 hover:border-cyan-500 hover:text-cyan-400 text-slate-300 text-[11px] font-mono transition-colors"
                            >
                              <span>{imp.trace_id}</span>
                              <ExternalLink className="w-3 h-3" />
                            </button>
                          ) : (
                            <span className="text-slate-600">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
