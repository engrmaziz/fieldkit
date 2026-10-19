"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { fetchObjectDetail, fetchNeighbors } from "@/lib/api";
import { ObjectDetailResponse, NeighborsResponse } from "@/lib/types";
import {
  ArrowLeft,
  Network,
  GitBranch,
  Building,
  Info,
  Clock,
  Layers,
  ChevronRight,
  RefreshCw,
  ExternalLink,
} from "lucide-react";

export default function ObjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { currentUser, getAuthHeaders } = useAuth();

  const objectType = params.type as string;
  const objectId = params.id as string;

  const [data, setData] = useState<ObjectDetailResponse | null>(null);
  const [neighbors, setNeighbors] = useState<NeighborsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Popover state for hovered property
  const [hoveredProp, setHoveredProp] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const headers = getAuthHeaders();
        const [objRes, neighborRes] = await Promise.all([
          fetchObjectDetail(objectType, objectId, headers),
          fetchNeighbors(objectType, objectId, 1, undefined, headers).catch(() => null),
        ]);
        setData(objRes);
        setNeighbors(neighborRes);
      } catch (err: any) {
        setError(err.message || "Failed to load object details");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [objectType, objectId, currentUser]);

  if (loading) {
    return (
      <div className="p-16 text-center text-slate-500 text-xs flex flex-col items-center justify-center space-y-3">
        <RefreshCw className="w-6 h-6 animate-spin text-cyan-400" />
        <span>Loading {objectType} properties and provenance metadata...</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="glass-panel rounded-xl p-8 text-center space-y-4">
        <div className="text-rose-400 font-bold text-sm">Failed to Load Object</div>
        <p className="text-xs text-slate-400 font-mono">{error}</p>
        <button
          onClick={() => router.push("/foundry/explorer")}
          className="px-4 py-2 rounded-lg bg-slate-800 text-slate-200 text-xs hover:bg-slate-700 transition-colors inline-flex items-center space-x-2"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Explorer</span>
        </button>
      </div>
    );
  }

  const obj = data.object;
  const provenance = data.provenance || {};

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800/80">
        <div className="flex items-center space-x-3">
          <Link
            href="/foundry/explorer"
            className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-cyan-950 border border-cyan-800 text-cyan-400 font-semibold uppercase">
                {objectType}
              </span>
              <h2 className="text-lg font-bold text-slate-100">
                {obj.name || obj.part_number || obj.po_number || obj.natural_key}
              </h2>
            </div>
            <span className="text-[11px] font-mono text-slate-500">UUID: {objectId}</span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center space-x-2">
          <Link
            href={`/foundry/graph?focus=${objectId}&type=${objectType}`}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-cyan-700 text-xs text-slate-300 hover:text-cyan-400 transition-colors"
          >
            <Network className="w-3.5 h-3.5" />
            <span>Graph View</span>
          </Link>
          <Link
            href={`/foundry/lineage?type=${objectType}&id=${objectId}&prop=name`}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-cyan-950/80 border border-cyan-800 text-xs text-cyan-300 hover:bg-cyan-900/60 transition-colors"
          >
            <GitBranch className="w-3.5 h-3.5" />
            <span>Lineage DAG</span>
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Properties with Provenance Hover */}
        <div className="lg:col-span-2 glass-panel rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-800 flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
              Resolved Entity Properties
            </span>
            <span className="text-[11px] text-slate-500 font-mono">
              Hover value to inspect provenance
            </span>
          </div>

          <div className="divide-y divide-slate-800/60">
            {Object.entries(obj).map(([key, val]) => {
              const prov = provenance[key];
              const isHovered = hoveredProp === key;

              return (
                <div
                  key={key}
                  className="px-5 py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2 hover:bg-slate-800/30 transition-colors relative"
                  onMouseEnter={() => setHoveredProp(key)}
                  onMouseLeave={() => setHoveredProp(null)}
                >
                  <div className="w-48 font-mono text-xs text-slate-400">{key}</div>

                  <div className="flex-1 flex items-center justify-between gap-4">
                    <span className="text-xs font-semibold text-slate-200">
                      {val === null || val === undefined ? (
                        <span className="text-slate-600 italic">null</span>
                      ) : typeof val === "object" ? (
                        JSON.stringify(val)
                      ) : (
                        String(val)
                      )}
                    </span>

                    {prov ? (
                      <div className="relative">
                        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-950/70 border border-cyan-800/80 text-cyan-300 cursor-help">
                          <Layers className="w-2.5 h-2.5" />
                          <span>{prov.source_id}</span>
                        </span>

                        {/* Provenance Popover on Hover */}
                        {isHovered && (
                          <div className="absolute right-0 bottom-full mb-2 w-72 rounded-lg bg-slate-900 border border-cyan-800 shadow-2xl p-3 z-50 text-[11px] text-slate-300 space-y-1.5 animate-in fade-in zoom-in-95 duration-150">
                            <div className="font-bold text-cyan-400 flex items-center justify-between border-b border-slate-800 pb-1">
                              <span>Field-Level Provenance</span>
                              <span className="text-[9px] font-mono text-slate-500">SURVIVORSHIP</span>
                            </div>
                            <div>
                              <span className="text-slate-400">Source: </span>
                              <span className="font-mono text-white font-semibold">{prov.source_id}</span>
                            </div>
                            <div>
                              <span className="text-slate-400">Row Ref: </span>
                              <span className="font-mono text-slate-200">{prov.source_row_ref}</span>
                            </div>
                            <div>
                              <span className="text-slate-400">Ingest Run: </span>
                              <span className="font-mono text-cyan-300">{prov.run_id}</span>
                            </div>
                            <div>
                              <span className="text-slate-400">Rule Applied: </span>
                              <span className="font-mono text-amber-300">{prov.rule}</span>
                            </div>
                            <div className="pt-1 border-t border-slate-800 text-[10px] text-slate-500 flex items-center space-x-1">
                              <Clock className="w-3 h-3" />
                              <span>{new Date(prov.recorded_at).toLocaleString()}</span>
                            </div>
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="text-[10px] font-mono text-slate-600">Generated</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Plant Metadata & Connected Neighbors */}
        <div className="space-y-6">
          {/* Plant Scope Card */}
          <div className="glass-panel rounded-xl p-5 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Plant Partitioning (RLS)
              </span>
              <Building className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="text-xs text-slate-400">
              {obj.plant ? (
                <div>
                  This record is scoped to plant{" "}
                  <span className="font-mono font-bold text-cyan-300">{obj.plant}</span>. Users without{" "}
                  {obj.plant} authorization or global admin privileges are restricted by Postgres Row-Level
                  Security.
                </div>
              ) : (
                <div>
                  This record has <span className="font-mono font-bold text-amber-300">Global</span> scope
                  and is accessible across all Halden Industrie plants.
                </div>
              )}
            </div>
          </div>

          {/* Connected Neighbors Card */}
          <div className="glass-panel rounded-xl p-5 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Direct Neighbors ({neighbors?.count ?? 0})
              </span>
              <Link
                href={`/foundry/graph?focus=${objectId}&type=${objectType}`}
                className="text-[11px] text-cyan-400 hover:text-cyan-300 flex items-center space-x-1"
              >
                <span>Expand in Graph</span>
                <ExternalLink className="w-3 h-3" />
              </Link>
            </div>

            {!neighbors || neighbors.neighbors.length === 0 ? (
              <p className="text-xs text-slate-500 italic py-2">
                No direct link neighbors discovered under active RLS credentials.
              </p>
            ) : (
              <div className="space-y-2">
                {neighbors.neighbors.slice(0, 5).map((n, idx) => (
                  <Link
                    key={idx}
                    href={`/foundry/objects/${n.target_type}/${n.object.id}`}
                    className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 hover:border-slate-700 flex items-center justify-between group transition-colors block text-xs"
                  >
                    <div>
                      <div className="flex items-center space-x-1.5">
                        <span className="text-[10px] font-mono px-1 rounded bg-slate-800 text-slate-400">
                          {n.link}
                        </span>
                        <span className="font-semibold text-slate-200 group-hover:text-cyan-400 transition-colors">
                          {n.object.name || n.object.part_number || n.object.po_number || n.object.natural_key}
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-500 font-mono">
                        {n.target_type} {n.object.plant ? `• ${n.object.plant}` : ""}
                      </span>
                    </div>
                    <ChevronRight className="w-3.5 h-3.5 text-slate-600 group-hover:text-cyan-400 transition-colors" />
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
