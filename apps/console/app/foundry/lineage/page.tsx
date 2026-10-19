"use client";

import { Suspense, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { fetchPropertyLineage, fetchObjects } from "@/lib/api";
import { PropertyLineageResponse } from "@/lib/types";
import {
  GitBranch,
  Layers,
  Clock,
  ArrowRight,
  Database,
  RefreshCw,
  Search,
  CheckCircle2,
} from "lucide-react";

function LineageContent() {
  const searchParams = useSearchParams();
  const { currentUser, getAuthHeaders } = useAuth();

  const [type, setType] = useState(searchParams?.get("type") || "Supplier");
  const [objectId, setObjectId] = useState(searchParams?.get("id") || "");
  const [property, setProperty] = useState(searchParams?.get("prop") || "name");

  const [lineageData, setLineageData] = useState<PropertyLineageResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // If no initial objectId, discover one automatically
  useEffect(() => {
    async function findInitialId() {
      if (!objectId) {
        try {
          const res = await fetchObjects(type, { limit: 1 }, getAuthHeaders());
          if (res.items.length > 0) {
            setObjectId(res.items[0].id);
          }
        } catch {}
      }
    }
    findInitialId();
  }, [type]);

  const loadLineage = async () => {
    if (!objectId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchPropertyLineage(type, objectId, property, getAuthHeaders());
      setLineageData(res);
    } catch (err: any) {
      setError(err.message || "Failed to load property lineage");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (objectId) {
      loadLineage();
    }
  }, [objectId, property, currentUser]);

  return (
    <div className="space-y-6">
      {/* Parameter Control Bar */}
      <div className="glass-panel rounded-xl p-4 space-y-3">
        <span className="text-xs font-mono text-slate-400 uppercase tracking-wider block">
          Lineage Target Selector
        </span>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <div>
            <label className="text-[11px] text-slate-400 block mb-1">Object Type</label>
            <select
              value={type}
              onChange={(e) => {
                setType(e.target.value);
                setObjectId("");
              }}
              className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="Supplier">Supplier</option>
              <option value="Part">Part</option>
              <option value="PurchaseOrder">PurchaseOrder</option>
              <option value="Shipment">Shipment</option>
              <option value="QualityIncident">QualityIncident</option>
            </select>
          </div>

          <div className="sm:col-span-2">
            <label className="text-[11px] text-slate-400 block mb-1">Entity UUID</label>
            <input
              type="text"
              placeholder="e.g. 227e998d-599d-41e8-bd51-..."
              value={objectId}
              onChange={(e) => setObjectId(e.target.value)}
              className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
            />
          </div>

          <div>
            <label className="text-[11px] text-slate-400 block mb-1">Property</label>
            <div className="flex space-x-2">
              <input
                type="text"
                value={property}
                onChange={(e) => setProperty(e.target.value)}
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
              />
              <button
                onClick={loadLineage}
                disabled={loading || !objectId}
                className="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-slate-950 text-xs font-semibold flex items-center space-x-1 shrink-0 disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
                <span>Fetch</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-200 text-xs font-mono">
          {error}
        </div>
      )}

      {/* Main Lineage Display */}
      {lineageData ? (
        <div className="space-y-6">
          {/* OpenLineage DAG Transform Flow */}
          <div className="glass-panel rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center space-x-2">
                <GitBranch className="w-4 h-4 text-cyan-400" />
                <span className="font-bold text-slate-200 text-xs uppercase tracking-wider">
                  OpenLineage Transformation DAG
                </span>
              </div>
              <span className="text-[11px] font-mono text-slate-400">
                Target Property: <span className="text-cyan-400 font-semibold">{property}</span> = &quot;{lineageData.current_value}&quot;
              </span>
            </div>

            {/* Visual DAG Nodes */}
            <div className="py-8 flex flex-col md:flex-row items-center justify-center gap-6">
              {/* Node 1: Input Datasets */}
              <div className="w-56 rounded-xl bg-slate-900 border border-slate-800 p-4 text-center space-y-2 shadow-lg">
                <div className="w-8 h-8 rounded-lg bg-blue-950/80 border border-blue-700/60 mx-auto flex items-center justify-center">
                  <Database className="w-4 h-4 text-blue-400" />
                </div>
                <div className="text-xs font-bold text-slate-200">
                  {lineageData.transforms[0]?.input_dataset || "raw_landing_zone"}
                </div>
                <span className="text-[10px] font-mono text-slate-500 block">MinIO S3 / ERP Dump</span>
              </div>

              {/* Arrow */}
              <div className="flex flex-col items-center">
                <ArrowRight className="w-5 h-5 text-slate-600 hidden md:block" />
                <span className="text-[10px] font-mono text-slate-500">extract / clean</span>
              </div>

              {/* Node 2: Transform Job */}
              <div className="w-64 rounded-xl bg-cyan-950/30 border border-cyan-800/80 p-4 text-center space-y-2 shadow-lg shadow-cyan-950/50">
                <div className="w-8 h-8 rounded-lg bg-cyan-900/60 border border-cyan-500 mx-auto flex items-center justify-center">
                  <Layers className="w-4 h-4 text-cyan-300" />
                </div>
                <div className="text-xs font-bold text-cyan-300">
                  {lineageData.transforms[0]?.transform || "Splink ER + Codegen Promotion"}
                </div>
                <div className="text-[10px] font-mono text-cyan-500 truncate">
                  Run ID: {lineageData.transforms[0]?.run_id || "run_latest"}
                </div>
              </div>

              {/* Arrow */}
              <div className="flex flex-col items-center">
                <ArrowRight className="w-5 h-5 text-slate-600 hidden md:block" />
                <span className="text-[10px] font-mono text-slate-500">load / promote</span>
              </div>

              {/* Node 3: Target Ontology Object */}
              <div className="w-56 rounded-xl bg-slate-900 border border-emerald-800/60 p-4 text-center space-y-2 shadow-lg">
                <div className="w-8 h-8 rounded-lg bg-emerald-950/80 border border-emerald-700 mx-auto flex items-center justify-center">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="text-xs font-bold text-emerald-300">
                  {lineageData.transforms[0]?.output_dataset || lineageData.object_type}
                </div>
                <span className="text-[10px] font-mono text-slate-500 block">Postgres RLS Ontology Store</span>
              </div>
            </div>
          </div>

          {/* Provenance Audit History Table */}
          <div className="glass-panel rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-slate-800 flex items-center justify-between text-xs text-slate-400">
              <span className="font-bold uppercase tracking-wider text-slate-300">
                Property Evolution & Survivorship History ({lineageData.provenance_count})
              </span>
              <span className="font-mono text-slate-500">Ordered by recorded_at DESC</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-900/60 border-b border-slate-800 text-[11px] font-mono text-slate-400">
                  <tr>
                    <th className="py-2.5 px-4 font-medium">Recorded Value</th>
                    <th className="py-2.5 px-4 font-medium">Source System</th>
                    <th className="py-2.5 px-4 font-medium">Source Row Ref</th>
                    <th className="py-2.5 px-4 font-medium">Survivorship Rule</th>
                    <th className="py-2.5 px-4 font-medium">Ingest Run</th>
                    <th className="py-2.5 px-4 font-medium">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                  {lineageData.history.map((h, i) => (
                    <tr key={h.id || i} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 px-4 font-semibold text-cyan-300 font-sans text-xs">
                        {String(h.value)}
                      </td>
                      <td className="py-3 px-4 text-slate-300">{h.source_id}</td>
                      <td className="py-3 px-4 text-slate-400">{h.source_row_ref}</td>
                      <td className="py-3 px-4 text-amber-300 font-sans text-xs">{h.rule_applied}</td>
                      <td className="py-3 px-4 text-slate-400">{h.run_id}</td>
                      <td className="py-3 px-4 text-slate-500">
                        {new Date(h.recorded_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        <div className="glass-panel rounded-xl p-12 text-center text-slate-500 text-xs">
          Select an entity UUID above to visualize the complete transformation DAG and property audit trail.
        </div>
      )}
    </div>
  );
}

export default function LineagePage() {
  return (
    <Suspense
      fallback={
        <div className="glass-panel rounded-xl p-16 text-center text-slate-500 text-xs flex flex-col items-center justify-center space-y-2">
          <RefreshCw className="w-6 h-6 animate-spin text-cyan-400" />
          <span>Loading Property Lineage...</span>
        </div>
      }
    >
      <LineageContent />
    </Suspense>
  );
}
