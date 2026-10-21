"use client";

import { useState, useMemo, useEffect, useCallback } from "react";
import {
  ScanEye,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Activity,
  Sliders,
  RotateCcw,
  UploadCloud,
  ChevronRight,
  ChevronLeft,
  Cpu,
  ShieldCheck,
  Zap,
  Clock,
  Layers,
  Sparkles,
  Info,
  Check,
  AlertOctagon,
  ArrowRight,
  RefreshCw,
  Eye,
  Database,
  FileCheck,
} from "lucide-react";
import {
  InspectionRecordUI,
  ReviewQueueItemUI,
  DriftMetricUI,
  ShadowModelReportUI,
  MOCK_INSPECTION_RECORDS,
  MOCK_REVIEW_QUEUE,
  MOCK_DRIFT_METRICS,
  MOCK_SHADOW_REPORT,
  DefectClass,
  InspectionDisposition,
} from "@/lib/inspection-data";

export default function InspectionConsolePage() {
  // Tab navigation
  const [activeTab, setActiveTab] = useState<"feed" | "queue" | "models" | "drift">("feed");

  // Inspection records & review queue state
  const [records, setRecords] = useState<InspectionRecordUI[]>(MOCK_INSPECTION_RECORDS);
  const [reviewQueue, setReviewQueue] = useState<ReviewQueueItemUI[]>(MOCK_REVIEW_QUEUE);
  const [driftMetrics, setDriftMetrics] = useState<DriftMetricUI[]>(MOCK_DRIFT_METRICS);
  const [shadowReport, setShadowReport] = useState<ShadowModelReportUI>(MOCK_SHADOW_REPORT);

  // Filters
  const [productFilter, setProductFilter] = useState<string>("all");
  const [dispositionFilter, setDispositionFilter] = useState<string>("all");

  // Inspector Drawer State
  const [selectedRecord, setSelectedRecord] = useState<InspectionRecordUI | null>(null);
  const [heatmapOpacity, setHeatmapOpacity] = useState<number>(0.65);

  // Review Queue Active Index
  const [activeQueueIdx, setActiveQueueIdx] = useState<number>(0);
  const [operatorNotes, setOperatorNotes] = useState<string>("");
  const [selectedClass, setSelectedClass] = useState<DefectClass>("inclusion");
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Model Promotion State
  const [isRetraining, setIsRetraining] = useState<boolean>(false);
  const [retrainSuccess, setRetrainSuccess] = useState<string | null>(null);
  const [isPromoting, setIsPromoting] = useState<boolean>(false);
  const [promoteSuccess, setPromoteSuccess] = useState<string | null>(null);
  const [isRollingBack, setIsRollingBack] = useState<boolean>(false);
  const [rollbackSuccess, setRollbackSuccess] = useState<string | null>(null);

  // Current item in review queue
  const currentQueueItem = reviewQueue[activeQueueIdx] || null;

  // Filtered live feed records
  const filteredRecords = useMemo(() => {
    return records.filter((r) => {
      const matchProduct = productFilter === "all" || r.productId === productFilter;
      const matchDisp = dispositionFilter === "all" || r.disposition === dispositionFilter;
      return matchProduct && matchDisp;
    });
  }, [records, productFilter, dispositionFilter]);

  // Handle Review Adjudication
  const handleAdjudicate = useCallback(
    (disposition: InspectionDisposition) => {
      if (!currentQueueItem) return;
      setIsSubmitting(true);

      setTimeout(() => {
        const updatedRecord: InspectionRecordUI = {
          ...currentQueueItem,
          disposition,
          reviewed: true,
          reviewedBy: "M. Yilmaz (Quality Lead)",
          operatorNotes: operatorNotes || `Adjudicated as ${disposition} via operator console`,
          reviewedAt: new Date().toLocaleTimeString(),
          predictedClass: selectedClass,
        };

        // Update records list
        setRecords((prev) =>
          prev.map((r) => (r.id === currentQueueItem.id ? updatedRecord : r))
        );

        // Remove from review queue
        setReviewQueue((prev) => prev.filter((_, idx) => idx !== activeQueueIdx));
        if (activeQueueIdx >= reviewQueue.length - 1 && activeQueueIdx > 0) {
          setActiveQueueIdx(activeQueueIdx - 1);
        }

        setActionMessage(
          `Record ${currentQueueItem.id} successfully adjudicated as ${disposition}.`
        );
        setIsSubmitting(false);
        setOperatorNotes("");
      }, 300);
    },
    [currentQueueItem, activeQueueIdx, reviewQueue.length, operatorNotes, selectedClass]
  );

  // Keyboard shortcuts for Review Queue
  useEffect(() => {
    if (activeTab !== "queue" || !currentQueueItem) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if typing in notes textarea
      if ((e.target as HTMLElement)?.tagName === "TEXTAREA" || (e.target as HTMLElement)?.tagName === "INPUT") {
        return;
      }

      if (e.key === "p" || e.key === "P") {
        e.preventDefault();
        handleAdjudicate("PASS");
      } else if (e.key === "r" || e.key === "R") {
        e.preventDefault();
        handleAdjudicate("REJECT");
      } else if (e.key === "]" && activeQueueIdx < reviewQueue.length - 1) {
        e.preventDefault();
        setActiveQueueIdx((i) => i + 1);
      } else if (e.key === "[" && activeQueueIdx > 0) {
        e.preventDefault();
        setActiveQueueIdx((i) => i - 1);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeTab, currentQueueItem, activeQueueIdx, reviewQueue.length, handleAdjudicate]);

  // Model Operations
  const handleTriggerRetrain = () => {
    setIsRetraining(true);
    setRetrainSuccess(null);
    setTimeout(() => {
      setIsRetraining(false);
      setRetrainSuccess(
        "Candidate retrain job completed: v2.1.0-cand passed frozen test gate (Accuracy: 100%, ECE: 0.021). Staged in registry."
      );
    }, 1200);
  };

  const handlePromoteCandidate = () => {
    setIsPromoting(true);
    setPromoteSuccess(null);
    setTimeout(() => {
      setIsPromoting(false);
      setPromoteSuccess(
        "Model inspect_v2.0.0_candidate promoted to PRODUCTION! In-memory hot-swap active on conveyor line."
      );
      setShadowReport((prev) => ({
        ...prev,
        prodModelId: prev.candModelId,
        candModelId: "inspect_v2.1.0_candidate",
        status: "COLLECTING_TELEMETRY",
      }));
    }, 1000);
  };

  const handleRollback = () => {
    setIsRollingBack(true);
    setRollbackSuccess(null);
    setTimeout(() => {
      setIsRollingBack(false);
      setRollbackSuccess(
        "Zero-Downtime Rollback complete! Pipeline reverted to inspect_v1.0.0_fp32. Audit record logged."
      );
      setShadowReport((prev) => ({
        ...prev,
        prodModelId: "inspect_v1.0.0_fp32",
        status: "READY_FOR_PROMOTION",
      }));
    }, 1000);
  };

  // SVG Surface Visualizer with Jet colormap overlay simulation
  const renderSurfaceVisual = (item: InspectionRecordUI, opacity: number = 0.65) => {
    return (
      <div className="relative w-full aspect-square max-w-[280px] mx-auto rounded-xl overflow-hidden border border-slate-700/80 bg-slate-950 shadow-inner flex items-center justify-center">
        {/* Base Surface Canvas */}
        <svg
          viewBox="0 0 256 256"
          className="w-full h-full"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            {/* Metallic Brushed Gradients */}
            <linearGradient id="metalGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#475569" />
              <stop offset="50%" stopColor="#64748b" />
              <stop offset="100%" stopColor="#334155" />
            </linearGradient>
            <radialGradient id="nutFlange" cx="50%" cy="50%" r="50%">
              <stop offset="40%" stopColor="#94a3b8" />
              <stop offset="70%" stopColor="#475569" />
              <stop offset="100%" stopColor="#1e293b" />
            </radialGradient>
            {/* Jet Colormap Defect Activation Gradient */}
            <radialGradient id="jetActivation" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#ef4444" stopOpacity="0.95" />
              <stop offset="35%" stopColor="#f59e0b" stopOpacity="0.85" />
              <stop offset="70%" stopColor="#3b82f6" stopOpacity="0.60" />
              <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.0" />
            </radialGradient>
          </defs>

          {/* Component Specific Geometry */}
          {item.surfaceSvgType === "nut" && (
            <g>
              <rect width="256" height="256" fill="#0f172a" />
              <circle cx="128" cy="128" r="105" fill="url(#nutFlange)" stroke="#64748b" strokeWidth="4" />
              <polygon
                points="128,45 195,84 195,172 128,211 61,172 61,84"
                fill="#334155"
                stroke="#94a3b8"
                strokeWidth="3"
              />
              <circle cx="128" cy="128" r="45" fill="#0f172a" stroke="#cbd5e1" strokeWidth="3" />
              {/* Thread ridges */}
              <circle cx="128" cy="128" r="41" fill="none" stroke="#475569" strokeWidth="1.5" strokeDasharray="6,4" />
              <circle cx="128" cy="128" r="37" fill="none" stroke="#334155" strokeWidth="1.5" strokeDasharray="4,3" />
            </g>
          )}

          {item.surfaceSvgType === "sheet" && (
            <g>
              <rect width="256" height="256" fill="url(#metalGrad)" />
              {/* Cold-rolled brush lines */}
              <line x1="0" y1="40" x2="256" y2="40" stroke="#94a3b8" strokeWidth="1" opacity="0.3" />
              <line x1="0" y1="85" x2="256" y2="85" stroke="#94a3b8" strokeWidth="1.5" opacity="0.4" />
              <line x1="0" y1="130" x2="256" y2="130" stroke="#94a3b8" strokeWidth="1" opacity="0.25" />
              <line x1="0" y1="180" x2="256" y2="180" stroke="#94a3b8" strokeWidth="2" opacity="0.35" />
              <line x1="0" y1="220" x2="256" y2="220" stroke="#94a3b8" strokeWidth="1" opacity="0.3" />
            </g>
          )}

          {item.surfaceSvgType === "screw" && (
            <g>
              <rect width="256" height="256" fill="#0f172a" />
              <rect x="78" y="25" width="100" height="70" rx="8" fill="#475569" stroke="#94a3b8" strokeWidth="3" />
              <polygon points="128,40 148,50 148,70 128,80 108,70 108,50" fill="#0f172a" stroke="#cbd5e1" strokeWidth="2" />
              <rect x="98" y="95" width="60" height="135" fill="#334155" stroke="#64748b" strokeWidth="2" />
              {/* Screw Threads */}
              {[115, 135, 155, 175, 195, 215].map((y) => (
                <line key={y} x1="90" y1={y} x2="166" y2={y + 8} stroke="#94a3b8" strokeWidth="3.5" />
              ))}
            </g>
          )}

          {item.surfaceSvgType === "grid" && (
            <g>
              <rect width="256" height="256" fill="#1e293b" />
              {[32, 64, 96, 128, 160, 192, 224].map((coord) => (
                <g key={coord}>
                  <line x1={coord} y1="0" x2={coord} y2="256" stroke="#64748b" strokeWidth="4" />
                  <line x1="0" y1={coord} x2="256" y2={coord} stroke="#64748b" strokeWidth="4" />
                </g>
              ))}
            </g>
          )}

          {item.surfaceSvgType === "tile" && (
            <g>
              <rect width="256" height="256" fill="#78350f" />
              <rect x="15" y="15" width="226" height="226" fill="#92400e" stroke="#b45309" strokeWidth="4" />
              <circle cx="60" cy="60" r="15" fill="#b45309" opacity="0.4" />
              <circle cx="180" cy="180" r="22" fill="#78350f" opacity="0.6" />
              <circle cx="190" cy="70" r="12" fill="#d97706" opacity="0.3" />
            </g>
          )}

          {/* Jet Colormap Anomaly Overlay */}
          {item.hasDefectVisual && item.defectLocation && (
            <g style={{ opacity }}>
              <circle
                cx={item.defectLocation.cx}
                cy={item.defectLocation.cy}
                r={item.defectLocation.r * 1.6}
                fill="url(#jetActivation)"
              />
              <circle
                cx={item.defectLocation.cx}
                cy={item.defectLocation.cy}
                r={item.defectLocation.r}
                fill="#ef4444"
                fillOpacity="0.4"
                stroke="#ef4444"
                strokeWidth="2.5"
                strokeDasharray="4,2"
              />
            </g>
          )}
        </svg>

        {/* Heatmap Layer Tag */}
        <div className="absolute bottom-2 left-2 px-2 py-0.5 rounded bg-slate-900/90 border border-slate-700/80 text-[10px] font-mono text-slate-300 backdrop-blur-sm flex items-center space-x-1.5">
          <span
            className="w-2 h-2 rounded-full"
            style={{
              backgroundColor:
                item.disposition === "PASS"
                  ? "#10b981"
                  : item.disposition === "REVIEW"
                  ? "#f59e0b"
                  : "#ef4444",
            }}
          />
          <span>Jet Blend: {Math.round(opacity * 100)}%</span>
        </div>

        {item.isAudit && (
          <div className="absolute top-2 right-2 px-2 py-0.5 rounded bg-amber-950/90 border border-amber-800 text-[9px] font-semibold text-amber-300 font-mono">
            2% AUDIT
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Banner / Plant Header */}
      <div className="border-b border-slate-800 bg-slate-900/60 backdrop-blur-md px-6 py-4">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center space-x-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-amber-600 to-rose-500 flex items-center justify-center shadow-lg shadow-amber-950/40 border border-amber-400/30">
              <ScanEye className="w-6 h-6 text-slate-950 stroke-[2.5]" />
            </div>
            <div>
              <div className="flex items-center space-x-3">
                <h1 className="text-xl font-bold tracking-tight text-white">InspectAI Edge Console</h1>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-950 border border-amber-800 text-amber-400 font-semibold uppercase">
                  P6 Production
                </span>
                <span className="text-xs px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-800 text-emerald-400 flex items-center space-x-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  <span>DE-HAM Active</span>
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                Halden Industrie Hamburg • Quality Station DE-HAM-L3 • Dual PatchCore + Calibrated Classifier
              </p>
            </div>
          </div>

          {/* Quick Metrics Bar */}
          <div className="flex items-center space-x-3 text-xs font-mono">
            <div className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center space-x-2">
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              <span className="text-slate-400">Throughput:</span>
              <span className="text-emerald-400 font-bold">103.2 FPS</span>
            </div>
            <div className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center space-x-2">
              <Clock className="w-3.5 h-3.5 text-cyan-400" />
              <span className="text-slate-400">P95 Latency:</span>
              <span className="text-cyan-400 font-bold">10.9 ms</span>
            </div>
            <div className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center space-x-2">
              <Layers className="w-3.5 h-3.5 text-rose-400" />
              <span className="text-slate-400">Escape Rate:</span>
              <span className="text-emerald-400 font-bold">0.00%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="border-b border-slate-800/80 bg-slate-900/30 px-6">
        <div className="max-w-7xl mx-auto flex space-x-6">
          <button
            onClick={() => setActiveTab("feed")}
            className={`py-3 text-xs font-medium border-b-2 transition-all flex items-center space-x-2 ${
              activeTab === "feed"
                ? "border-amber-400 text-amber-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <ScanEye className="w-4 h-4" />
            <span>Live Conveyor Feed</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 font-mono">
              {records.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab("queue")}
            className={`py-3 text-xs font-medium border-b-2 transition-all flex items-center space-x-2 ${
              activeTab === "queue"
                ? "border-amber-400 text-amber-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>Operator Review Queue</span>
            {reviewQueue.length > 0 && (
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-500 text-slate-950 font-bold font-mono">
                {reviewQueue.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab("models")}
            className={`py-3 text-xs font-medium border-b-2 transition-all flex items-center space-x-2 ${
              activeTab === "models"
                ? "border-amber-400 text-amber-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Cpu className="w-4 h-4 text-cyan-400" />
            <span>Shadow Mode & Promotion</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-950 border border-emerald-800 text-emerald-400 font-mono">
              100% Agreement
            </span>
          </button>

          <button
            onClick={() => setActiveTab("drift")}
            className={`py-3 text-xs font-medium border-b-2 transition-all flex items-center space-x-2 ${
              activeTab === "drift"
                ? "border-amber-400 text-amber-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Activity className="w-4 h-4 text-rose-400" />
            <span>PSI Drift Monitor</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 font-mono">
              PSI 0.0727
            </span>
          </button>
        </div>
      </div>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto w-full p-6 flex-1 flex flex-col gap-6">
        {/* TAB 1: LIVE CONVEYOR FEED */}
        {activeTab === "feed" && (
          <div className="flex flex-col gap-6">
            {/* Filter Toolbar */}
            <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-xs text-slate-400 font-mono">Product:</span>
                <div className="flex space-x-1">
                  {["all", "metal_nut", "steel_sheet", "screw", "grid", "tile"].map((prod) => (
                    <button
                      key={prod}
                      onClick={() => setProductFilter(prod)}
                      className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                        productFilter === prod
                          ? "bg-amber-500 text-slate-950 font-semibold"
                          : "bg-slate-800/80 text-slate-400 hover:text-slate-200 hover:bg-slate-700"
                      }`}
                    >
                      {prod === "all" ? "All Products" : prod}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex items-center space-x-3">
                <span className="text-xs text-slate-400 font-mono">Disposition:</span>
                <div className="flex space-x-1">
                  {["all", "PASS", "REVIEW", "REJECT"].map((disp) => (
                    <button
                      key={disp}
                      onClick={() => setDispositionFilter(disp)}
                      className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                        dispositionFilter === disp
                          ? "bg-slate-200 text-slate-950 font-semibold"
                          : "bg-slate-800/80 text-slate-400 hover:text-slate-200 hover:bg-slate-700"
                      }`}
                    >
                      {disp}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Grid of Inspected Parts */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {filteredRecords.map((item) => {
                const isPass = item.disposition === "PASS";
                const isReview = item.disposition === "REVIEW";
                const isReject = item.disposition === "REJECT";

                return (
                  <div
                    key={item.id}
                    onClick={() => setSelectedRecord(item)}
                    className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 hover:border-slate-700 cursor-pointer transition-all hover:shadow-lg hover:shadow-slate-950/50 flex flex-col justify-between group"
                  >
                    <div>
                      {/* Card Header */}
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-xs font-mono font-semibold text-slate-300">
                          {item.id}
                        </span>
                        <div className="flex items-center space-x-1.5">
                          <span
                            className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase ${
                              isPass
                                ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                                : isReview
                                ? "bg-amber-950 text-amber-400 border border-amber-800"
                                : "bg-rose-950 text-rose-400 border border-rose-800"
                            }`}
                          >
                            {item.disposition}
                          </span>
                        </div>
                      </div>

                      {/* Visual Surface */}
                      <div className="my-2">{renderSurfaceVisual(item, 0.65)}</div>

                      {/* Product Name */}
                      <h3 className="text-xs font-semibold text-slate-200 mt-2 truncate">
                        {item.productName}
                      </h3>
                      <p className="text-[11px] text-slate-400 font-mono capitalize">
                        Defect:{" "}
                        <span className={item.predictedClass === "good" ? "text-emerald-400" : "text-amber-400"}>
                          {item.predictedClass.replace("_", " ")}
                        </span>{" "}
                        ({Math.round(item.calibratedConfidence * 100)}%)
                      </p>
                    </div>

                    {/* Card Footer / Metrics */}
                    <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-400">
                      <div>
                        <span>Score: </span>
                        <span className="font-semibold text-slate-200">
                          {item.anomalyScore.toFixed(3)}
                        </span>
                      </div>
                      <div>
                        <span>Lat: </span>
                        <span className="text-cyan-400 font-semibold">{item.latencyMs}ms</span>
                      </div>
                      <div className="text-slate-500">{item.timestamp}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* TAB 2: OPERATOR REVIEW QUEUE (HITL) */}
        {activeTab === "queue" && (
          <div className="flex flex-col gap-6">
            {/* Queue Status Alert */}
            <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-800/60 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <AlertTriangle className="w-5 h-5 text-amber-400" />
                <div>
                  <h3 className="text-xs font-bold text-amber-300 uppercase tracking-wider font-mono">
                    Borderline Inspection Queue — Plant Hamburg Shift 2
                  </h3>
                  <p className="text-xs text-amber-400/80 mt-0.5">
                    {reviewQueue.length} components flagged for human review (within 8% operator fatigue budget).
                  </p>
                </div>
              </div>

              {/* Keyboard Shortcuts Pill */}
              <div className="hidden lg:flex items-center space-x-3 text-xs font-mono text-slate-400">
                <span>Shortcuts:</span>
                <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-emerald-400">
                  [P] Pass
                </span>
                <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-rose-400">
                  [R] Reject
                </span>
                <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-cyan-400">
                  [ / ] Nav
                </span>
              </div>
            </div>

            {actionMessage && (
              <div className="p-3 rounded-lg bg-emerald-950/60 border border-emerald-800 text-xs font-mono text-emerald-300 flex items-center justify-between">
                <span>{actionMessage}</span>
                <button
                  onClick={() => setActionMessage(null)}
                  className="text-emerald-400 hover:text-white"
                >
                  ✕
                </button>
              </div>
            )}

            {currentQueueItem ? (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 p-6 rounded-2xl bg-slate-900/60 border border-slate-800">
                {/* Left Column: Visual Inspector with Opacity Slider */}
                <div className="lg:col-span-5 flex flex-col items-center justify-center p-4 bg-slate-950/60 rounded-xl border border-slate-800/80">
                  <div className="w-full flex items-center justify-between mb-4">
                    <span className="text-xs font-mono text-slate-400">
                      Item {activeQueueIdx + 1} of {reviewQueue.length}
                    </span>
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-amber-950 text-amber-400 border border-amber-800">
                      Priority: {currentQueueItem.priority}
                    </span>
                  </div>

                  {renderSurfaceVisual(currentQueueItem, heatmapOpacity)}

                  {/* Heatmap Opacity Crossfade Slider */}
                  <div className="w-full max-w-[280px] mt-4 flex flex-col gap-1.5">
                    <div className="flex justify-between text-[11px] font-mono text-slate-400">
                      <span>Raw Surface (0%)</span>
                      <span className="text-amber-400 font-bold">
                        Heatmap ({Math.round(heatmapOpacity * 100)}%)
                      </span>
                      <span>Jet Overlay</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      value={heatmapOpacity}
                      onChange={(e) => setHeatmapOpacity(parseFloat(e.target.value))}
                      className="w-full accent-amber-500 cursor-pointer"
                    />
                  </div>
                </div>

                {/* Right Column: Telemetry & Adjudication Controls */}
                <div className="lg:col-span-7 flex flex-col justify-between">
                  <div>
                    {/* Header Details */}
                    <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                      <div>
                        <h2 className="text-base font-bold text-white font-mono">
                          {currentQueueItem.id}
                        </h2>
                        <p className="text-xs text-slate-400 font-mono mt-0.5">
                          {currentQueueItem.productName}
                        </p>
                      </div>
                      <div className="text-right font-mono text-xs text-slate-400">
                        <div>Trigger: {currentQueueItem.routingReason}</div>
                        <div className="text-cyan-400 font-semibold">
                          Latency: {currentQueueItem.latencyMs} ms
                        </div>
                      </div>
                    </div>

                    {/* Inspection Decision Engine Breakdown */}
                    <div className="grid grid-cols-3 gap-3 my-4">
                      <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 font-mono">
                        <span className="text-[10px] text-slate-400 block">PatchCore Anomaly</span>
                        <span className="text-sm font-bold text-amber-400">
                          {currentQueueItem.anomalyScore.toFixed(3)}
                        </span>
                        <span className="text-[10px] text-slate-500 block">
                          Pass: &lt;{currentQueueItem.thresholdPass.toFixed(3)}
                        </span>
                      </div>
                      <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 font-mono">
                        <span className="text-[10px] text-slate-400 block">Classifier Pred</span>
                        <span className="text-sm font-bold text-rose-400 capitalize">
                          {currentQueueItem.predictedClass.replace("_", " ")}
                        </span>
                        <span className="text-[10px] text-slate-500 block">
                          Conf: {Math.round(currentQueueItem.calibratedConfidence * 100)}%
                        </span>
                      </div>
                      <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 font-mono">
                        <span className="text-[10px] text-slate-400 block">Expected Cost</span>
                        <span className="text-sm font-bold text-emerald-400">
                          {currentQueueItem.costExpected.toFixed(2)} €
                        </span>
                        <span className="text-[10px] text-slate-500 block">Escape: 50.00 €</span>
                      </div>
                    </div>

                    {/* Defect Class Correction Selector */}
                    <div className="mt-4">
                      <label className="text-xs font-mono text-slate-300 block mb-1.5">
                        Defect Class Ground-Truth Label:
                      </label>
                      <select
                        value={selectedClass}
                        onChange={(e) => setSelectedClass(e.target.value as DefectClass)}
                        className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-xs text-slate-200 font-mono focus:outline-none focus:border-amber-400"
                      >
                        <option value="good">good (Normal Component)</option>
                        <option value="crazing">crazing (Thermal Micro-cracks)</option>
                        <option value="inclusion">inclusion (Smelt Impurity)</option>
                        <option value="patches">patches (Surface Oxidation / Scale)</option>
                        <option value="pitted_surface">pitted_surface (Cavity Pitting)</option>
                        <option value="rolled_in_scale">rolled_in_scale (Rolling Burr)</option>
                        <option value="scratches">scratches (Handling Scrapes)</option>
                      </select>
                    </div>

                    {/* Operator Notes Input */}
                    <div className="mt-3">
                      <label className="text-xs font-mono text-slate-300 block mb-1.5">
                        Operator Adjudication Notes:
                      </label>
                      <textarea
                        rows={2}
                        value={operatorNotes}
                        onChange={(e) => setOperatorNotes(e.target.value)}
                        placeholder="e.g. Minor hairline mark within tolerance; confirmed non-structural..."
                        className="w-full p-2.5 rounded-lg bg-slate-950 border border-slate-700 text-xs text-slate-200 font-mono focus:outline-none focus:border-amber-400 resize-none"
                      />
                    </div>
                  </div>

                  {/* Adjudication Action Buttons */}
                  <div className="mt-6 pt-4 border-t border-slate-800 flex items-center justify-between gap-4">
                    <div className="flex space-x-2">
                      <button
                        disabled={activeQueueIdx === 0}
                        onClick={() => setActiveQueueIdx((i) => Math.max(0, i - 1))}
                        className="px-3 py-2 rounded-lg bg-slate-800 text-slate-300 text-xs font-mono disabled:opacity-40 hover:bg-slate-700"
                      >
                        ← Prev [ [ ]
                      </button>
                      <button
                        disabled={activeQueueIdx >= reviewQueue.length - 1}
                        onClick={() => setActiveQueueIdx((i) => Math.min(reviewQueue.length - 1, i + 1))}
                        className="px-3 py-2 rounded-lg bg-slate-800 text-slate-300 text-xs font-mono disabled:opacity-40 hover:bg-slate-700"
                      >
                        Next [ ] ] →
                      </button>
                    </div>

                    <div className="flex space-x-3">
                      <button
                        disabled={isSubmitting}
                        onClick={() => handleAdjudicate("PASS")}
                        className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold text-xs flex items-center space-x-2 shadow-lg shadow-emerald-950/40 transition-all font-mono"
                      >
                        <CheckCircle2 className="w-4 h-4 stroke-[2.5]" />
                        <span>ADJUDICATE PASS [P]</span>
                      </button>

                      <button
                        disabled={isSubmitting}
                        onClick={() => handleAdjudicate("REJECT")}
                        className="px-5 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs flex items-center space-x-2 shadow-lg shadow-rose-950/40 transition-all font-mono"
                      >
                        <XCircle className="w-4 h-4 stroke-[2.5]" />
                        <span>REJECT SCRAP [R]</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-12 text-center rounded-2xl bg-slate-900/40 border border-slate-800/80 flex flex-col items-center">
                <ShieldCheck className="w-12 h-12 text-emerald-400 mb-3" />
                <h3 className="text-base font-bold text-slate-100">Review Queue Empty</h3>
                <p className="text-xs text-slate-400 font-mono mt-1 max-w-md">
                  All flagged inspection items have been adjudicated. High-confidence edge decisions are proceeding at 103.2 FPS.
                </p>
              </div>
            )}
          </div>
        )}

        {/* TAB 3: SHADOW MODE & MODEL PROMOTION */}
        {activeTab === "models" && (
          <div className="flex flex-col gap-6">
            {/* Header Description */}
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-white font-mono flex items-center space-x-2">
                  <Cpu className="w-4 h-4 text-cyan-400" />
                  <span>Model Lifecycle & Non-Blocking Shadow Execution</span>
                </h2>
                <p className="text-xs text-slate-400 font-mono mt-0.5">
                  Side-by-side inference logging paired telemetry without impacting live decisions. Candidate promotion gates require &ge;85% decision agreement.
                </p>
              </div>
              <button
                onClick={handleTriggerRetrain}
                disabled={isRetraining}
                className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold text-xs font-mono flex items-center space-x-2 transition-all shadow-lg shadow-cyan-950/30"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isRetraining ? "animate-spin" : ""}`} />
                <span>{isRetraining ? "Retraining Candidate..." : "Trigger Retraining"}</span>
              </button>
            </div>

            {retrainSuccess && (
              <div className="p-3 rounded-lg bg-cyan-950/60 border border-cyan-800 text-xs font-mono text-cyan-300">
                {retrainSuccess}
              </div>
            )}
            {promoteSuccess && (
              <div className="p-3 rounded-lg bg-emerald-950/60 border border-emerald-800 text-xs font-mono text-emerald-300">
                {promoteSuccess}
              </div>
            )}
            {rollbackSuccess && (
              <div className="p-3 rounded-lg bg-amber-950/60 border border-amber-800 text-xs font-mono text-amber-300">
                {rollbackSuccess}
              </div>
            )}

            {/* Model Side-by-Side Comparison Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Production Model Card */}
              <div className="p-6 rounded-2xl bg-slate-900/70 border border-slate-800 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 border border-emerald-800 text-emerald-400 font-bold uppercase">
                      ACTIVE PRODUCTION
                    </span>
                    <span className="text-xs font-mono text-slate-400">P95: {shadowReport.prodLatencyP95} ms</span>
                  </div>
                  <h3 className="text-lg font-bold text-white font-mono">{shadowReport.prodModelId}</h3>
                  <p className="text-xs text-slate-400 font-mono mt-1">
                    PatchCore Coreset 10% + Calibrated ResNet-18 (ONNX CPU Runtime)
                  </p>

                  <div className="space-y-3 mt-6 text-xs font-mono">
                    <div className="flex justify-between py-1.5 border-b border-slate-800 text-slate-300">
                      <span>Image AUROC (MVTec)</span>
                      <span className="text-emerald-400 font-bold">1.0000</span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-800 text-slate-300">
                      <span>Pixel AUROC</span>
                      <span className="text-emerald-400 font-bold">0.9978</span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-800 text-slate-300">
                      <span>Classifier Macro-F1</span>
                      <span className="text-emerald-400 font-bold">1.0000</span>
                    </div>
                    <div className="flex justify-between py-1.5 text-slate-300">
                      <span>Calibration ECE</span>
                      <span className="text-cyan-400 font-bold">0.0313</span>
                    </div>
                  </div>
                </div>

                <div className="mt-6 pt-4 border-t border-slate-800">
                  <button
                    onClick={handleRollback}
                    disabled={isRollingBack}
                    className="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-rose-400 font-bold text-xs font-mono flex items-center justify-center space-x-2 border border-rose-900/50"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>{isRollingBack ? "Rolling back..." : "Instant Rollback to Previous Stable"}</span>
                  </button>
                </div>
              </div>

              {/* Candidate Shadow Model Card */}
              <div className="p-6 rounded-2xl bg-slate-900/70 border border-cyan-800/60 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950 border border-cyan-800 text-cyan-400 font-bold uppercase">
                      SHADOW CANDIDATE
                    </span>
                    <span className="text-xs font-mono text-cyan-400">
                      P95: {shadowReport.candLatencyP95} ms ({shadowReport.meanLatencyDeltaMs} ms)
                    </span>
                  </div>
                  <h3 className="text-lg font-bold text-white font-mono">{shadowReport.candModelId}</h3>
                  <p className="text-xs text-slate-400 font-mono mt-1">
                    Fine-tuned on Operator Adjudicated Set + Frozen MVTec/NEU Splits
                  </p>

                  <div className="space-y-3 mt-6 text-xs font-mono">
                    <div className="flex justify-between py-1.5 border-b border-slate-800 text-slate-300">
                      <span>Paired Shadow Evaluations</span>
                      <span className="text-white font-bold">{shadowReport.sampleCount} parts</span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-800 text-slate-300">
                      <span>Decision Agreement Rate</span>
                      <span className="text-emerald-400 font-bold">
                        {(shadowReport.decisionAgreementRate * 100).toFixed(1)}% (Req &ge; 85%)
                      </span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-800 text-slate-300">
                      <span>Class Concordance</span>
                      <span className="text-emerald-400 font-bold">
                        {(shadowReport.classConcordanceRate * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex justify-between py-1.5 text-slate-300">
                      <span>Promotion Eligibility</span>
                      <span className="text-emerald-400 font-bold">READY FOR PROMOTION</span>
                    </div>
                  </div>
                </div>

                <div className="mt-6 pt-4 border-t border-slate-800">
                  <button
                    onClick={handlePromoteCandidate}
                    disabled={isPromoting}
                    className="w-full py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs font-mono flex items-center justify-center space-x-2 shadow-lg shadow-amber-950/40"
                  >
                    <CheckCircle2 className="w-4 h-4 stroke-[2.5]" />
                    <span>{isPromoting ? "Promoting Model..." : "Promote Candidate to Production"}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: DISTRIBUTION SHIFT & DRIFT MONITOR */}
        {activeTab === "drift" && (
          <div className="flex flex-col gap-6">
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-white font-mono flex items-center space-x-2">
                  <Activity className="w-4 h-4 text-rose-400" />
                  <span>Population Stability Index (PSI) Drift Monitor</span>
                </h2>
                <p className="text-xs text-slate-400 font-mono mt-0.5">
                  Thresholds: &lt;0.10 Stable (Green), 0.10 - 0.20 Watch (Amber), &gt;0.20 Critical Shift Alert (Red).
                </p>
              </div>
              <span className="text-xs font-mono px-3 py-1 rounded bg-slate-950 border border-slate-800 text-slate-300">
                Laplace-smoothed adaptive binning
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {driftMetrics.map((dm) => {
                const isStable = dm.status === "STABLE";
                const isWatch = dm.status === "WATCH";
                const isCritical = dm.status === "CRITICAL_DRIFT";

                return (
                  <div
                    key={dm.productId}
                    className="p-5 rounded-2xl bg-slate-900/70 border border-slate-800 flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-xs font-mono font-bold text-slate-300">
                          {dm.productId}
                        </span>
                        <span
                          className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase ${
                            isStable
                              ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                              : isWatch
                              ? "bg-amber-950 text-amber-400 border border-amber-800"
                              : "bg-rose-950 text-rose-400 border border-rose-800 animate-pulse"
                          }`}
                        >
                          {dm.status.replace("_", " ")}
                        </span>
                      </div>

                      <h4 className="text-sm font-semibold text-white truncate">{dm.productName}</h4>
                      <p className="text-xs text-slate-400 font-mono mt-1">
                        Samples: {dm.sampleCount} • Updated: {dm.lastUpdated}
                      </p>

                      {/* PSI Meter */}
                      <div className="mt-4 p-3 rounded-lg bg-slate-950/80 border border-slate-800/80">
                        <div className="flex justify-between items-baseline font-mono">
                          <span className="text-[11px] text-slate-400">PSI Value:</span>
                          <span
                            className={`text-lg font-bold ${
                              isStable
                                ? "text-emerald-400"
                                : isWatch
                                ? "text-amber-400"
                                : "text-rose-400"
                            }`}
                          >
                            {dm.psiScore.toFixed(4)}
                          </span>
                        </div>
                        <div className="w-full h-1.5 rounded-full bg-slate-800 mt-2 overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              isStable
                                ? "bg-emerald-400"
                                : isWatch
                                ? "bg-amber-400"
                                : "bg-rose-500"
                            }`}
                            style={{ width: `${Math.min(100, (dm.psiScore / 0.3) * 100)}%` }}
                          />
                        </div>
                      </div>

                      <div className="mt-3 flex justify-between text-[11px] font-mono text-slate-400">
                        <span>Mean: {dm.meanScore.toFixed(3)}</span>
                        <span>Baseline: {dm.baselineMean.toFixed(3)}</span>
                      </div>
                    </div>

                    {isCritical && (
                      <div className="mt-4 pt-3 border-t border-rose-900/50 text-[11px] font-mono text-rose-400 flex items-center space-x-1.5">
                        <AlertOctagon className="w-4 h-4 shrink-0" />
                        <span>Smelting batch shift detected. Retraining trigger active.</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </main>

      {/* INSPECTION DETAIL DRAWER / MODAL */}
      {selectedRecord && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/50">
              <div className="flex items-center space-x-3">
                <ScanEye className="w-5 h-5 text-amber-400" />
                <div>
                  <h3 className="text-base font-bold text-white font-mono">
                    {selectedRecord.id} — {selectedRecord.productName}
                  </h3>
                  <span className="text-xs text-slate-400 font-mono">
                    Captured at {selectedRecord.timestamp} • Latency: {selectedRecord.latencyMs} ms
                  </span>
                </div>
              </div>
              <button
                onClick={() => setSelectedRecord(null)}
                className="w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center justify-center font-mono"
              >
                ✕
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Visual with Slider */}
              <div className="flex flex-col items-center">
                {renderSurfaceVisual(selectedRecord, heatmapOpacity)}

                <div className="w-full max-w-[280px] mt-4 flex flex-col gap-1.5">
                  <div className="flex justify-between text-[11px] font-mono text-slate-400">
                    <span>Raw (0%)</span>
                    <span className="text-amber-400 font-bold">
                      Jet Heatmap: {Math.round(heatmapOpacity * 100)}%
                    </span>
                    <span>100%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={heatmapOpacity}
                    onChange={(e) => setHeatmapOpacity(parseFloat(e.target.value))}
                    className="w-full accent-amber-500 cursor-pointer"
                  />
                </div>
              </div>

              {/* Probability Chart & Decision Matrix */}
              <div className="flex flex-col justify-between font-mono">
                <div>
                  <div className="flex justify-between items-center pb-2 border-b border-slate-800 mb-3">
                    <span className="text-xs text-slate-400">Disposition:</span>
                    <span
                      className={`text-xs px-2.5 py-0.5 rounded font-bold uppercase ${
                        selectedRecord.disposition === "PASS"
                          ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                          : selectedRecord.disposition === "REVIEW"
                          ? "bg-amber-950 text-amber-400 border border-amber-800"
                          : "bg-rose-950 text-rose-400 border border-rose-800"
                      }`}
                    >
                      {selectedRecord.disposition}
                    </span>
                  </div>

                  <h4 className="text-xs font-bold text-slate-300 uppercase mb-2">
                    Calibrated Class Probabilities
                  </h4>

                  <div className="space-y-2 text-xs">
                    {(Object.keys(selectedRecord.classProbabilities) as DefectClass[]).map((cls) => {
                      const prob = selectedRecord.classProbabilities[cls];
                      return (
                        <div key={cls} className="flex flex-col gap-0.5">
                          <div className="flex justify-between text-[11px]">
                            <span className="text-slate-400 capitalize">{cls.replace("_", " ")}</span>
                            <span className="text-slate-200 font-bold">{(prob * 100).toFixed(1)}%</span>
                          </div>
                          <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                cls === "good" ? "bg-emerald-400" : "bg-rose-400"
                              }`}
                              style={{ width: `${prob * 100}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800 mt-4 text-[11px] text-slate-400">
                  <div>Anomaly Score: {selectedRecord.anomalyScore.toFixed(3)}</div>
                  <div>Pass Threshold: &lt;{selectedRecord.thresholdPass.toFixed(3)}</div>
                  <div>Reject Threshold: &gt;={selectedRecord.thresholdReject.toFixed(3)}</div>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3 border-t border-slate-800 bg-slate-950/50 flex justify-end">
              <button
                onClick={() => setSelectedRecord(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-mono text-slate-200"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
