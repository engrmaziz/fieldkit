"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { fetchObjects, executeTypedQuery } from "@/lib/api";
import { KeysetListResponse, OntologyObjectType } from "@/lib/types";
import {
  Search,
  Filter,
  Plus,
  Trash2,
  ChevronRight,
  RefreshCw,
  Eye,
  Network,
  Tag,
  Building,
} from "lucide-react";

const OBJECT_TYPES: OntologyObjectType[] = [
  "Supplier",
  "Part",
  "Plant",
  "PurchaseOrder",
  "Shipment",
  "QualityIncident",
  "Certificate",
];

const PROPS_BY_TYPE: Record<string, string[]> = {
  Supplier: ["name", "country", "supplier_code", "plant", "lei"],
  Part: ["name", "part_number", "category", "unit_cost", "plant"],
  Plant: ["name", "plant_code", "location", "country"],
  PurchaseOrder: ["po_number", "status", "total_amount", "currency", "plant"],
  Shipment: ["shipment_number", "tracking_number", "status", "plant"],
  QualityIncident: ["incident_number", "severity", "description", "plant"],
  Certificate: ["cert_number", "cert_type", "status"],
};

export default function ExplorerPage() {
  const { currentUser, getAuthHeaders } = useAuth();
  const [selectedType, setSelectedType] = useState<OntologyObjectType>("Supplier");
  const [searchTerm, setSearchTerm] = useState("");
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<string[]>([]);
  const [data, setData] = useState<KeysetListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Dynamic filter builder state
  const [filters, setFilters] = useState<Array<{ prop: string; op: string; value: string }>>([]);
  const [showFilterBuilder, setShowFilterBuilder] = useState(false);

  const loadData = useCallback(
    async (targetCursor?: string | null) => {
      setLoading(true);
      setError(null);
      try {
        const headers = getAuthHeaders();
        let result: KeysetListResponse;

        if (filters.length > 0) {
          // Use typed query DSL
          const formattedFilters = filters
            .filter((f) => f.prop && f.value)
            .map((f) => {
              let val: any = f.value;
              if (!isNaN(Number(val)) && val.trim() !== "") {
                val = Number(val);
              }
              return { prop: f.prop, op: f.op, value: val };
            });

          result = await executeTypedQuery(
            {
              type: selectedType,
              filters: formattedFilters,
              limit: 25,
            },
            headers
          );
        } else {
          result = await fetchObjects(
            selectedType,
            {
              q: searchTerm.trim() || undefined,
              cursor: targetCursor || undefined,
              limit: 25,
            },
            headers
          );
        }
        setData(result);
      } catch (err: any) {
        setError(err.message || "Failed to load ontology objects");
      } finally {
        setLoading(false);
      }
    },
    [selectedType, searchTerm, filters, currentUser]
  );

  useEffect(() => {
    setCursor(null);
    setCursorHistory([]);
    loadData(null);
  }, [selectedType, currentUser]);

  const handleNextPage = () => {
    if (!data?.next_cursor) return;
    setCursorHistory((prev) => [...prev, cursor || ""]);
    setCursor(data.next_cursor);
    loadData(data.next_cursor);
  };

  const handleResetFilters = () => {
    setFilters([]);
    setSearchTerm("");
    setCursor(null);
    setCursorHistory([]);
    loadData(null);
  };

  const addFilter = () => {
    const availableProps = PROPS_BY_TYPE[selectedType] || ["name"];
    setFilters((prev) => [...prev, { prop: availableProps[0], op: "eq", value: "" }]);
  };

  const removeFilter = (idx: number) => {
    setFilters((prev) => prev.filter((_, i) => i !== idx));
  };

  return (
    <div className="space-y-6">
      {/* Type Selector Bar */}
      <div className="flex items-center space-x-2 overflow-x-auto pb-2">
        {OBJECT_TYPES.map((type) => (
          <button
            key={type}
            onClick={() => {
              setSelectedType(type);
              setFilters([]);
            }}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all border ${
              selectedType === type
                ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/40 shadow-sm shadow-cyan-950"
                : "bg-slate-900/60 text-slate-400 border-slate-800 hover:text-slate-200 hover:bg-slate-800/60"
            }`}
          >
            {type}
          </button>
        ))}
      </div>

      {/* Control Bar: Search + Filter Toggle + Keyset Navigation */}
      <div className="glass-panel rounded-xl p-4 space-y-4">
        <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
          {/* Search Box */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder={`Search ${selectedType}s by keyword (e.g. Hydraulik, Krupp)...`}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && loadData(null)}
              className="w-full pl-9 pr-4 py-2 bg-slate-950/80 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-cyan-500 transition-colors placeholder:text-slate-500"
            />
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setShowFilterBuilder(!showFilterBuilder)}
              className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-xs border transition-colors ${
                showFilterBuilder || filters.length > 0
                  ? "bg-cyan-950/60 border-cyan-800 text-cyan-300"
                  : "bg-slate-900 border-slate-800 text-slate-300 hover:bg-slate-800"
              }`}
            >
              <Filter className="w-3.5 h-3.5" />
              <span>Filters ({filters.length})</span>
            </button>

            <button
              onClick={() => loadData(null)}
              disabled={loading}
              className="flex items-center space-x-1.5 px-3 py-2 rounded-lg text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-slate-950 transition-colors shadow-sm disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              <span>Run Query</span>
            </button>
          </div>
        </div>

        {/* Dynamic DSL Filter Builder */}
        {showFilterBuilder && (
          <div className="pt-3 border-t border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
                Typed Ontology Filter Builder
              </span>
              <button
                onClick={addFilter}
                className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center space-x-1"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Filter Condition</span>
              </button>
            </div>

            {filters.length === 0 ? (
              <p className="text-xs text-slate-500 italic py-2">
                No active filters. Click "Add Filter Condition" to filter by properties safely via Typed Query DSL.
              </p>
            ) : (
              <div className="space-y-2">
                {filters.map((f, idx) => (
                  <div key={idx} className="flex items-center space-x-2">
                    <select
                      value={f.prop}
                      onChange={(e) => {
                        const val = e.target.value;
                        setFilters((prev) =>
                          prev.map((item, i) => (i === idx ? { ...item, prop: val } : item))
                        );
                      }}
                      className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded text-xs text-slate-300 focus:outline-none focus:border-cyan-500"
                    >
                      {(PROPS_BY_TYPE[selectedType] || ["name"]).map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                    </select>

                    <select
                      value={f.op}
                      onChange={(e) => {
                        const val = e.target.value;
                        setFilters((prev) =>
                          prev.map((item, i) => (i === idx ? { ...item, op: val } : item))
                        );
                      }}
                      className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded text-xs text-slate-300 focus:outline-none focus:border-cyan-500"
                    >
                      <option value="eq">=</option>
                      <option value="ne">!=</option>
                      <option value="contains">contains</option>
                      <option value="gt">&gt;</option>
                      <option value="gte">&gt;=</option>
                      <option value="lt">&lt;</option>
                      <option value="lte">&lt;=</option>
                    </select>

                    <input
                      type="text"
                      placeholder="Value..."
                      value={f.value}
                      onChange={(e) => {
                        const val = e.target.value;
                        setFilters((prev) =>
                          prev.map((item, i) => (i === idx ? { ...item, value: val } : item))
                        );
                      }}
                      className="flex-1 px-3 py-1.5 bg-slate-950 border border-slate-800 rounded text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
                    />

                    <button
                      onClick={() => removeFilter(idx)}
                      className="p-1.5 text-slate-400 hover:text-rose-400 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-950/50 border border-rose-800/80 text-rose-200 text-xs flex items-start space-x-3">
          <div className="font-semibold">Query Error:</div>
          <div className="font-mono">{error}</div>
        </div>
      )}

      {/* Results Table */}
      <div className="glass-panel rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between text-xs text-slate-400">
          <div className="flex items-center space-x-2">
            <span>Query Results:</span>
            <span className="font-mono text-cyan-400 font-semibold">{data?.count ?? 0} records</span>
            {currentUser.plant && (
              <span className="text-[11px] font-mono text-amber-400 bg-amber-950/40 px-2 py-0.5 rounded border border-amber-800/60">
                Filtered by RLS: {currentUser.plant}
              </span>
            )}
          </div>

          {data?.next_cursor && (
            <div className="flex items-center space-x-2">
              <span className="text-[11px] font-mono text-slate-500">Keyset Cursor Active</span>
              <button
                onClick={handleNextPage}
                disabled={loading}
                className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 flex items-center space-x-1"
              >
                <span>Next Page</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>

        {loading ? (
          <div className="p-12 text-center text-slate-500 text-xs flex flex-col items-center justify-center space-y-2">
            <RefreshCw className="w-6 h-6 animate-spin text-cyan-400" />
            <span>Executing permissioned query against ontology store...</span>
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="p-12 text-center text-slate-500 text-xs">
            <p>No {selectedType} objects found matching the specified query.</p>
            {currentUser.plant && (
              <p className="mt-1 text-slate-600">
                Note: Row-Level Security restricts your view to plant {currentUser.plant} or global records.
              </p>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900/60 border-b border-slate-800/80 text-[11px] font-mono uppercase text-slate-400">
                <tr>
                  <th className="py-2.5 px-4 font-medium">Identifier</th>
                  <th className="py-2.5 px-4 font-medium">Primary Info</th>
                  <th className="py-2.5 px-4 font-medium">Plant Scope</th>
                  <th className="py-2.5 px-4 font-medium">Created At</th>
                  <th className="py-2.5 px-4 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {data.items.map((item) => {
                  const id = item.id;
                  const naturalKey = item.natural_key || item.id;
                  const primaryText =
                    item.name ||
                    item.part_number ||
                    item.po_number ||
                    item.shipment_number ||
                    item.incident_number ||
                    naturalKey;
                  const secondaryText =
                    item.country ||
                    item.category ||
                    item.status ||
                    item.location ||
                    item.currency;

                  return (
                    <tr
                      key={id}
                      className="hover:bg-slate-800/40 transition-colors group"
                    >
                      <td className="py-3 px-4 font-mono text-cyan-400 font-medium">
                        {naturalKey}
                      </td>
                      <td className="py-3 px-4">
                        <div className="font-semibold text-slate-200">{primaryText}</div>
                        {secondaryText && (
                          <div className="text-[11px] text-slate-400">{secondaryText}</div>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        {item.plant ? (
                          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-[10px] font-mono text-slate-300">
                            <Building className="w-2.5 h-2.5 text-cyan-400" />
                            <span>{item.plant}</span>
                          </span>
                        ) : (
                          <span className="text-[10px] font-mono text-slate-500">Global</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-slate-400 font-mono text-[11px]">
                        {item.created_at ? new Date(item.created_at).toLocaleDateString() : "—"}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end space-x-2">
                          <Link
                            href={`/foundry/objects/${selectedType}/${id}`}
                            className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-cyan-400 transition-colors"
                            title="Inspect Object & Provenance"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </Link>
                          <Link
                            href={`/foundry/graph?focus=${id}&type=${selectedType}`}
                            className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-cyan-400 transition-colors"
                            title="Inspect Neighbors in Graph"
                          >
                            <Network className="w-3.5 h-3.5" />
                          </Link>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
