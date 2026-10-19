"use client";

import React, { useEffect } from "react";
import { ChunkCitation } from "@/lib/types";
import {
  X,
  FileText,
  Shield,
  MapPin,
  Check,
  Copy,
  ChevronRight,
  ExternalLink,
} from "lucide-react";

interface CitationDrawerProps {
  citation: ChunkCitation | null;
  isOpen: boolean;
  onClose: () => void;
}

export default function CitationDrawer({
  citation,
  isOpen,
  onClose,
}: CitationDrawerProps) {
  const [copied, setCopied] = React.useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) {
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !citation) return null;

  const handleCopyChunkId = () => {
    navigator.clipboard.writeText(citation.chunk_id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/70 backdrop-blur-sm flex justify-end transition-opacity duration-300">
      {/* Click outside to close */}
      <div className="flex-1" onClick={onClose} />

      {/* Slide-over panel */}
      <div className="w-full max-w-xl bg-[#0c1220] border-l border-slate-800 shadow-2xl flex flex-col h-full transform transition-transform duration-300 ease-out">
        {/* Drawer Header */}
        <div className="p-5 border-b border-slate-800 flex items-start justify-between bg-slate-900/60">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <span className="w-6 h-6 rounded-md bg-teal-950/80 border border-teal-600/50 flex items-center justify-center text-teal-300 text-xs font-mono font-bold">
                [{citation.citation_index}]
              </span>
              <span className="text-xs font-mono uppercase tracking-wider text-teal-400 font-semibold">
                RAG Authoritative Source
              </span>
            </div>
            <h2 className="text-base font-bold text-white leading-snug">
              {citation.title}
            </h2>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Heading Hierarchy Breadcrumb */}
        {citation.heading_path && citation.heading_path.length > 0 && (
          <div className="px-5 py-2.5 bg-slate-900/40 border-b border-slate-800/60 flex items-center space-x-1.5 text-xs text-slate-400 overflow-x-auto">
            <FileText className="w-3.5 h-3.5 text-slate-500 shrink-0" />
            {citation.heading_path.map((step, idx) => (
              <React.Fragment key={idx}>
                <span className="font-medium text-slate-300 whitespace-nowrap">
                  {step}
                </span>
                {idx < citation.heading_path.length - 1 && (
                  <ChevronRight className="w-3 h-3 text-slate-600 shrink-0" />
                )}
              </React.Fragment>
            ))}
          </div>
        )}

        {/* Drawer Body */}
        <div className="p-5 flex-1 overflow-y-auto space-y-5">
          {/* ACL Security Policy Meta */}
          <div className="p-3.5 rounded-lg bg-slate-900/80 border border-slate-800/90 space-y-2.5">
            <div className="text-[11px] font-mono uppercase text-slate-400 font-semibold tracking-wider">
              Document Access Control Policy (ACL)
            </div>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="flex items-start space-x-2">
                <Shield className="w-4 h-4 text-cyan-400 mt-0.5 shrink-0" />
                <div>
                  <span className="text-slate-400 text-[11px] block">
                    Authorized Roles:
                  </span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {citation.allowed_roles.map((role) => (
                      <span
                        key={role}
                        className="px-1.5 py-0.5 rounded bg-cyan-950/60 border border-cyan-800/60 text-cyan-300 font-mono text-[10px]"
                      >
                        {role}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="flex items-start space-x-2">
                <MapPin className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                <div>
                  <span className="text-slate-400 text-[11px] block">
                    Plant Scope:
                  </span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {citation.allowed_plants && citation.allowed_plants.length > 0 ? (
                      citation.allowed_plants.map((plant) => (
                        <span
                          key={plant}
                          className="px-1.5 py-0.5 rounded bg-emerald-950/60 border border-emerald-800/60 text-emerald-300 font-mono text-[10px]"
                        >
                          {plant}
                        </span>
                      ))
                    ) : (
                      <span className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 font-mono text-[10px]">
                        Global (All Plants)
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Chunk Identifier */}
          <div className="flex items-center justify-between text-xs px-3 py-2 rounded bg-slate-900/50 border border-slate-800/80 font-mono">
            <span className="text-slate-400">Chunk ID:</span>
            <div className="flex items-center space-x-2">
              <span className="text-slate-200 select-all font-semibold">
                {citation.chunk_id}
              </span>
              <button
                onClick={handleCopyChunkId}
                className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-800 transition-colors"
                title="Copy chunk ID"
              >
                {copied ? (
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
              </button>
            </div>
          </div>

          {/* Passage Content */}
          <div className="space-y-2">
            <div className="text-xs font-semibold text-slate-300 flex items-center justify-between">
              <span>Authoritative Grounding Passage</span>
              <span className="text-[11px] text-slate-400 font-normal">
                Verbatim Excerpt
              </span>
            </div>
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 text-sm leading-relaxed whitespace-pre-wrap font-sans selection:bg-teal-500/30 selection:text-teal-200">
              {citation.content}
            </div>
          </div>
        </div>

        {/* Drawer Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/80 flex justify-between items-center text-xs text-slate-400 font-mono">
          <span>Fieldkit Verified Corpus</span>
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium transition-colors"
          >
            Close Panel
          </button>
        </div>
      </div>
    </div>
  );
}
