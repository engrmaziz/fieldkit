"use client";

import React, { useState } from "react";
import {
  X,
  Clock,
  Layers,
  Cpu,
  Hash,
  AlertCircle,
  CheckCircle2,
  Copy,
  Check,
  ChevronRight,
  ChevronDown,
  ShieldCheck,
  FileCode2,
} from "lucide-react";

export interface SpanTreeNode {
  span_id: string;
  parent_span_id: string;
  name: string;
  service: string;
  status: string;
  duration_ms: number;
  relative_start_ms: number;
  model: string;
  task: string;
  prompt_version: string;
  route: string;
  plant: string;
  input_tokens: number;
  output_tokens: number;
  attributes: Record<string, string>;
  events: Array<{ name: string; content?: string; [key: string]: any }>;
  children: SpanTreeNode[];
}

export interface TraceTreeResponse {
  trace_id: string;
  total_duration_ms: number;
  total_spans: number;
  root: SpanTreeNode | null;
}

interface TraceWaterfallDrawerProps {
  tree: TraceTreeResponse | null;
  isOpen: boolean;
  onClose: () => void;
}

export default function TraceWaterfallDrawer({
  tree,
  isOpen,
  onClose,
}: TraceWaterfallDrawerProps) {
  const [copied, setCopied] = useState(false);
  const [selectedSpan, setSelectedSpan] = useState<SpanTreeNode | null>(null);
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({});

  if (!isOpen || !tree) return null;

  const totalDuration = Math.max(tree.total_duration_ms, 1.0);

  const handleCopyTraceId = () => {
    navigator.clipboard.writeText(tree.trace_id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const toggleExpand = (spanId: string) => {
    setExpandedNodes((prev) => ({
      ...prev,
      [spanId]: !prev[spanId],
    }));
  };

  const activeSpan = selectedSpan || tree.root;

  // Flatten tree for hierarchical waterfall rendering
  const renderSpanRow = (node: SpanTreeNode, depth: number = 0) => {
    const isExpanded = expandedNodes[node.span_id] ?? true;
    const isSelected = activeSpan?.span_id === node.span_id;
    const hasChildren = node.children && node.children.length > 0;

    // Calculate percentage start and width for timeline bar
    const leftPct = Math.min(100, Math.max(0, (node.relative_start_ms / totalDuration) * 100));
    const widthPct = Math.min(100 - leftPct, Math.max(1.5, (node.duration_ms / totalDuration) * 100));

    const isError = node.status === "ERROR" || node.status === "error";

    return (
      <React.Fragment key={node.span_id}>
        <div
          onClick={() => setSelectedSpan(node)}
          className={`flex items-center text-xs py-2 px-3 border-b border-slate-800/60 cursor-pointer transition-colors ${
            isSelected
              ? "bg-cyan-950/40 border-l-2 border-l-cyan-400"
              : "hover:bg-slate-900/60"
          }`}
        >
          {/* Span Name & Tree Indent */}
          <div className="w-2/5 flex items-center pr-3 min-w-0" style={{ paddingLeft: `${depth * 16}px` }}>
            {hasChildren ? (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  toggleExpand(node.span_id);
                }}
                className="p-0.5 mr-1.5 text-slate-400 hover:text-slate-200"
              >
                {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
              </button>
            ) : (
              <div className="w-4 mr-1.5" />
            )}

            <span className="truncate font-mono font-medium text-slate-200 mr-2" title={node.name}>
              {node.name}
            </span>

            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono shrink-0">
              {node.service}
            </span>
          </div>

          {/* Timeline Bar */}
          <div className="w-3/5 relative h-5 flex items-center bg-slate-950/60 rounded px-1 overflow-hidden border border-slate-800/40">
            <div
              className={`absolute h-3.5 rounded transition-all flex items-center px-1.5 ${
                isError
                  ? "bg-red-500/80 shadow-sm shadow-red-900/50"
                  : "bg-cyan-500/80 shadow-sm shadow-cyan-900/50"
              }`}
              style={{
                left: `${leftPct}%`,
                width: `${widthPct}%`,
                minWidth: "6px",
              }}
            >
              <span className="text-[9px] font-mono text-slate-950 font-bold whitespace-nowrap overflow-hidden">
                {node.duration_ms.toFixed(1)}ms
              </span>
            </div>
          </div>
        </div>

        {/* Recursive Children */}
        {hasChildren && isExpanded && node.children.map((child) => renderSpanRow(child, depth + 1))}
      </React.Fragment>
    );
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/80 backdrop-blur-sm flex justify-end animate-in fade-in duration-200">
      <div className="w-full max-w-4xl bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col h-full">
        {/* Drawer Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/50">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-cyan-950/80 border border-cyan-700/60 flex items-center justify-center text-cyan-400">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="font-semibold text-slate-100 text-sm">Trace Waterfall Details</h3>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-cyan-400 border border-slate-700">
                  {tree.total_spans} Spans
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                  {tree.total_duration_ms.toFixed(1)} ms
                </span>
              </div>
              <div className="flex items-center space-x-2 mt-0.5">
                <span className="text-xs font-mono text-slate-400">{tree.trace_id}</span>
                <button
                  onClick={handleCopyTraceId}
                  className="text-slate-500 hover:text-slate-300 transition-colors"
                  title="Copy Trace ID"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-md text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Split: Upper Waterfall Timeline / Lower Details Inspector */}
        <div className="flex-1 overflow-y-auto flex flex-col">
          {/* Upper: Waterfall Gantt Chart */}
          <div className="p-4 border-b border-slate-800/80 bg-slate-950/30">
            <div className="flex justify-between text-[10px] text-slate-500 font-mono mb-2 px-3">
              <span>SPAN NAME & SERVICE</span>
              <span>TIMELINE: 0 ms — {tree.total_duration_ms.toFixed(1)} ms</span>
            </div>
            <div className="bg-slate-900/90 rounded-lg border border-slate-800/80 overflow-hidden">
              {tree.root ? renderSpanRow(tree.root) : <div className="p-4 text-xs text-slate-500">No spans found</div>}
            </div>
          </div>

          {/* Lower: Span Detail Inspector */}
          {activeSpan && (
            <div className="p-5 flex-1 bg-slate-900/60 overflow-y-auto">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h4 className="font-semibold text-slate-200 text-sm flex items-center space-x-2">
                    <span>{activeSpan.name}</span>
                    {activeSpan.status === "ERROR" ? (
                      <span className="flex items-center text-[10px] text-red-400 font-mono bg-red-950/80 px-2 py-0.5 rounded border border-red-800">
                        <AlertCircle className="w-3 h-3 mr-1" /> ERROR
                      </span>
                    ) : (
                      <span className="flex items-center text-[10px] text-emerald-400 font-mono bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-800">
                        <CheckCircle2 className="w-3 h-3 mr-1" /> OK
                      </span>
                    )}
                  </h4>
                  <p className="text-xs font-mono text-slate-400 mt-0.5">
                    Service: {activeSpan.service} • Span ID: {activeSpan.span_id}
                  </p>
                </div>

                <div className="text-right">
                  <div className="text-xs font-mono text-cyan-400 font-bold">{activeSpan.duration_ms.toFixed(1)} ms</div>
                  <div className="text-[10px] font-mono text-slate-500">
                    +{activeSpan.relative_start_ms.toFixed(1)} ms offset
                  </div>
                </div>
              </div>

              {/* GenAI Metadata Badges */}
              {(activeSpan.model || activeSpan.input_tokens > 0) && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
                  <div className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800">
                    <span className="text-[10px] text-slate-500 uppercase font-mono block">Model</span>
                    <span className="text-xs font-mono text-slate-200 font-medium">{activeSpan.model || "—"}</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800">
                    <span className="text-[10px] text-slate-500 uppercase font-mono block">Prompt Ver</span>
                    <span className="text-xs font-mono text-cyan-400 font-medium">{activeSpan.prompt_version || "—"}</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800">
                    <span className="text-[10px] text-slate-500 uppercase font-mono block">Input Tokens</span>
                    <span className="text-xs font-mono text-slate-200 font-medium">{activeSpan.input_tokens}</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800">
                    <span className="text-[10px] text-slate-500 uppercase font-mono block">Output Tokens</span>
                    <span className="text-xs font-mono text-slate-200 font-medium">{activeSpan.output_tokens}</span>
                  </div>
                </div>
              )}

              {/* Events: Prompts & Completions (PII Masked) */}
              {activeSpan.events && activeSpan.events.length > 0 && (
                <div className="mb-4">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-semibold text-slate-300 flex items-center space-x-1.5">
                      <FileCode2 className="w-3.5 h-3.5 text-cyan-400" />
                      <span>Span Events (Prompt & Completion)</span>
                    </span>
                    <span className="flex items-center text-[10px] text-emerald-400 font-mono bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800/60">
                      <ShieldCheck className="w-3 h-3 mr-1" /> PII Masked & 4KB Truncated
                    </span>
                  </div>
                  <div className="space-y-2">
                    {activeSpan.events.map((ev, idx) => (
                      <div key={idx} className="p-3 rounded-lg bg-slate-950 border border-slate-800 font-mono text-xs">
                        <div className="text-[10px] text-cyan-400 font-bold mb-1 uppercase tracking-wider">{ev.name}</div>
                        <div className="text-slate-300 whitespace-pre-wrap break-words">{ev.content || JSON.stringify(ev)}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Attributes Key-Value Table */}
              <div>
                <span className="text-xs font-semibold text-slate-300 block mb-1.5">Span Attributes</span>
                <div className="bg-slate-950 rounded-lg border border-slate-800 overflow-hidden">
                  <table className="w-full text-left text-xs font-mono">
                    <tbody>
                      {Object.entries(activeSpan.attributes || {}).map(([key, val]) => (
                        <tr key={key} className="border-b border-slate-800/60 last:border-0 hover:bg-slate-900/40">
                          <td className="p-2 text-slate-400 w-1/3 truncate" title={key}>{key}</td>
                          <td className="p-2 text-slate-200 break-all">{val}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
