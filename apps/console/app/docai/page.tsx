"use client";

import { useState } from "react";
import Link from "next/link";
import {
  FileText,
  Truck,
  Scale,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Upload,
  ArrowRight,
  Filter,
  Search,
  Sparkles,
  GitCompare,
  FileCheck,
} from "lucide-react";
import { MOCK_DOCAI_DOCUMENTS } from "@/lib/docai-data";
import { DocAIDocument } from "@/lib/types";

export default function DocAIPage() {
  const [documents, setDocuments] = useState<DocAIDocument[]>(MOCK_DOCAI_DOCUMENTS);
  const [activeTab, setActiveTab] = useState<"all" | "delivery_note" | "contract">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);

  const filteredDocs = documents.filter((doc) => {
    if (activeTab !== "all" && doc.document_type !== activeTab) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return (
        doc.filename.toLowerCase().includes(q) ||
        doc.document_id.toLowerCase().includes(q) ||
        (doc.plant && doc.plant.toLowerCase().includes(q))
      );
    }
    return true;
  });

  const handleSimulateUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setUploadStatus(`Uploading ${file.name} (Validating magic bytes: application/pdf)...`);
      setTimeout(() => {
        const newDoc: DocAIDocument = {
          document_id: `DOC-NEW-${Math.floor(1000 + Math.random() * 9000)}`,
          filename: file.name,
          mime_type: "application/pdf",
          file_size_bytes: file.size,
          document_type: file.name.toLowerCase().includes("vertrag") || file.name.toLowerCase().includes("contract") ? "contract" : "delivery_note",
          status: "auto_accepted",
          plant: "DE-HAM",
          created_at: new Date().toISOString(),
          confidence: 0.978,
          page_count: 1,
        };
        setDocuments([newDoc, ...documents]);
        setUploadStatus(`✓ Verified magic bytes! Queued and auto-accepted in 0.42s`);
        setTimeout(() => setUploadStatus(null), 4000);
      }, 1200);
    }
  };

  const getStatusBadge = (status: DocAIDocument["status"]) => {
    switch (status) {
      case "auto_accepted":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-950/60 text-emerald-400 border border-emerald-800/80">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            Auto-Accepted (Donut)
          </span>
        );
      case "review_required":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-950/60 text-amber-300 border border-amber-800/80">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
            Review Queue
          </span>
        );
      case "completed":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-cyan-950/60 text-cyan-400 border border-cyan-800/80">
            <FileCheck className="w-3.5 h-3.5 text-cyan-400" />
            Ingested to ERP
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            Processing
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header Banner */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-cyan-900/40 border border-cyan-400/40">
                <FileText className="w-5 h-5 text-slate-950" />
              </div>
              <div>
                <h1 className="text-xl md:text-2xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
                  Contract & Document Intelligence Engine
                  <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-cyan-950 border border-cyan-800 text-cyan-400">
                    P4 DOCAI
                  </span>
                </h1>
                <p className="text-xs md:text-sm text-slate-400">
                  Automated OCR, Donut extraction, CUAD clause segmentation, and deterministic legal playbook auditing.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/docai/diff"
              className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-800 text-xs font-medium transition-colors"
            >
              <GitCompare className="w-4 h-4 text-cyan-400" />
              Version Redline Diff
            </Link>

            <label className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-slate-950 font-semibold text-xs cursor-pointer shadow-lg shadow-cyan-950/50 transition-all">
              <Upload className="w-4 h-4 text-slate-950" />
              Upload Document
              <input
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.tiff"
                className="hidden"
                onChange={handleSimulateUpload}
              />
            </label>
          </div>
        </div>

        {uploadStatus && (
          <div className="p-3.5 rounded-lg bg-cyan-950/60 border border-cyan-800 text-cyan-300 text-xs font-mono flex items-center gap-2 animate-fadeIn">
            <Sparkles className="w-4 h-4 text-cyan-400 animate-spin" />
            {uploadStatus}
          </div>
        )}

        {/* Operational KPI Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800/80">
            <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
              <span>DAILY DEPOT INTAKE</span>
              <Truck className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="mt-2 text-2xl font-bold text-slate-100">312</div>
            <div className="mt-1 text-[11px] text-emerald-400 flex items-center gap-1 font-mono">
              <span>✓ 83.3% Auto-Accepted (Donut)</span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800/80">
            <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
              <span>ACTIVE CONTRACTS</span>
              <Scale className="w-4 h-4 text-indigo-400" />
            </div>
            <div className="mt-2 text-2xl font-bold text-slate-100">1,840</div>
            <div className="mt-1 text-[11px] text-cyan-400 font-mono">
              <span>Plant Wrocław (PL-WRO)</span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800/80">
            <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
              <span>SPAN GROUNDING ACCURACY</span>
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="mt-2 text-2xl font-bold text-emerald-400">100.0%</div>
            <div className="mt-1 text-[11px] text-slate-400 font-mono">
              <span>Exact substring alignment</span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800/80">
            <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
              <span>PLAYBOOK RISK RECALL</span>
              <AlertTriangle className="w-4 h-4 text-amber-400" />
            </div>
            <div className="mt-2 text-2xl font-bold text-amber-300">90.0%</div>
            <div className="mt-1 text-[11px] text-amber-400 font-mono">
              <span>halden_v1.yaml compliance</span>
            </div>
          </div>
        </div>

        {/* Filter Tabs & Search Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center space-x-1 p-1 rounded-lg bg-slate-900 border border-slate-800">
            <button
              onClick={() => setActiveTab("all")}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                activeTab === "all"
                  ? "bg-slate-800 text-cyan-400 shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              All Documents ({documents.length})
            </button>
            <button
              onClick={() => setActiveTab("delivery_note")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                activeTab === "delivery_note"
                  ? "bg-slate-800 text-cyan-400 shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Truck className="w-3.5 h-3.5" />
              Delivery Notes ({documents.filter((d) => d.document_type === "delivery_note").length})
            </button>
            <button
              onClick={() => setActiveTab("contract")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                activeTab === "contract"
                  ? "bg-slate-800 text-cyan-400 shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Scale className="w-3.5 h-3.5" />
              Contracts ({documents.filter((d) => d.document_type === "contract").length})
            </button>
          </div>

          <div className="relative w-full sm:w-72">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              placeholder="Search filename, ID, or plant..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-1.5 rounded-lg bg-slate-900/90 border border-slate-800 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
            />
          </div>
        </div>

        {/* Documents Table */}
        <div className="rounded-xl bg-slate-900/80 border border-slate-800 overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950/60 border-b border-slate-800 font-mono uppercase text-slate-400 text-[11px]">
                <tr>
                  <th className="py-3 px-4">Document</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Depot / Plant</th>
                  <th className="py-3 px-4">Confidence</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-sans">
                {filteredDocs.map((doc) => (
                  <tr key={doc.document_id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-3.5 px-4">
                      <div className="font-semibold text-slate-100 flex items-center gap-2">
                        {doc.document_type === "delivery_note" ? (
                          <Truck className="w-4 h-4 text-cyan-400 shrink-0" />
                        ) : (
                          <Scale className="w-4 h-4 text-indigo-400 shrink-0" />
                        )}
                        <span>{doc.filename}</span>
                      </div>
                      <div className="text-[11px] font-mono text-slate-500 mt-0.5">
                        {doc.document_id} • {(doc.file_size_bytes / 1024).toFixed(0)} KB • {doc.page_count} page(s)
                      </div>
                    </td>

                    <td className="py-3.5 px-4 font-mono capitalize text-slate-300">
                      {doc.document_type.replace("_", " ")}
                    </td>

                    <td className="py-3.5 px-4 font-mono">
                      <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 text-[11px]">
                        {doc.plant || "Global"}
                      </span>
                    </td>

                    <td className="py-3.5 px-4 font-mono">
                      {doc.confidence ? (
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-2 rounded-full bg-slate-800 overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                doc.confidence >= 0.90 ? "bg-emerald-400" : "bg-amber-400"
                              }`}
                              style={{ width: `${doc.confidence * 100}%` }}
                            />
                          </div>
                          <span className="text-[11px] text-slate-300">
                            {(doc.confidence * 100).toFixed(1)}%
                          </span>
                        </div>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>

                    <td className="py-3.5 px-4">{getStatusBadge(doc.status)}</td>

                    <td className="py-3.5 px-4 text-right">
                      <Link
                        href={`/docai/${doc.document_id}`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-cyan-950 hover:text-cyan-400 border border-slate-700 hover:border-cyan-800 text-xs font-medium text-slate-200 transition-all"
                      >
                        Inspect & Review
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
