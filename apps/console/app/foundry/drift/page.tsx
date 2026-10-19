"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { fetchDriftEvents, approveDrift, rejectDrift } from "@/lib/api";
import { DriftEvent } from "@/lib/types";
import {
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Sparkles,
  ArrowRight,
  ShieldAlert,
  RefreshCw,
  Layers,
} from "lucide-react";

export default function DriftInboxPage() {
  const { currentUser, getAuthHeaders } = useAuth();
  const [events, setEvents] = useState<DriftEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);

  const loadEvents = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchDriftEvents(getAuthHeaders());
      setEvents(res);
    } catch (err: any) {
      setError(err.message || "Failed to load drift events");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEvents();
  }, [currentUser]);

  const handleApprove = async (eventId: string) => {
    setActionInProgress(eventId);
    try {
      await approveDrift(eventId, getAuthHeaders());
      setEvents((prev) =>
        prev.map((e) => (e.event_id === eventId ? { ...e, status: "approved" } : e))
      );
    } catch (err: any) {
      alert("Approval failed: " + err.message);
    } finally {
      setActionInProgress(null);
    }
  };

  const handleReject = async (eventId: string) => {
    setActionInProgress(eventId);
    try {
      await rejectDrift(eventId, getAuthHeaders());
      setEvents((prev) =>
        prev.map((e) => (e.event_id === eventId ? { ...e, status: "rejected" } : e))
      );
    } catch (err: any) {
      alert("Rejection failed: " + err.message);
    } finally {
      setActionInProgress(null);
    }
  };

  const blockEvents = events.filter((e) => e.severity === "BLOCK" && e.status !== "approved");

  return (
    <div className="space-y-6">
      {/* Header & Gate Status */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center space-x-2">
            <span>Schema & Statistical Drift Inbox</span>
            <span className="text-xs font-mono font-normal px-2 py-0.5 rounded bg-slate-800 text-slate-300">
              {events.length} Total Events
            </span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Deterministic rule violations and AI column rename proposals awaiting analyst approval
          </p>
        </div>

        <button
          onClick={loadEvents}
          disabled={loading}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 text-xs text-slate-300 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh Inbox</span>
        </button>
      </div>

      {/* Promotion Gate Status Banner */}
      {blockEvents.length > 0 ? (
        <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800/80 text-xs space-y-2">
          <div className="flex items-center space-x-2 text-rose-300 font-bold">
            <ShieldAlert className="w-4 h-4 text-rose-400" />
            <span>Promotion Gate: BLOCKED ({blockEvents.length} unresolved BLOCK events)</span>
          </div>
          <p className="text-rose-200/80 leading-relaxed">
            Staging promotion to the core ontology is halted because required contract columns are missing or types
            have drifted. Approve suggested column renames below to register an override in the{" "}
            <code className="font-mono bg-rose-950 px-1 py-0.5 rounded">contract_override</code> table and resume
            automated promotion.
          </p>
        </div>
      ) : (
        <div className="p-3.5 rounded-xl bg-emerald-950/30 border border-emerald-800/60 text-xs flex items-center space-x-2 text-emerald-300">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>Promotion Gate Clear: No unresolved BLOCK events halting staging promotion.</span>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-200 text-xs font-mono">
          {error}
        </div>
      )}

      {/* Event Cards List */}
      {loading ? (
        <div className="p-16 text-center text-slate-500 text-xs flex flex-col items-center justify-center space-y-2">
          <RefreshCw className="w-6 h-6 animate-spin text-cyan-400" />
          <span>Scanning drift events from persistence store...</span>
        </div>
      ) : events.length === 0 ? (
        <div className="glass-panel rounded-xl p-12 text-center text-slate-500 text-xs">
          No schema or statistical drift events recorded. Ingest runs are adhering 100% to contract YAMLs.
        </div>
      ) : (
        <div className="space-y-4">
          {events.map((evt) => {
            const isBlock = evt.severity === "BLOCK";
            const suggestion = evt.suggestion;
            const isPending = evt.status === "open" || evt.status === "suggested";

            return (
              <div
                key={evt.event_id}
                className={`glass-panel rounded-xl p-5 space-y-4 border transition-all ${
                  isBlock ? "border-rose-900/40 hover:border-rose-700/60" : "border-slate-800 hover:border-slate-700"
                }`}
              >
                {/* Event Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                  <div className="flex items-center space-x-2.5">
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase tracking-wider ${
                        isBlock
                          ? "bg-rose-950 text-rose-300 border border-rose-800"
                          : "bg-amber-950 text-amber-300 border border-amber-800"
                      }`}
                    >
                      {evt.severity}
                    </span>
                    <span className="text-xs font-mono font-bold text-slate-200">{evt.event_type}</span>
                    <span className="text-xs text-slate-400">• Source: {evt.source}</span>
                  </div>

                  <div className="flex items-center space-x-3 text-[11px] font-mono text-slate-400">
                    <span>Run: {evt.run_id}</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold ${
                        evt.status === "approved"
                          ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                          : evt.status === "rejected"
                          ? "bg-slate-800 text-slate-400"
                          : "bg-cyan-950 text-cyan-300 border border-cyan-800"
                      }`}
                    >
                      {evt.status}
                    </span>
                  </div>
                </div>

                {/* Details Summary */}
                <div className="text-xs text-slate-300 space-y-1">
                  <div>
                    Target Column: <span className="font-mono text-cyan-300 font-semibold">{evt.column_name}</span>
                  </div>
                  {evt.details?.reason && (
                    <div className="text-slate-400 text-[11px] leading-relaxed">
                      {evt.details.reason}
                    </div>
                  )}
                </div>

                {/* LLM Rename Proposal Card (if available) */}
                {suggestion && (
                  <div className="rounded-lg bg-cyan-950/20 border border-cyan-800/60 p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-1.5 text-cyan-300 text-xs font-bold">
                        <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                        <span>LLM Column Rename Proposal (packages/llm)</span>
                      </div>
                      {suggestion.confidence !== undefined && (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-950 border border-cyan-800 text-cyan-300">
                          Confidence: {Math.round(suggestion.confidence * 100)}%
                        </span>
                      )}
                    </div>

                    {suggestion.mapping && (
                      <div className="flex items-center space-x-3 text-xs font-mono bg-slate-950/60 p-2.5 rounded border border-slate-800">
                        <span className="text-rose-400 font-semibold line-through">
                          {suggestion.mapping.old}
                        </span>
                        <ArrowRight className="w-4 h-4 text-cyan-400" />
                        <span className="text-emerald-400 font-semibold">
                          {suggestion.mapping.new}
                        </span>
                      </div>
                    )}

                    {suggestion.reason && (
                      <p className="text-[11px] text-slate-300 leading-relaxed italic">
                        &quot;{suggestion.reason}&quot;
                      </p>
                    )}

                    {/* Action Buttons */}
                    {isPending && (
                      <div className="flex items-center space-x-3 pt-2">
                        <button
                          onClick={() => handleApprove(evt.event_id)}
                          disabled={actionInProgress === evt.event_id}
                          className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-slate-950 text-xs font-semibold flex items-center space-x-1.5 transition-colors disabled:opacity-50"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Approve Mapping Override</span>
                        </button>
                        <button
                          onClick={() => handleReject(evt.event_id)}
                          disabled={actionInProgress === evt.event_id}
                          className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium flex items-center space-x-1.5 transition-colors"
                        >
                          <XCircle className="w-3.5 h-3.5" />
                          <span>Reject Proposal</span>
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
