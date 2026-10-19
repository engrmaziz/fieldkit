"use client";

import React, { useState } from "react";
import {
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  UserCheck,
  Lock,
  ArrowRight,
} from "lucide-react";
import { UserPrincipal } from "@/lib/types";

interface AclRefusalBannerProps {
  content: string;
  currentUser: UserPrincipal;
  onSwitchToAdminAndRetry?: () => void;
}

export default function AclRefusalBanner({
  content,
  currentUser,
  onSwitchToAdminAndRetry,
}: AclRefusalBannerProps) {
  const [expanded, setExpanded] = useState(false);

  // Check if content indicates an authorization refusal
  const isRefusal =
    content.toLowerCase().includes("authorized to access") ||
    content.toLowerCase().includes("not found in the documents you are authorized") ||
    content.toLowerCase().includes("insufficient permission") ||
    content.toLowerCase().includes("restricted by document policy");

  if (!isRefusal) return null;

  return (
    <div className="mt-3 rounded-xl border border-amber-800/60 bg-amber-950/20 p-4 shadow-sm">
      <div className="flex items-start justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-amber-950/80 border border-amber-700/60 flex items-center justify-center shrink-0">
            <Lock className="w-4 h-4 text-amber-400" />
          </div>
          <div>
            <h4 className="text-xs font-bold text-amber-300 tracking-wide uppercase font-mono">
              Access Control Refusal Triggered
            </h4>
            <p className="text-xs text-slate-300">
              Your active persona does not hold clearance for the requested document scope.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="flex items-center space-x-1 text-xs font-mono text-amber-400 hover:text-amber-200 transition-colors select-none"
        >
          <span>{expanded ? "Hide Details" : "Why can't I see this?"}</span>
          {expanded ? (
            <ChevronUp className="w-3.5 h-3.5" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5" />
          )}
        </button>
      </div>

      {expanded && (
        <div className="mt-4 pt-3.5 border-t border-amber-900/40 text-xs space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3 rounded-lg bg-slate-950/80 border border-slate-800/80">
            <div>
              <span className="text-[11px] font-mono uppercase text-slate-400 block mb-1">
                Your Current Scope:
              </span>
              <div className="space-y-0.5 font-mono text-slate-200">
                <div>
                  <span className="text-slate-400">User:</span> {currentUser.name}
                </div>
                <div>
                  <span className="text-slate-400">Roles:</span>{" "}
                  <span className="text-cyan-400">
                    [{currentUser.roles.join(", ")}]
                  </span>
                </div>
                <div>
                  <span className="text-slate-400">Plant:</span>{" "}
                  <span className="text-emerald-400">
                    {currentUser.plant || "Global (Admin)"}
                  </span>
                </div>
              </div>
            </div>

            <div>
              <span className="text-[11px] font-mono uppercase text-slate-400 block mb-1">
                Required Security Clearance:
              </span>
              <div className="space-y-0.5 font-mono text-slate-200">
                <div>
                  <span className="text-slate-400">Required Roles:</span>{" "}
                  <span className="text-rose-400">[legal] or [admin]</span>
                </div>
                <div>
                  <span className="text-slate-400">Restricted Doc:</span>{" "}
                  <span>Legal Arbitration & Executive Liabilities</span>
                </div>
                <div>
                  <span className="text-slate-400">Enforcement:</span>{" "}
                  <span className="text-teal-400">Pre-Retrieval Pruning (0 Leaks)</span>
                </div>
              </div>
            </div>
          </div>

          <p className="text-slate-400 text-xs leading-relaxed">
            Fieldkit enforces strict pre-retrieval role-based filtering: chunks with restricted
            clearance tags are dropped by the indexing engine before vector ranking.
            The LLM never observes unauthorized passages.
          </p>

          {onSwitchToAdminAndRetry && !currentUser.roles.includes("admin") && !currentUser.roles.includes("legal") && (
            <div className="flex justify-end pt-1">
              <button
                type="button"
                onClick={onSwitchToAdminAndRetry}
                className="inline-flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-600 hover:bg-amber-500 text-slate-950 transition-colors shadow-sm"
              >
                <UserCheck className="w-3.5 h-3.5" />
                <span>Switch to Sofia Schmidt (Legal / Admin) & Retry</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
