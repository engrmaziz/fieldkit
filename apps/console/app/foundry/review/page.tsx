"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/lib/auth-context";
import { fetchReviewQueue, submitReviewDecision } from "@/lib/api";
import { ReviewQueueItem } from "@/lib/types";
import {
  UserCheck,
  Check,
  X,
  SkipForward,
  Keyboard,
  Sparkles,
  Layers,
  ArrowRight,
  RefreshCw,
  CheckCircle2,
} from "lucide-react";

export default function ReviewQueuePage() {
  const { currentUser, getAuthHeaders } = useAuth();
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const loadQueue = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchReviewQueue(getAuthHeaders());
      setItems(res.items || []);
      setCurrentIndex(0);
    } catch (err: any) {
      setError(err.message || "Failed to load review queue");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQueue();
  }, [currentUser]);

  const handleDecision = useCallback(
    async (decision: "match" | "non_match") => {
      const current = items[currentIndex];
      if (!current) return;

      try {
        const res = await submitReviewDecision(current.pair_id, decision, getAuthHeaders());
        setActionMessage(
          `Decision recorded: ${decision.toUpperCase()} for pair ${current.pair_id}. Affected clusters re-indexed.`
        );

        // Remove resolved item from local queue
        setItems((prev) => prev.filter((_, i) => i !== currentIndex));
        setTimeout(() => setActionMessage(null), 4000);
      } catch (err: any) {
        alert("Failed to submit review decision: " + err.message);
      }
    },
    [items, currentIndex, currentUser]
  );

  const handleSkip = useCallback(() => {
    if (currentIndex < items.length - 1) {
      setCurrentIndex((prev) => prev + 1);
    } else {
      setCurrentIndex(0);
    }
  }, [currentIndex, items.length]);

  // Keyboard shortcut listener: m = match, n = non_match, s = skip
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input
      if (["INPUT", "TEXTAREA", "SELECT"].includes((e.target as HTMLElement).tagName)) {
        return;
      }

      if (e.key.toLowerCase() === "m") {
        e.preventDefault();
        handleDecision("match");
      } else if (e.key.toLowerCase() === "n") {
        e.preventDefault();
        handleDecision("non_match");
      } else if (e.key.toLowerCase() === "s") {
        e.preventDefault();
        handleSkip();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleDecision, handleSkip]);

  const currentPair = items[currentIndex];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center space-x-2">
            <span>Entity Resolution Review Queue</span>
            <span className="text-xs font-mono font-normal px-2 py-0.5 rounded bg-cyan-950 border border-cyan-800 text-cyan-400">
              {items.length} Pending Pairs
            </span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Ambiguous supplier matches requiring human-in-the-loop verification
          </p>
        </div>

        {/* Keyboard Shortcut Legend */}
        <div className="flex items-center space-x-3 text-xs bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg text-slate-400">
          <Keyboard className="w-3.5 h-3.5 text-cyan-400" />
          <span>Hotkeys:</span>
          <span className="font-mono text-emerald-400 font-bold bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700">
            [M] Match
          </span>
          <span className="font-mono text-rose-400 font-bold bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700">
            [N] Non-Match
          </span>
          <span className="font-mono text-slate-300 font-bold bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700">
            [S] Skip
          </span>
        </div>
      </div>

      {/* Action Banner Feedback */}
      {actionMessage && (
        <div className="p-3.5 rounded-xl bg-cyan-950/40 border border-cyan-800 text-cyan-300 text-xs flex items-center space-x-2 animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 text-cyan-400 shrink-0" />
          <span>{actionMessage}</span>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-200 text-xs font-mono">
          {error}
        </div>
      )}

      {loading ? (
        <div className="p-16 text-center text-slate-500 text-xs flex flex-col items-center justify-center space-y-2">
          <RefreshCw className="w-6 h-6 animate-spin text-cyan-400" />
          <span>Loading ambiguous entity pairs from review queue...</span>
        </div>
      ) : items.length === 0 ? (
        <div className="glass-panel rounded-xl p-16 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-emerald-950/80 border border-emerald-700 text-emerald-400 mx-auto flex items-center justify-center">
            <Check className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-bold text-slate-200">Review Queue Empty</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            All ambiguous entity pairs have been resolved. Splink connected-components clustering has established
            canonical supplier survivorship records.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Pair Metadata & ML/LLM Scores Card */}
          <div className="glass-panel rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center space-x-4">
              <div>
                <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider block">
                  Pair Identifier
                </span>
                <span className="text-xs font-mono font-bold text-cyan-400">
                  {currentPair.pair_id}
                </span>
              </div>
              <div className="h-6 w-px bg-slate-800" />
              <div>
                <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider block">
                  Queue Position
                </span>
                <span className="text-xs font-mono text-slate-200">
                  {currentIndex + 1} of {items.length}
                </span>
              </div>
            </div>

            <div className="flex items-center space-x-6 text-xs font-mono">
              <div>
                <span className="text-slate-400">Splink Prob: </span>
                <span className="font-bold text-amber-400">
                  {(currentPair.match_probability * 100).toFixed(1)}%
                </span>
              </div>
              {currentPair.llm_confidence !== undefined && currentPair.llm_confidence !== null && (
                <div>
                  <span className="text-slate-400">LLM Conf: </span>
                  <span className="font-bold text-cyan-400">
                    {(currentPair.llm_confidence * 100).toFixed(0)}%
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Side-by-Side Comparison Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Record A */}
            <div className="glass-panel rounded-xl p-5 space-y-4 border-slate-800">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
                <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  Record A ({currentPair.source_a})
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400">
                  ID: {currentPair.record_a.vendor_id || "A"}
                </span>
              </div>

              <div className="space-y-3 text-xs">
                {Object.entries(currentPair.record_a).map(([k, v]) => {
                  const valB = currentPair.record_b[k];
                  const isDiff = valB !== undefined && String(v) !== String(valB);

                  return (
                    <div key={k} className="space-y-1">
                      <span className="text-[10px] font-mono text-slate-500 uppercase block">{k}</span>
                      <div
                        className={`p-2 rounded font-mono text-xs border ${
                          isDiff
                            ? "bg-amber-950/30 border-amber-800/60 text-amber-200"
                            : "bg-slate-950/60 border-slate-800/80 text-slate-200"
                        }`}
                      >
                        {String(v)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Record B */}
            <div className="glass-panel rounded-xl p-5 space-y-4 border-slate-800">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
                <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  Record B ({currentPair.source_b})
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400">
                  ID: {currentPair.record_b.vendor_id || "B"}
                </span>
              </div>

              <div className="space-y-3 text-xs">
                {Object.entries(currentPair.record_b).map(([k, v]) => {
                  const valA = currentPair.record_a[k];
                  const isDiff = valA !== undefined && String(v) !== String(valA);

                  return (
                    <div key={k} className="space-y-1">
                      <span className="text-[10px] font-mono text-slate-500 uppercase block">{k}</span>
                      <div
                        className={`p-2 rounded font-mono text-xs border ${
                          isDiff
                            ? "bg-amber-950/30 border-amber-800/60 text-amber-200"
                            : "bg-slate-950/60 border-slate-800/80 text-slate-200"
                        }`}
                      >
                        {String(v)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* LLM Evidence Bullets (if available) */}
          {currentPair.llm_evidence && currentPair.llm_evidence.length > 0 && (
            <div className="rounded-xl bg-cyan-950/20 border border-cyan-800/60 p-4 space-y-2">
              <div className="flex items-center space-x-1.5 text-cyan-300 text-xs font-bold">
                <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                <span>LLM Adjudicator Evidence (packages/llm)</span>
              </div>
              <ul className="list-disc list-inside text-xs text-slate-300 space-y-1">
                {currentPair.llm_evidence.map((ev, i) => (
                  <li key={i}>{ev}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Review Decision Buttons Bar */}
          <div className="glass-panel rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
            <span className="text-xs text-slate-400">
              Confirm whether these records represent the same legal business entity:
            </span>

            <div className="flex items-center space-x-3 w-full sm:w-auto">
              <button
                onClick={() => handleDecision("match")}
                className="flex-1 sm:flex-none px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-slate-950 text-xs font-bold flex items-center justify-center space-x-2 transition-colors shadow-lg shadow-emerald-950"
              >
                <Check className="w-4 h-4 stroke-[2.5]" />
                <span>Same Entity [M]</span>
              </button>

              <button
                onClick={() => handleDecision("non_match")}
                className="flex-1 sm:flex-none px-5 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-slate-950 text-xs font-bold flex items-center justify-center space-x-2 transition-colors shadow-lg shadow-rose-950"
              >
                <X className="w-4 h-4 stroke-[2.5]" />
                <span>Different [N]</span>
              </button>

              <button
                onClick={handleSkip}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium flex items-center space-x-1.5 transition-colors"
              >
                <SkipForward className="w-3.5 h-3.5" />
                <span>Skip [S]</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
