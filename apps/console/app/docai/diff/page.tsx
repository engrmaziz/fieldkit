"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  GitCompare,
  AlertTriangle,
  CheckCircle2,
  MinusCircle,
  PlusCircle,
  FileText,
  ShieldAlert,
} from "lucide-react";
import { MOCK_CONTRACT_DIFF_ITEMS } from "@/lib/docai-data";
import { ContractDiffItem } from "@/lib/types";

export default function ContractDiffPage() {
  const [diffItems] = useState<ContractDiffItem[]>(MOCK_CONTRACT_DIFF_ITEMS);
  const [filter, setFilter] = useState<"all" | "modified" | "material">("all");

  const filteredItems = diffItems.filter((item) => {
    if (filter === "modified") return item.status !== "UNCHANGED";
    if (filter === "material") return item.is_material;
    return true;
  });

  const unchangedCount = diffItems.filter((i) => i.status === "UNCHANGED").length;
  const modifiedCount = diffItems.filter((i) => i.status === "MODIFIED").length;
  const addedCount = diffItems.filter((i) => i.status === "ADDED").length;
  const deletedCount = diffItems.filter((i) => i.status === "DELETED").length;
  const materialCount = diffItems.filter((i) => i.is_material).length;

  const renderRedlineDiff = (textDiff: string) => {
    // Highlight [- ... -] in red and [+ ... +] in green
    const parts = textDiff.split(/(\[-\s*.*?\s*-\]|\[\+\s*.*?\s*\+\])/g);
    return (
      <span className="font-mono text-xs leading-relaxed">
        {parts.map((part, index) => {
          if (part.startsWith("[-") && part.endsWith("-]")) {
            const content = part.slice(2, -2).trim();
            return (
              <span
                key={index}
                className="bg-rose-950/80 text-rose-300 line-through px-1.5 py-0.5 rounded mx-0.5 border border-rose-800"
              >
                {content}
              </span>
            );
          } else if (part.startsWith("[+") && part.endsWith("+]")) {
            const content = part.slice(2, -2).trim();
            return (
              <span
                key={index}
                className="bg-emerald-950/80 text-emerald-300 font-semibold px-1.5 py-0.5 rounded mx-0.5 border border-emerald-800"
              >
                {content}
              </span>
            );
          }
          return <span key={index}>{part}</span>;
        })}
      </span>
    );
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div className="flex items-center gap-3">
            <Link
              href="/docai"
              className="p-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-800 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <div>
              <div className="flex items-center gap-2">
                <GitCompare className="w-5 h-5 text-cyan-400" />
                <h1 className="text-xl md:text-2xl font-bold tracking-tight text-slate-100">
                  Contract Version Redline Diff (Hungarian Alignment)
                </h1>
                <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-cyan-950 border border-cyan-800 text-cyan-400">
                  P4 M5
                </span>
              </div>
              <p className="text-xs md:text-sm text-slate-400 mt-1">
                Comparing <span className="text-slate-200 font-semibold">Halden Standard v1.0</span> vs{" "}
                <span className="text-slate-200 font-semibold">Supplier Redline Markup v2.0</span> (Knorr-Bremse, PL-WRO)
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-emerald-400 bg-emerald-950/60 border border-emerald-800 px-3 py-1.5 rounded-lg flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Optimal Hungarian Alignment: 100% Paired
            </span>
          </div>
        </div>

        {/* Diff KPI Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
            <div className="text-[11px] font-mono text-slate-400">UNCHANGED</div>
            <div className="text-xl font-bold text-slate-100 mt-1">{unchangedCount}</div>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
            <div className="text-[11px] font-mono text-amber-400">MODIFIED</div>
            <div className="text-xl font-bold text-amber-300 mt-1">{modifiedCount}</div>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
            <div className="text-[11px] font-mono text-rose-400">DELETED</div>
            <div className="text-xl font-bold text-rose-300 mt-1">{deletedCount}</div>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
            <div className="text-[11px] font-mono text-emerald-400">ADDED</div>
            <div className="text-xl font-bold text-emerald-300 mt-1">{addedCount}</div>
          </div>

          <div className="p-3.5 rounded-xl bg-rose-950/40 border border-rose-800/80">
            <div className="text-[11px] font-mono text-rose-300 font-bold flex items-center gap-1">
              <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
              MATERIAL RISKS
            </div>
            <div className="text-xl font-bold text-rose-400 mt-1">{materialCount}</div>
          </div>
        </div>

        {/* Filter buttons */}
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setFilter("all")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              filter === "all" ? "bg-slate-800 text-cyan-400 shadow-sm" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            All Clauses ({diffItems.length})
          </button>
          <button
            onClick={() => setFilter("modified")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              filter === "modified" ? "bg-slate-800 text-cyan-400 shadow-sm" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Edits & Changes Only ({diffItems.length - unchangedCount})
          </button>
          <button
            onClick={() => setFilter("material")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              filter === "material" ? "bg-rose-950 text-rose-300 border border-rose-800" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
            Material Legal Risks Only ({materialCount})
          </button>
        </div>

        {/* Diff Items List */}
        <div className="space-y-4">
          {filteredItems.map((item, idx) => (
            <div
              key={idx}
              className={`p-5 rounded-xl border transition-all ${
                item.is_material
                  ? "bg-slate-900/90 border-rose-800/70 shadow-lg shadow-rose-950/20"
                  : "bg-slate-900/70 border-slate-800"
              }`}
            >
              {/* Card Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-slate-200 text-sm">
                    Section {item.section_v1 || item.section_v2 || `Item ${idx + 1}`}
                  </span>
                  {item.status === "UNCHANGED" && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-400 border border-slate-700">
                      UNCHANGED
                    </span>
                  )}
                  {item.status === "MODIFIED" && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-950/80 text-amber-300 border border-amber-800">
                      MODIFIED ({(item.similarity_score * 100).toFixed(0)}% Match)
                    </span>
                  )}
                  {item.status === "DELETED" && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-rose-950/80 text-rose-300 border border-rose-800 flex items-center gap-1">
                      <MinusCircle className="w-3 h-3" />
                      DELETED IN REV 2
                    </span>
                  )}
                  {item.status === "ADDED" && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-950/80 text-emerald-300 border border-emerald-800 flex items-center gap-1">
                      <PlusCircle className="w-3 h-3" />
                      ADDED IN REV 2
                    </span>
                  )}
                </div>

                {item.is_material && (
                  <span
                    className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase ${
                      item.severity === "CRITICAL"
                        ? "bg-rose-950 text-rose-400 border border-rose-800"
                        : "bg-amber-950 text-amber-300 border border-amber-800"
                    }`}
                  >
                    ⚠ MATERIAL RISK: {item.severity}
                  </span>
                )}
              </div>

              {/* Material Risk Explanations */}
              {item.material_reasons.length > 0 && (
                <div className="mt-3 p-3 rounded-lg bg-rose-950/20 border border-rose-900/60 space-y-1">
                  <span className="text-[10px] font-mono font-bold text-rose-400 uppercase">
                    REDLINE RISK IMPACT (SOFIA SCHMIDT AUDIT):
                  </span>
                  <ul className="list-disc list-inside text-xs text-rose-200 space-y-0.5">
                    {item.material_reasons.map((r, rIdx) => (
                      <li key={rIdx}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Redline Text Display */}
              <div className="mt-4 p-4 rounded-lg bg-slate-950 border border-slate-800/80">
                {renderRedlineDiff(item.text_diff)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
