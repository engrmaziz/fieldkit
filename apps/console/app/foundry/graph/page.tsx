"use client";

import { Suspense, useEffect, useRef, useState, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { fetchNeighbors, fetchObjects } from "@/lib/api";
import {
  Network,
  ZoomIn,
  ZoomOut,
  Maximize2,
  RefreshCw,
  AlertTriangle,
  Info,
  ExternalLink,
  Layers,
} from "lucide-react";
import cytoscape, { Core } from "cytoscape";

const TYPE_COLORS: Record<string, string> = {
  Supplier: "#0284c7", // Sky blue
  PurchaseOrder: "#10b981", // Emerald green
  Part: "#8b5cf6", // Purple
  Shipment: "#f59e0b", // Amber
  QualityIncident: "#f43f5e", // Rose red
  Certificate: "#06b6d4", // Cyan
  Plant: "#64748b", // Slate
};

function GraphContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { currentUser, getAuthHeaders } = useAuth();

  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  const initialFocus = searchParams?.get("focus");
  const initialType = searchParams?.get("type") || "Supplier";

  const [selectedNode, setSelectedNode] = useState<any | null>(null);
  const [nodeCount, setNodeCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [warning, setWarning] = useState<string | null>(null);

  // Initialize Cytoscape
  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "background-color": "data(color)",
            color: "#f8fafc",
            "font-size": "10px",
            "text-valign": "bottom",
            "text-margin-y": 4,
            width: 28,
            height: 28,
            "border-width": 2,
            "border-color": "#0f172a",
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-width": 3,
            "border-color": "#38bdf8",
            "border-opacity": 0.9,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "#334155",
            "target-arrow-color": "#475569",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": "8px",
            color: "#94a3b8",
            "text-background-color": "#090d16",
            "text-background-opacity": 0.8,
            "text-background-padding": "2px",
          },
        },
      ],
      layout: {
        name: "cose",
        animate: false,
      },
    });

    cy.on("select", "node", (evt) => {
      setSelectedNode(evt.target.data());
    });

    cy.on("unselect", "node", () => {
      setSelectedNode(null);
    });

    cyRef.current = cy;

    return () => {
      cy.destroy();
    };
  }, []);

  // Expand node neighbors (depth 1)
  const expandNode = useCallback(
    async (nodeId: string, nodeType: string) => {
      const cy = cyRef.current;
      if (!cy) return;

      if (cy.nodes().length >= 300) {
        setWarning("Maximum graph limit reached (300 nodes). Further expansions restricted to avoid lag.");
        return;
      }

      setLoading(true);
      try {
        const headers = getAuthHeaders();
        const res = await fetchNeighbors(nodeType, nodeId, 1, undefined, headers);

        let addedCount = 0;
        res.neighbors.forEach((n) => {
          const targetId = n.object.id;
          if (cy.nodes(`[id = "${targetId}"]`).length === 0) {
            cy.add({
              group: "nodes",
              data: {
                id: targetId,
                type: n.target_type,
                label:
                  n.object.name ||
                  n.object.part_number ||
                  n.object.po_number ||
                  n.object.natural_key ||
                  targetId.slice(0, 8),
                color: TYPE_COLORS[n.target_type] || "#64748b",
                raw: n.object,
              },
            });
            addedCount++;
          }

          const edgeId = `e-${nodeId}-${targetId}-${n.link}`;
          if (cy.edges(`[id = "${edgeId}"]`).length === 0) {
            cy.add({
              group: "edges",
              data: {
                id: edgeId,
                source: nodeId,
                target: targetId,
                label: n.link,
              },
            });
          }
        });

        if (addedCount > 0) {
          cy.layout({ name: "cose", animate: true, animationDuration: 500 }).run();
        }
        setNodeCount(cy.nodes().length);
      } catch (err: any) {
        console.error("Expansion failed", err);
      } finally {
        setLoading(false);
      }
    },
    [currentUser]
  );

  // Initial load
  useEffect(() => {
    async function initGraph() {
      const cy = cyRef.current;
      if (!cy) return;

      cy.elements().remove();
      setWarning(null);

      try {
        const headers = getAuthHeaders();
        if (initialFocus) {
          cy.add({
            group: "nodes",
            data: {
              id: initialFocus,
              type: initialType,
              label: `Seed ${initialType}`,
              color: TYPE_COLORS[initialType] || "#0284c7",
              raw: { id: initialFocus, type: initialType },
            },
          });
          await expandNode(initialFocus, initialType);
        } else {
          // Fetch initial suppliers
          const res = await fetchObjects("Supplier", { limit: 6 }, headers);
          res.items.forEach((item) => {
            cy.add({
              group: "nodes",
              data: {
                id: item.id,
                type: "Supplier",
                label: item.name || item.natural_key,
                color: TYPE_COLORS.Supplier,
                raw: item,
              },
            });
          });
          if (res.items.length > 0) {
            await expandNode(res.items[0].id, "Supplier");
          }
        }
        cy.layout({ name: "cose", animate: false }).run();
        setNodeCount(cy.nodes().length);
      } catch (err: any) {
        setWarning("Failed to seed initial graph nodes: " + err.message);
      }
    }

    initGraph();
  }, [initialFocus, initialType, currentUser]);

  return (
    <div className="space-y-4">
      {/* Warning Banner */}
      {warning && (
        <div className="p-3 rounded-lg bg-amber-950/60 border border-amber-800 text-amber-300 text-xs flex items-center space-x-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{warning}</span>
        </div>
      )}

      {/* Main Graph Canvas Container */}
      <div className="relative glass-panel rounded-xl overflow-hidden h-[620px] flex">
        {/* Cytoscape Canvas */}
        <div ref={containerRef} className="flex-1 h-full bg-[#070b12]" />

        {/* Canvas Toolbar Overlay */}
        <div className="absolute top-4 left-4 z-10 flex items-center space-x-2 bg-slate-900/90 border border-slate-800 p-1.5 rounded-lg backdrop-blur">
          <button
            onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 1.25)}
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded transition-colors"
            title="Zoom In"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 0.8)}
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded transition-colors"
            title="Zoom Out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={() => cyRef.current?.fit(undefined, 30)}
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded transition-colors"
            title="Fit to Screen"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
          <div className="h-4 w-px bg-slate-800" />
          <span className="text-[11px] font-mono text-slate-400 px-1">
            Nodes: <span className="text-cyan-400 font-bold">{nodeCount}</span>
          </span>
        </div>

        {/* Legend Overlay */}
        <div className="absolute bottom-4 left-4 z-10 p-2.5 rounded-lg bg-slate-950/90 border border-slate-800 text-[10px] space-y-1 backdrop-blur">
          <span className="text-slate-400 font-mono block uppercase text-[9px] mb-1">
            Ontology Link Types
          </span>
          <div className="flex items-center space-x-3">
            {Object.entries(TYPE_COLORS).map(([type, color]) => (
              <div key={type} className="flex items-center space-x-1.5">
                <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                <span className="text-slate-300 font-mono">{type}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Right Drawer: Selected Node Inspector */}
        <div className="w-80 border-l border-slate-800 bg-slate-950/95 p-4 flex flex-col justify-between overflow-y-auto">
          {selectedNode ? (
            <div className="space-y-4">
              <div>
                <span
                  className="text-[10px] font-mono px-2 py-0.5 rounded uppercase font-semibold inline-block mb-1.5"
                  style={{
                    backgroundColor: `${selectedNode.color}25`,
                    color: selectedNode.color,
                    border: `1px solid ${selectedNode.color}60`,
                  }}
                >
                  {selectedNode.type}
                </span>
                <h3 className="font-bold text-slate-100 text-sm">{selectedNode.label}</h3>
                <span className="text-[10px] font-mono text-slate-500 block truncate">
                  {selectedNode.id}
                </span>
              </div>

              {/* Node Attributes Preview */}
              <div className="space-y-2 border-t border-slate-800 pt-3">
                <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">
                  Node Attributes
                </span>
                <div className="space-y-1 text-xs">
                  {Object.entries(selectedNode.raw || {})
                    .slice(0, 6)
                    .map(([k, v]) => (
                      <div key={k} className="flex justify-between text-[11px]">
                        <span className="text-slate-400 font-mono">{k}:</span>
                        <span className="text-slate-200 font-mono truncate max-w-[140px]">
                          {String(v)}
                        </span>
                      </div>
                    ))}
                </div>
              </div>

              {/* Expansion Trigger Button */}
              <div className="border-t border-slate-800 pt-3 space-y-2">
                <button
                  onClick={() => expandNode(selectedNode.id, selectedNode.type)}
                  disabled={loading}
                  className="w-full py-2 px-3 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-slate-950 text-xs font-semibold flex items-center justify-center space-x-2 transition-colors disabled:opacity-50"
                >
                  <Network className="w-3.5 h-3.5" />
                  <span>{loading ? "Traversing..." : "Expand Neighbors (+1 Depth)"}</span>
                </button>

                <Link
                  href={`/foundry/objects/${selectedNode.type}/${selectedNode.id}`}
                  className="w-full py-2 px-3 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 text-xs flex items-center justify-center space-x-1.5 transition-colors"
                >
                  <span>Inspect Full Object & Provenance</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center text-slate-500 text-xs space-y-2">
              <Network className="w-8 h-8 text-slate-600 stroke-1" />
              <p>Click any node in the graph to inspect properties or expand neighbors by 1 depth.</p>
            </div>
          )}

          {/* Quick RLS Note */}
          <div className="pt-4 border-t border-slate-900 text-[10px] text-slate-500 font-mono">
            Graph link traversals apply Row-Level Security: cross-plant neighbors outside active scope are filtered out.
          </div>
        </div>
      </div>
    </div>
  );
}

export default function GraphExplorerPage() {
  return (
    <Suspense
      fallback={
        <div className="glass-panel rounded-xl p-16 text-center text-slate-500 text-xs flex flex-col items-center justify-center space-y-2">
          <RefreshCw className="w-6 h-6 animate-spin text-cyan-400" />
          <span>Loading Interactive Graph Explorer...</span>
        </div>
      }
    >
      <GraphContent />
    </Suspense>
  );
}
