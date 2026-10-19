"use client";

import React, { useState } from "react";
import {
  ThumbsUp,
  ThumbsDown,
  Copy,
  Check,
  Activity,
  MessageSquare,
  Send,
} from "lucide-react";
import { submitAssistantFeedback } from "@/lib/assistant-api";
import { useAuth } from "@/lib/auth-context";

interface FeedbackButtonsProps {
  traceId?: string | null;
  route?: string;
  query?: string;
  initialFeedback?: "up" | "down" | null;
}

export default function FeedbackButtons({
  traceId,
  route,
  query,
  initialFeedback = null,
}: FeedbackButtonsProps) {
  const { getAuthHeaders } = useAuth();
  const [feedback, setFeedback] = useState<"up" | "down" | null>(initialFeedback);
  const [copiedTrace, setCopiedTrace] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submittedMessage, setSubmittedMessage] = useState<string | null>(null);
  const [showCommentBox, setShowCommentBox] = useState(false);
  const [comment, setComment] = useState("");

  const handleFeedback = async (vote: "up" | "down", commentText?: string) => {
    if (!traceId) {
      setFeedback(vote);
      return;
    }

    setFeedback(vote);
    setIsSubmitting(true);

    try {
      await submitAssistantFeedback(
        {
          traceId,
          thumbs: vote,
          comment: commentText || comment || undefined,
          route,
          query,
        },
        getAuthHeaders()
      );
      setSubmittedMessage(vote === "up" ? "Feedback recorded!" : "Critique logged to P7.");
      setTimeout(() => setSubmittedMessage(null), 3000);
      setShowCommentBox(false);
    } catch (err) {
      console.warn("Feedback submission error:", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCopyTrace = () => {
    if (!traceId) return;
    navigator.clipboard.writeText(traceId);
    setCopiedTrace(true);
    setTimeout(() => setCopiedTrace(false), 2000);
  };

  return (
    <div className="mt-3 flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-800/60 text-xs">
      {/* Left side: Trace ID telemetry pill */}
      <div className="flex items-center space-x-2">
        {traceId ? (
          <div className="inline-flex items-center space-x-1.5 px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-[10px] font-mono text-slate-400">
            <Activity className="w-3 h-3 text-cyan-400 shrink-0" />
            <span>Trace:</span>
            <span className="text-slate-300 font-semibold truncate max-w-[100px] sm:max-w-[140px]">
              {traceId.slice(0, 12)}...
            </span>
            <button
              type="button"
              onClick={handleCopyTrace}
              className="text-slate-400 hover:text-white p-0.5 rounded transition-colors"
              title="Copy OpenTelemetry trace ID"
            >
              {copiedTrace ? (
                <Check className="w-3 h-3 text-emerald-400" />
              ) : (
                <Copy className="w-3 h-3" />
              )}
            </button>
          </div>
        ) : (
          <span className="text-[10px] font-mono text-slate-400">Fieldkit Local Trace</span>
        )}

        {submittedMessage && (
          <span className="text-[11px] font-mono text-emerald-400 animate-fade-in">
            ✓ {submittedMessage}
          </span>
        )}
      </div>

      {/* Right side: Thumbs up/down buttons */}
      <div className="flex items-center space-x-1.5">
        <button
          type="button"
          onClick={() => handleFeedback("up")}
          disabled={isSubmitting}
          className={`p-1.5 rounded-lg border transition-all ${
            feedback === "up"
              ? "bg-emerald-950/80 border-emerald-600/70 text-emerald-300 shadow-sm"
              : "bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-800/80"
          }`}
          title="Helpful response"
        >
          <ThumbsUp className="w-3.5 h-3.5" />
        </button>

        <button
          type="button"
          onClick={() => {
            if (feedback !== "down") {
              handleFeedback("down");
              setShowCommentBox(true);
            } else {
              setShowCommentBox(!showCommentBox);
            }
          }}
          disabled={isSubmitting}
          className={`p-1.5 rounded-lg border transition-all ${
            feedback === "down"
              ? "bg-rose-950/80 border-rose-600/70 text-rose-300 shadow-sm"
              : "bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-800/80"
          }`}
          title="Not helpful / Needs correction"
        >
          <ThumbsDown className="w-3.5 h-3.5" />
        </button>

        <button
          type="button"
          onClick={() => setShowCommentBox(!showCommentBox)}
          className={`p-1.5 rounded-lg border text-slate-400 hover:text-slate-200 transition-colors ${
            showCommentBox
              ? "bg-slate-800 border-slate-700 text-slate-200"
              : "bg-slate-900/60 border-slate-800 hover:bg-slate-800/80"
          }`}
          title="Add feedback critique"
        >
          <MessageSquare className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Expandable Critique Comment Input */}
      {showCommentBox && (
        <div className="w-full mt-2 flex items-center space-x-2">
          <input
            type="text"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && comment.trim()) {
                handleFeedback(feedback || "down", comment.trim());
              }
            }}
            placeholder="What went wrong or could be improved? (optional)"
            className="flex-1 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500/50"
          />
          <button
            type="button"
            onClick={() => handleFeedback(feedback || "down", comment.trim())}
            className="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-medium text-xs flex items-center space-x-1"
          >
            <span>Submit</span>
            <Send className="w-3 h-3" />
          </button>
        </div>
      )}
    </div>
  );
}
