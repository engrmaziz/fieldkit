"use client";

import React from "react";
import { BookOpen, Database, Sparkles, Zap } from "lucide-react";

interface RouteBadgeProps {
  route?: string;
  confidence?: number;
  cached?: boolean;
  rewrittenQuery?: string;
}

export default function RouteBadge({
  route,
  confidence,
  cached,
  rewrittenQuery,
}: RouteBadgeProps) {
  if (!route) return null;

  const normalizedRoute = route.toLowerCase();

  let badgeColor = "bg-slate-800 text-slate-300 border-slate-700";
  let label = "ROUTER";
  let Icon = Sparkles;

  if (normalizedRoute === "rag") {
    badgeColor = "bg-emerald-950/70 text-emerald-300 border-emerald-700/50 shadow-emerald-900/20";
    label = "RAG RETRIEVAL";
    Icon = BookOpen;
  } else if (normalizedRoute === "sql") {
    badgeColor = "bg-cyan-950/70 text-cyan-300 border-cyan-700/50 shadow-cyan-900/20";
    label = "NL2SQL ENGINE";
    Icon = Database;
  } else if (normalizedRoute === "both") {
    badgeColor = "bg-purple-950/70 text-purple-300 border-purple-700/50 shadow-purple-900/20";
    label = "HYBRID (RAG + SQL)";
    Icon = Sparkles;
  }

  const confidencePct =
    confidence !== undefined ? Math.round(confidence * 100) : null;

  return (
    <div className="flex flex-wrap items-center gap-2 mb-2 select-none">
      <div
        className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono font-medium border shadow-sm ${badgeColor}`}
      >
        <Icon className="w-3.5 h-3.5" />
        <span>{label}</span>
        {confidencePct !== null && (
          <span className="opacity-75 font-normal">({confidencePct}%)</span>
        )}
      </div>

      {cached && (
        <div className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-mono bg-amber-950/50 border border-amber-700/40 text-amber-300">
          <Zap className="w-3 h-3 text-amber-400" />
          <span>Cached (Exact Match)</span>
        </div>
      )}

      {rewrittenQuery && (
        <span
          className="text-[11px] text-slate-400 font-mono italic max-w-md truncate"
          title={`Rewritten query: "${rewrittenQuery}"`}
        >
          Context rewritten
        </span>
      )}
    </div>
  );
}
