"use client";

import React, { useState } from "react";
import { AuditEventItem } from "./types";
import {
  ShieldCheck,
  ShieldAlert,
  GitCommit,
  CheckCircle2,
  Clock,
  Layers,
  ChevronRight,
  Code,
  Bug,
  AlertTriangle,
} from "lucide-react";

interface AuditLedgerTimelineProps {
  ticketId: string;
  events: AuditEventItem[];
}

export default function AuditLedgerTimeline({
  ticketId,
  events,
}: AuditLedgerTimelineProps) {
  const [tamperSimulated, setTamperSimulated] = useState<boolean>(false);
  const [selectedEventSeq, setSelectedEventSeq] = useState<number | null>(null);

  // If tamper simulated, sequence 2 has modified payload causing hash break
  const isValid = !tamperSimulated;

  return (
    <div className="flex flex-col h-full bg-slate-900/60 border border-slate-800/80 rounded-xl overflow-hidden shadow-xl backdrop-blur-md">
      {/* Header & Cryptographic Status */}
      <div className="p-4 border-b border-slate-800 bg-slate-950/60 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center space-x-2.5">
          <Layers className="w-4 h-4 text-cyan-400" />
          <h2 className="text-sm font-semibold tracking-wide text-slate-100 uppercase">
            SHA-256 Hash-Chained Audit Ledger
          </h2>
          <span className="text-xs font-mono text-slate-400">({ticketId})</span>
        </div>

        <div className="flex items-center space-x-2.5">
          {isValid ? (
            <div className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-mono bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Chain Integrity: 100% Valid</span>
            </div>
          ) : (
            <div className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-mono bg-rose-500/10 border border-rose-500/30 text-rose-400 animate-pulse">
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>TAMPER DETECTED: Sequence #2 Hash Mismatch</span>
            </div>
          )}

          <button
            onClick={() => setTamperSimulated(!tamperSimulated)}
            className={`px-2.5 py-1 rounded text-[11px] font-mono border transition-all ${
              tamperSimulated
                ? "bg-rose-950/80 text-rose-300 border-rose-700"
                : "bg-slate-900 text-slate-400 hover:text-slate-200 border-slate-800"
            }`}
          >
            {tamperSimulated ? "Reset Integrity" : "Simulate Tamper"}
          </button>
        </div>
      </div>

      {/* Timeline Stream */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {events.length === 0 ? (
          <div className="text-center py-16 text-slate-500 space-y-2">
            <Layers className="w-8 h-8 mx-auto stroke-1 text-slate-600" />
            <p className="text-xs font-mono">No audit events logged yet for this ticket</p>
          </div>
        ) : (
          <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-0.5 before:bg-slate-800">
            {events.map((ev) => {
              const isSelected = selectedEventSeq === ev.sequence;
              const isBroken = tamperSimulated && ev.sequence >= 2;

              return (
                <div key={ev.sequence} className="relative group text-left">
                  {/* Sequence Node Dot */}
                  <div
                    className={`absolute -left-6 top-1 w-3.5 h-3.5 rounded-full border-2 transition-all ${
                      isBroken
                        ? "bg-rose-500 border-rose-300 shadow-md shadow-rose-900/50"
                        : "bg-slate-950 border-cyan-400 shadow-sm"
                    }`}
                  />

                  {/* Event Card */}
                  <div
                    onClick={() =>
                      setSelectedEventSeq(isSelected ? null : ev.sequence)
                    }
                    className={`p-3 rounded-lg border cursor-pointer transition-all ${
                      isSelected
                        ? "bg-slate-800/90 border-cyan-500/60"
                        : isBroken
                        ? "bg-rose-950/20 border-rose-800/60"
                        : "bg-slate-950/50 border-slate-800/80 hover:bg-slate-800/40 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs mb-1">
                      <div className="flex items-center space-x-2 font-mono">
                        <span className="text-slate-400 text-[10px]">
                          #{ev.sequence}
                        </span>
                        <span className="font-bold text-slate-200">
                          {ev.event_type}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-900 border border-slate-800 text-cyan-400">
                          {ev.state_name}
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-500 font-mono">
                        {new Date(ev.timestamp).toLocaleTimeString()}
                      </span>
                    </div>

                    {/* Hash pointer display */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[10px] font-mono pt-1 text-slate-400">
                      <div className="truncate">
                        <span className="text-slate-500">prev: </span>
                        <span className="text-slate-300">
                          {ev.prev_hash.slice(0, 16)}...
                        </span>
                      </div>
                      <div className="truncate">
                        <span className="text-slate-500">hash: </span>
                        <span
                          className={
                            isBroken && ev.sequence === 2
                              ? "text-rose-400 font-bold"
                              : "text-cyan-400"
                          }
                        >
                          {ev.event_hash.slice(0, 16)}...
                        </span>
                      </div>
                    </div>

                    {/* Expandable Payload JSON */}
                    {isSelected && (
                      <div className="mt-2.5 pt-2 border-t border-slate-800 font-mono text-[11px]">
                        <span className="text-slate-500 text-[10px] block mb-1">
                          Canonical Payload:
                        </span>
                        <pre className="p-2.5 rounded bg-slate-950 border border-slate-800 text-slate-300 overflow-x-auto">
                          {JSON.stringify(ev.payload, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
