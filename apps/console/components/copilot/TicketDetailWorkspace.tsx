"use client";

import React, { useState } from "react";
import { Ticket } from "./types";
import {
  ShieldCheck,
  Eye,
  EyeOff,
  Building2,
  FileCheck2,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Edit3,
  Send,
  Lock,
  ArrowRight,
  ExternalLink,
  Scale,
  Sparkles,
  Info,
} from "lucide-react";

interface TicketDetailWorkspaceProps {
  ticket: Ticket;
  onApprove: (ticketId: string) => void;
  onReject: (ticketId: string, feedback: string) => void;
  onEditAndApprove: (ticketId: string, editedDraft: string) => void;
}

export default function TicketDetailWorkspace({
  ticket,
  onApprove,
  onReject,
  onEditAndApprove,
}: TicketDetailWorkspaceProps) {
  const [unmaskPII, setUnmaskPII] = useState<boolean>(false);
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [editedDraft, setEditedDraft] = useState<string>(
    ticket.action_plan?.reply_draft || ""
  );
  const [rejectModalOpen, setRejectModalOpen] = useState<boolean>(false);
  const [rejectionReason, setRejectionReason] = useState<string>(
    "Customer unit shows signs of improper installation outside warranty terms."
  );

  const isAwaiting = ticket.status === "awaiting_approval";

  return (
    <div className="flex flex-col h-full bg-slate-900/60 border border-slate-800/80 rounded-xl overflow-hidden shadow-xl backdrop-blur-md">
      {/* Workspace Header */}
      <div className="p-4 border-b border-slate-800 bg-slate-950/60 flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center space-x-2.5">
            <span className="font-mono text-base font-bold text-slate-100">
              {ticket.ticket_id}
            </span>
            <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-cyan-950/80 border border-cyan-800 text-cyan-300 font-semibold uppercase">
              {ticket.queue.replace("_", " ")}
            </span>
            <span className="text-[11px] font-mono text-slate-400">
              Confidence: {(ticket.confidence * 100).toFixed(1)}% (XLM-R Local Int8)
            </span>
          </div>
          <div className="flex items-center space-x-3 text-xs text-slate-400">
            <span className="text-slate-200 font-medium">{ticket.customer_name}</span>
            <span>•</span>
            <span className="font-mono text-cyan-400">Order {ticket.order_id}</span>
            <span>•</span>
            <span className="font-mono">{ticket.plant}</span>
          </div>
        </div>

        {/* PII Unmask Toggle */}
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setUnmaskPII(!unmaskPII)}
            className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-mono transition-all border ${
              unmaskPII
                ? "bg-amber-950/80 text-amber-300 border-amber-600 shadow-sm"
                : "bg-slate-900 text-slate-300 border-slate-700 hover:border-slate-600"
            }`}
          >
            {unmaskPII ? (
              <>
                <EyeOff className="w-3.5 h-3.5 text-amber-400" />
                <span>Mask PII</span>
              </>
            ) : (
              <>
                <Eye className="w-3.5 h-3.5 text-cyan-400" />
                <span>Unmask PII</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main Workspace Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {/* PII Alert Banner if Unmasked */}
        {unmaskPII && (
          <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center justify-between font-mono">
            <div className="flex items-center space-x-2">
              <Lock className="w-4 h-4 text-amber-400 shrink-0" />
              <span>
                <strong>Confidential View:</strong> Accessing unredacted customer banking & contact data under GDPR Art 6 compliance audit.
              </span>
            </div>
            <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-amber-950 border border-amber-700">
              AUDITED
            </span>
          </div>
        )}

        {/* 1. Customer Message & Presidio Sanitization Box */}
        <div className="p-4 rounded-lg bg-slate-950/70 border border-slate-800 space-y-2">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span className="flex items-center space-x-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Customer Inbound Message ({ticket.language.toUpperCase()})</span>
            </span>
            <span className="text-[10px] text-slate-500">
              Presidio Deterministic Filter Active
            </span>
          </div>
          <p className="text-xs text-slate-200 leading-relaxed font-sans whitespace-pre-wrap">
            {unmaskPII ? ticket.raw_text : ticket.masked_text}
          </p>

          {ticket.pii_detected.length > 0 && (
            <div className="pt-2 border-t border-slate-800/80 flex items-center space-x-2 text-[10px] font-mono text-slate-400">
              <span className="text-slate-500">Redacted Tokens:</span>
              {ticket.pii_detected.map((p, idx) => (
                <span
                  key={idx}
                  className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-amber-400/90"
                >
                  {p}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* 2. ERP Context Card (Customer, Plant, Order & Legal Hold) */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="p-3 rounded-lg bg-slate-950/50 border border-slate-800 text-xs space-y-1">
            <span className="text-[10px] text-slate-500 font-mono uppercase block">Customer Profile</span>
            <div className="font-semibold text-slate-200">{ticket.customer_name}</div>
            <div className="text-[11px] font-mono text-slate-400">{ticket.customer_id}</div>
          </div>

          <div className="p-3 rounded-lg bg-slate-950/50 border border-slate-800 text-xs space-y-1">
            <span className="text-[10px] text-slate-500 font-mono uppercase block">Order & Delivery</span>
            <div className="font-semibold text-cyan-400 font-mono">{ticket.order_id}</div>
            <div className="text-[11px] font-mono text-slate-400">
              Total: €{ticket.order_total_eur?.toLocaleString() || "N/A"} • Plant: {ticket.plant}
            </div>
          </div>

          <div className="p-3 rounded-lg bg-slate-950/50 border border-slate-800 text-xs space-y-1">
            <span className="text-[10px] text-slate-500 font-mono uppercase block">Legal Hold Status</span>
            <div className="flex items-center space-x-1.5">
              {ticket.legal_hold ? (
                <span className="flex items-center space-x-1 font-mono text-xs font-bold text-rose-400">
                  <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                  <span>ACTIVE LEGAL HOLD</span>
                </span>
              ) : (
                <span className="flex items-center space-x-1 font-mono text-xs font-bold text-emerald-400">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>CLEARED (No Holds)</span>
                </span>
              )}
            </div>
            <div className="text-[10px] text-slate-500 font-mono">Enforced by policy.yaml</div>
          </div>
        </div>

        {/* 3. Action Plan & Policy Checks */}
        {ticket.action_plan && (
          <div className="p-4 rounded-lg bg-slate-950/80 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <FileCheck2 className="w-4 h-4 text-cyan-400" />
                <h3 className="text-xs font-bold font-mono tracking-wide text-slate-100 uppercase">
                  Proposed Action Plan & Tool Calls
                </h3>
              </div>
              <span className="text-[11px] font-mono text-slate-400">
                {ticket.action_plan.actions.length} tools planned
              </span>
            </div>

            <div className="space-y-2">
              {ticket.action_plan.actions.map((action, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-1.5 text-xs"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2 font-mono">
                      <span className="text-cyan-400 font-bold">{action.tool}()</span>
                      {action.side_effect ? (
                        <span className="px-1.5 py-0.2 rounded text-[10px] bg-amber-500/10 border border-amber-500/30 text-amber-400 font-mono">
                          MUTATING SIDE-EFFECT
                        </span>
                      ) : (
                        <span className="px-1.5 py-0.2 rounded text-[10px] bg-slate-800 text-slate-400 font-mono">
                          READ-ONLY
                        </span>
                      )}
                    </div>
                    <span className="text-[11px] font-mono text-slate-500">
                      Index #{idx}
                    </span>
                  </div>

                  <p className="text-[11px] text-slate-400 font-sans">
                    {action.rationale}
                  </p>

                  <div className="p-2 rounded bg-slate-950 border border-slate-800/80 font-mono text-[11px] text-slate-300 overflow-x-auto">
                    {JSON.stringify(action.args, null, 2)}
                  </div>
                </div>
              ))}
            </div>

            {/* Policy Evaluation Verdict */}
            <div className="p-3 rounded-lg bg-slate-900/90 border border-slate-800 space-y-2">
              <div className="flex items-center space-x-2 text-xs font-mono text-slate-300">
                <Scale className="w-3.5 h-3.5 text-cyan-400" />
                <span className="font-bold">Deterministic Policy Verification (policy.yaml):</span>
              </div>

              {ticket.violations && ticket.violations.length > 0 ? (
                <div className="space-y-1.5 pt-1">
                  {ticket.violations.map((v, i) => (
                    <div
                      key={i}
                      className="p-2 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center space-x-2"
                    >
                      <AlertTriangle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                      <span className="font-mono text-[11px]">
                        [{v.rule}] {v.message}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-2 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-center space-x-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  <span className="font-mono text-[11px]">
                    All deterministic policy constraints met (Return within 90 days, credit &le; €500, legal hold clear).
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 4. Outbound Draft Response */}
        <div className="p-4 rounded-lg bg-slate-950/80 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Send className="w-4 h-4 text-cyan-400" />
              <h3 className="text-xs font-bold font-mono tracking-wide text-slate-100 uppercase">
                Outbound Customer Draft (Mailpit SMTP Dispatch)
              </h3>
            </div>
            {isAwaiting && !isEditing && (
              <button
                onClick={() => setIsEditing(true)}
                className="flex items-center space-x-1.5 px-2.5 py-1 rounded text-xs font-mono bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors"
              >
                <Edit3 className="w-3 h-3 text-cyan-400" />
                <span>Edit Draft</span>
              </button>
            )}
          </div>

          {isEditing ? (
            <div className="space-y-2">
              <textarea
                value={editedDraft}
                onChange={(e) => setEditedDraft(e.target.value)}
                rows={6}
                className="w-full bg-slate-900 border border-cyan-500/60 rounded-lg p-3 text-xs text-slate-200 font-mono focus:outline-none leading-relaxed"
              />
              <div className="flex items-center justify-end space-x-2">
                <button
                  onClick={() => setIsEditing(false)}
                  className="px-3 py-1 rounded text-xs font-mono bg-slate-800 text-slate-400 hover:text-slate-200"
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    setIsEditing(false);
                    onEditAndApprove(ticket.ticket_id, editedDraft);
                  }}
                  className="px-3 py-1 rounded text-xs font-mono bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold"
                >
                  Save & Approve
                </button>
              </div>
            </div>
          ) : (
            <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 text-xs text-slate-300 font-sans leading-relaxed whitespace-pre-wrap">
              {ticket.action_plan?.reply_draft}
            </div>
          )}
        </div>
      </div>

      {/* Human-in-the-Loop Action Bar (Only active when awaiting approval) */}
      {isAwaiting && (
        <div className="p-4 border-t border-slate-800 bg-slate-950 flex items-center justify-between gap-3">
          <div className="flex items-center space-x-2 text-xs font-mono text-amber-400">
            <AlertTriangle className="w-4 h-4 text-amber-400 animate-pulse" />
            <span>Side-effect tools require supervisor sign-off before mutation</span>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={() => setRejectModalOpen(true)}
              className="flex items-center space-x-1.5 px-4 py-2 rounded-lg text-xs font-mono font-bold bg-rose-500/10 text-rose-400 border border-rose-500/30 hover:bg-rose-500/20 transition-all"
            >
              <XCircle className="w-3.5 h-3.5" />
              <span>Reject Plan</span>
            </button>

            <button
              onClick={() => onApprove(ticket.ticket_id)}
              className="flex items-center space-x-1.5 px-5 py-2 rounded-lg text-xs font-mono font-bold bg-emerald-600 hover:bg-emerald-500 text-slate-950 transition-all shadow-lg shadow-emerald-950/40"
            >
              <CheckCircle2 className="w-3.5 h-3.5 text-slate-950" />
              <span>Approve & Execute</span>
            </button>
          </div>
        </div>
      )}

      {/* Reject Confirmation Dialog */}
      {rejectModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4 shadow-2xl">
            <div className="flex items-center space-x-2 text-rose-400 font-mono text-sm font-bold">
              <XCircle className="w-4 h-4" />
              <span>Reject Action Plan</span>
            </div>
            <p className="text-xs text-slate-300 font-sans">
              Provide feedback for the rejection. Zero external tools will execute, and the rejection will be permanently cryptographically signed in the audit ledger.
            </p>
            <textarea
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              rows={3}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-rose-500"
            />
            <div className="flex items-center justify-end space-x-2 pt-2">
              <button
                onClick={() => setRejectModalOpen(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-mono bg-slate-800 text-slate-400 hover:text-slate-200"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setRejectModalOpen(false);
                  onReject(ticket.ticket_id, rejectionReason);
                }}
                className="px-4 py-1.5 rounded-lg text-xs font-mono font-bold bg-rose-600 hover:bg-rose-500 text-slate-100"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
