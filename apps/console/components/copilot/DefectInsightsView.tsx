"use client";

import React, { useState } from "react";
import { DefectCluster } from "./types";
import {
  Sparkles,
  TrendingUp,
  AlertTriangle,
  Layers,
  Wrench,
  RefreshCw,
  ExternalLink,
  Tag,
  CheckCircle2,
  BellRing,
} from "lucide-react";

interface DefectInsightsViewProps {
  clusters: DefectCluster[];
  onRecluster: () => void;
  isScanning: boolean;
}

export default function DefectInsightsView({
  clusters,
  onRecluster,
  isScanning,
}: DefectInsightsViewProps) {
  const [selectedClusterId, setSelectedClusterId] = useState<number | null>(1);

  return (
    <div className="flex flex-col h-full bg-slate-900/60 border border-slate-800/80 rounded-xl overflow-hidden shadow-xl backdrop-blur-md">
      {/* Header */}
      <div className="p-4 border-b border-slate-800 bg-slate-950/60 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center space-x-2.5">
          <Sparkles className="w-4 h-4 text-cyan-400" />
          <h2 className="text-sm font-semibold tracking-wide text-slate-100 uppercase">
            Emerging Defect Clusters & Tracehub Alerts
          </h2>
          <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
            BERTopic / TF-IDF Engine Active
          </span>
        </div>

        <button
          onClick={onRecluster}
          disabled={isScanning}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-mono bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold transition-all disabled:opacity-50"
        >
          <RefreshCw
            className={`w-3.5 h-3.5 text-slate-950 ${isScanning ? "animate-spin" : ""}`}
          />
          <span>{isScanning ? "Re-clustering..." : "Run Topic Re-scan"}</span>
        </button>
      </div>

      {/* Main Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Top Summary Banner */}
        <div className="p-4 rounded-xl bg-gradient-to-r from-rose-950/40 via-amber-950/20 to-slate-950 border border-rose-800/40 text-xs space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 text-rose-300 font-bold font-mono">
              <TrendingUp className="w-4 h-4 text-rose-400" />
              <span>DEFECT ANOMALY DETECTED: +600% Surge in Valve Flange Leaks</span>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40 uppercase font-bold">
              CRITICAL SPIKE
            </span>
          </div>
          <p className="text-slate-300 leading-relaxed font-sans">
            Unsupervised topic clustering identified 14 defect tickets over the last 7 days regarding hydraulic valve <strong className="text-cyan-300">HX-400</strong> flange leakage (baseline: 2 tickets). Incident alert automatically emitted to Project 7 Tracehub anomaly queue.
          </p>
        </div>

        {/* Clusters Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {clusters.map((c) => {
            const isSelected = selectedClusterId === c.cluster_id;
            const isCritical = c.severity === "critical";
            const isWarning = c.severity === "warning";

            return (
              <div
                key={c.cluster_id}
                onClick={() => setSelectedClusterId(c.cluster_id)}
                className={`p-4 rounded-xl border text-left cursor-pointer transition-all space-y-3 ${
                  isSelected
                    ? "bg-slate-800/90 border-cyan-500/60 shadow-lg shadow-cyan-950/40"
                    : "bg-slate-950/60 border-slate-800/80 hover:bg-slate-800/40 hover:border-slate-700"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-slate-300">
                    Cluster #{c.cluster_id}
                  </span>
                  <span
                    className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded font-bold border ${
                      isCritical
                        ? "bg-rose-950/80 text-rose-300 border-rose-800 animate-pulse"
                        : isWarning
                        ? "bg-amber-950/80 text-amber-300 border-amber-800"
                        : "bg-slate-800 text-slate-400 border-slate-700"
                    }`}
                  >
                    {isCritical ? `+${(c.growth_rate * 100).toFixed(0)}% SPIKE` : "NORMAL"}
                  </span>
                </div>

                <h3 className="text-sm font-semibold text-slate-100 font-sans leading-snug">
                  {c.topic_title}
                </h3>

                {/* Terms Cloud */}
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {c.top_terms.map((t, idx) => (
                    <span
                      key={idx}
                      className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-cyan-400/90"
                    >
                      {t}
                    </span>
                  ))}
                </div>

                {/* Metrics: Velocity & Volume */}
                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono text-slate-400">
                  <div>
                    <span className="text-slate-200 font-bold">{c.current_count}</span>
                    <span className="text-slate-500 text-[10px]"> vs {c.baseline_count} base</span>
                  </div>

                  {c.tracehub_alert_id && (
                    <div className="flex items-center space-x-1 text-[10px] text-amber-400">
                      <BellRing className="w-3 h-3 text-amber-400" />
                      <span>{c.tracehub_alert_id}</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Selected Cluster Details Drawer */}
        {selectedClusterId && (
          <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between text-xs font-mono text-slate-300">
              <span className="font-bold uppercase tracking-wide flex items-center space-x-2">
                <Layers className="w-4 h-4 text-cyan-400" />
                <span>Cluster #{selectedClusterId} Diagnostic Breakdown</span>
              </span>
              <span className="text-slate-500">Tracehub Integration</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
              <div className="space-y-2 p-3 rounded-lg bg-slate-900 border border-slate-800">
                <span className="text-[10px] text-slate-500 uppercase block">Associated Asset / Part Numbers</span>
                <div className="flex items-center space-x-2">
                  <Wrench className="w-4 h-4 text-cyan-400" />
                  <span className="text-slate-100 font-bold">
                    {clusters.find((c) => c.cluster_id === selectedClusterId)?.part_numbers.join(", ") || "No specific part tag"}
                  </span>
                </div>
              </div>

              <div className="space-y-2 p-3 rounded-lg bg-slate-900 border border-slate-800">
                <span className="text-[10px] text-slate-500 uppercase block">Sample Clustered Tickets</span>
                <div className="flex flex-wrap gap-1.5">
                  {clusters
                    .find((c) => c.cluster_id === selectedClusterId)
                    ?.sample_ticket_ids.map((id) => (
                      <span
                        key={id}
                        className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-cyan-300 text-[11px]"
                      >
                        {id}
                      </span>
                    ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
