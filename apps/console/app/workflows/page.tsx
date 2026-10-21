"use client";

import { useState, useMemo, useEffect } from "react";
import {
  GitFork,
  Play,
  RotateCcw,
  CheckCircle2,
  Clock,
  AlertCircle,
  Plus,
  FileCode,
  Layers,
  Globe,
  GitBranch,
  UserCheck,
  Shield,
  ArrowRight,
  Download,
  Upload,
  RefreshCw,
  X,
  ChevronRight,
  Sliders,
  Check,
  Zap,
  Info,
} from "lucide-react";
import {
  WorkflowDefinitionUI,
  WorkflowStepUI,
  WorkflowRunUI,
  StepType,
  RunStatus,
  SHIPPED_WORKFLOWS,
  MOCK_RUNS,
} from "@/lib/workflow-data";

export default function WorkflowsPage() {
  // Active workflow & mode
  const [workflows, setWorkflows] = useState<WorkflowDefinitionUI[]>(SHIPPED_WORKFLOWS);
  const [selectedWorkflowName, setSelectedWorkflowName] = useState<string>("retrain-promote");
  const [activeTab, setActiveTab] = useState<"builder" | "yaml" | "runs">("builder");

  // Selected workflow
  const currentWorkflow = useMemo(() => {
    return (
      workflows.find((w) => w.name === selectedWorkflowName) ||
      workflows[0]
    );
  }, [workflows, selectedWorkflowName]);

  // Selected step for side drawer inspector
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const selectedStep = useMemo(() => {
    return currentWorkflow.steps.find((s) => s.id === selectedStepId) || null;
  }, [currentWorkflow, selectedStepId]);

  // YAML editor state
  const [yamlContent, setYamlContent] = useState<string>(currentWorkflow.rawYaml || "");
  useEffect(() => {
    setYamlContent(currentWorkflow.rawYaml || "");
  }, [currentWorkflow]);

  // Runs state
  const [runs, setRuns] = useState<WorkflowRunUI[]>(MOCK_RUNS);
  const [activeRunId, setActiveRunId] = useState<string>("run-7c33-4a12");
  const [isTriggering, setIsTriggering] = useState<boolean>(false);
  const [signalSuccess, setSignalSuccess] = useState<string | null>(null);

  const activeRun = useMemo(() => {
    return runs.find((r) => r.id === activeRunId) || runs[0];
  }, [runs, activeRunId]);

  // Add Step Modal
  const [isAddStepOpen, setIsAddStepOpen] = useState<boolean>(false);
  const [newStepId, setNewStepId] = useState<string>("");
  const [newStepType, setNewStepType] = useState<StepType>("http");
  const [newStepUrl, setNewStepUrl] = useState<string>("http://localhost:8001/api/endpoint");
  const [newStepMethod, setNewStepMethod] = useState<"GET" | "POST">("POST");

  // Step layout coordinates (DAG column topological rank)
  const layoutNodes = useMemo(() => {
    const steps = currentWorkflow.steps;
    // Calculate in-degree and levels
    const levels: Record<string, number> = {};
    const stepMap = new Map(steps.map((s) => [s.id, s]));

    function getLevel(id: string, visited = new Set<string>()): number {
      if (visited.has(id)) return 0;
      visited.add(id);
      const step = stepMap.get(id);
      if (!step || !step.depends_on || step.depends_on.length === 0) return 0;
      return Math.max(...step.depends_on.map((dep) => getLevel(dep, new Set(visited)) + 1));
    }

    steps.forEach((s) => {
      levels[s.id] = getLevel(s.id);
    });

    // Group steps by level
    const levelGroups: Record<number, WorkflowStepUI[]> = {};
    Object.entries(levels).forEach(([id, lvl]) => {
      if (!levelGroups[lvl]) levelGroups[lvl] = [];
      const s = stepMap.get(id);
      if (s) levelGroups[lvl].push(s);
    });

    const maxLevel = Math.max(0, ...Object.keys(levelGroups).map(Number));
    const nodes: Array<{
      step: WorkflowStepUI;
      x: number;
      y: number;
      level: number;
    }> = [];

    const columnWidth = 260;
    const rowHeight = 130;
    const paddingX = 40;
    const paddingY = 60;

    for (let lvl = 0; lvl <= maxLevel; lvl++) {
      const items = levelGroups[lvl] || [];
      items.forEach((step, idx) => {
        nodes.push({
          step,
          x: paddingX + lvl * columnWidth,
          y: paddingY + idx * rowHeight,
          level: lvl,
        });
      });
    }

    return nodes;
  }, [currentWorkflow]);

  // Edges between steps
  const layoutEdges = useMemo(() => {
    const nodeCoords = new Map(layoutNodes.map((n) => [n.step.id, n]));
    const edges: Array<{
      fromId: string;
      toId: string;
      x1: number;
      y1: number;
      x2: number;
      y2: number;
    }> = [];

    layoutNodes.forEach((target) => {
      if (target.step.depends_on) {
        target.step.depends_on.forEach((depId) => {
          const source = nodeCoords.get(depId);
          if (source) {
            edges.push({
              fromId: depId,
              toId: target.step.id,
              x1: source.x + 200,
              y1: source.y + 40,
              x2: target.x,
              y2: target.y + 40,
            });
          }
        });
      }
    });

    return edges;
  }, [layoutNodes]);

  // Trigger New Workflow Run
  const handleTriggerRun = () => {
    setIsTriggering(true);
    setTimeout(() => {
      const newRunId = `run-${Math.random().toString(36).substring(2, 6)}-${Math.random().toString(36).substring(2, 6)}`;
      const newRun: WorkflowRunUI = {
        id: newRunId,
        workflow_name: currentWorkflow.name,
        workflow_version: currentWorkflow.version,
        status: "running",
        started_at: new Date().toISOString(),
        step_states: Object.fromEntries(
          currentWorkflow.steps.map((s, idx) => [s.id, idx === 0 ? "running" : "pending"])
        ),
        events: [
          {
            id: `evt-${Date.now()}-1`,
            run_id: newRunId,
            sequence_num: 1,
            event_type: "run_started",
            timestamp: new Date().toISOString(),
          },
          {
            id: `evt-${Date.now()}-2`,
            run_id: newRunId,
            sequence_num: 2,
            event_type: "step_started",
            step_id: currentWorkflow.steps[0]?.id,
            timestamp: new Date().toISOString(),
          },
        ],
      };
      setRuns([newRun, ...runs]);
      setActiveRunId(newRunId);
      setIsTriggering(false);
      setActiveTab("runs");
    }, 600);
  };

  // Signal Approval for Suspended Runs
  const handleDeliverSignal = (signalName: string) => {
    if (!activeRun || activeRun.status !== "suspended") return;
    setSignalSuccess(`Delivered signal "${signalName}". Resuming workflow execution.`);

    setTimeout(() => {
      setRuns((prev) =>
        prev.map((r) => {
          if (r.id !== activeRun.id) return r;
          const nextStepStates = { ...r.step_states };
          if (r.suspended_at_step) {
            nextStepStates[r.suspended_at_step] = "completed";
          }
          // Advance next pending step if any
          const steps = currentWorkflow.steps;
          const remaining = steps.filter((s) => nextStepStates[s.id] === "pending");
          if (remaining.length > 0) {
            nextStepStates[remaining[0].id] = "completed";
          }

          return {
            ...r,
            status: "completed",
            finished_at: new Date().toISOString(),
            duration_ms: 182000,
            step_states: nextStepStates,
            events: [
              ...r.events,
              {
                id: `evt-${Date.now()}-sig`,
                run_id: r.id,
                sequence_num: r.events.length + 1,
                event_type: "signal_received",
                timestamp: new Date().toISOString(),
                payload: { signal: signalName, user: "M. Yilmaz (Quality Lead)" },
              },
              {
                id: `evt-${Date.now()}-comp`,
                run_id: r.id,
                sequence_num: r.events.length + 2,
                event_type: "run_completed",
                timestamp: new Date().toISOString(),
              },
            ],
          };
        })
      );
      setSignalSuccess(null);
    }, 1200);
  };

  // Add Step Handler
  const handleAddStep = () => {
    if (!newStepId.trim()) return;
    const newStep: WorkflowStepUI = {
      id: newStepId.trim(),
      type: newStepType,
      url: newStepType === "http" ? newStepUrl : undefined,
      method: newStepType === "http" ? newStepMethod : undefined,
      depends_on: currentWorkflow.steps.length > 0 ? [currentWorkflow.steps[currentWorkflow.steps.length - 1].id] : [],
      timeout_sec: 60,
    };

    const updatedSteps = [...currentWorkflow.steps, newStep];
    const updatedYaml = `${currentWorkflow.rawYaml || ""}\n  - id: ${newStep.id}\n    type: ${newStep.type}\n    url: "${newStep.url || ""}"\n    method: "${newStep.method || "POST"}"\n`;

    setWorkflows((prev) =>
      prev.map((w) =>
        w.name === currentWorkflow.name
          ? { ...w, steps: updatedSteps, rawYaml: updatedYaml }
          : w
      )
    );

    setIsAddStepOpen(false);
    setNewStepId("");
    setSelectedStepId(newStep.id);
  };

  // Helper for Step Icons
  const renderStepIcon = (type: StepType) => {
    switch (type) {
      case "http":
        return <Globe className="w-4 h-4 text-cyan-400" />;
      case "wait":
        return <Clock className="w-4 h-4 text-amber-400" />;
      case "branch":
        return <GitBranch className="w-4 h-4 text-purple-400" />;
      case "map":
        return <Layers className="w-4 h-4 text-blue-400" />;
      case "human_approval":
        return <UserCheck className="w-4 h-4 text-emerald-400" />;
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Header Bar */}
      <div className="border-b border-slate-800/80 bg-slate-900/60 px-6 py-3.5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-4">
          <div className="w-8 h-8 rounded-lg bg-cyan-950/80 border border-cyan-800 flex items-center justify-center text-cyan-400 shadow-md shadow-cyan-950/40">
            <GitFork className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-sm font-semibold tracking-wide text-slate-100 uppercase">
                Workflow Orchestrator
              </h1>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-800 text-cyan-400 font-medium">
                P8 AIR-GAP ENGINE
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Event-sourced deterministic DAG pipeline builder & runtime inspector
            </p>
          </div>
        </div>

        {/* Workflow Switcher & Mode Tabs */}
        <div className="flex items-center space-x-3">
          <select
            value={selectedWorkflowName}
            onChange={(e) => setSelectedWorkflowName(e.target.value)}
            className="text-xs bg-slate-900 border border-slate-700 rounded-md px-3 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500 font-mono"
          >
            {workflows.map((w) => (
              <option key={w.name} value={w.name}>
                {w.name} (v{w.version})
              </option>
            ))}
          </select>

          {/* View Mode Toggle */}
          <div className="flex items-center bg-slate-900 p-0.5 rounded-lg border border-slate-800 text-xs">
            <button
              onClick={() => setActiveTab("builder")}
              className={`px-3 py-1 rounded-md font-medium transition-colors ${
                activeTab === "builder"
                  ? "bg-cyan-600/20 text-cyan-300 border border-cyan-500/30"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Visual Canvas
            </button>
            <button
              onClick={() => setActiveTab("yaml")}
              className={`flex items-center space-x-1 px-3 py-1 rounded-md font-medium transition-colors ${
                activeTab === "yaml"
                  ? "bg-cyan-600/20 text-cyan-300 border border-cyan-500/30"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <FileCode className="w-3.5 h-3.5" />
              <span>YAML</span>
            </button>
            <button
              onClick={() => setActiveTab("runs")}
              className={`flex items-center space-x-1 px-3 py-1 rounded-md font-medium transition-colors ${
                activeTab === "runs"
                  ? "bg-cyan-600/20 text-cyan-300 border border-cyan-500/30"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Runs ({runs.length})</span>
            </button>
          </div>

          {/* Trigger Run Button */}
          <button
            onClick={handleTriggerRun}
            disabled={isTriggering}
            className="flex items-center space-x-1.5 bg-gradient-to-r from-cyan-600 to-teal-500 hover:from-cyan-500 hover:to-teal-400 text-slate-950 font-semibold px-3.5 py-1.5 rounded-md text-xs shadow-md transition-all disabled:opacity-50"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>{isTriggering ? "Triggering..." : "Trigger Run"}</span>
          </button>
        </div>
      </div>

      {/* Main Workspace Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Tab 1: Visual Canvas */}
        {activeTab === "builder" && (
          <div className="flex-1 flex relative">
            {/* Canvas Surface */}
            <div className="flex-1 overflow-auto bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:24px_24px] p-6 relative">
              {/* Canvas Controls Overlay */}
              <div className="absolute top-4 left-4 z-10 flex items-center space-x-2">
                <button
                  onClick={() => setIsAddStepOpen(true)}
                  className="flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-slate-900/90 border border-slate-700 text-xs text-slate-200 hover:bg-slate-800 transition-colors shadow-lg backdrop-blur-sm"
                >
                  <Plus className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Add Step</span>
                </button>
                <div className="px-3 py-1.5 rounded-md bg-slate-900/90 border border-slate-700 text-xs font-mono text-slate-400 backdrop-blur-sm">
                  Schedule: <span className="text-cyan-300">{currentWorkflow.schedule || "None (On-Demand)"}</span>
                </div>
              </div>

              {/* Interactive SVG Diagram */}
              <div className="min-w-[900px] min-h-[500px] relative pt-12">
                <svg className="absolute inset-0 w-full h-full pointer-events-none z-0">
                  <defs>
                    <linearGradient id="edge-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                      <stop offset="0%" stopColor="#0891b2" stopOpacity="0.8" />
                      <stop offset="100%" stopColor="#14b8a6" stopOpacity="0.8" />
                    </linearGradient>
                    <marker
                      id="arrow"
                      viewBox="0 0 10 10"
                      refX="8"
                      refY="5"
                      markerWidth="6"
                      markerHeight="6"
                      orient="auto-start-reverse"
                    >
                      <path d="M 0 1 L 10 5 L 0 9 z" fill="#14b8a6" />
                    </marker>
                  </defs>
                  {layoutEdges.map((edge, idx) => {
                    const dx = edge.x2 - edge.x1;
                    const c1x = edge.x1 + dx * 0.5;
                    const c1y = edge.y1;
                    const c2x = edge.x1 + dx * 0.5;
                    const c2y = edge.y2;
                    return (
                      <path
                        key={`edge-${idx}`}
                        d={`M ${edge.x1} ${edge.y1} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${edge.x2} ${edge.y2}`}
                        fill="none"
                        stroke="url(#edge-gradient)"
                        strokeWidth="2"
                        strokeDasharray="4 4"
                        className="animate-pulse"
                        markerEnd="url(#arrow)"
                      />
                    );
                  })}
                </svg>

                {/* Render Step Nodes */}
                {layoutNodes.map(({ step, x, y }) => {
                  const isSelected = selectedStepId === step.id;
                  return (
                    <div
                      key={step.id}
                      onClick={() => setSelectedStepId(step.id)}
                      style={{ transform: `translate(${x}px, ${y}px)` }}
                      className={`absolute w-52 p-3.5 rounded-lg border backdrop-blur-md cursor-pointer transition-all shadow-lg z-10 ${
                        isSelected
                          ? "bg-slate-900 border-cyan-400 ring-2 ring-cyan-500/30 shadow-cyan-900/30"
                          : "bg-slate-900/90 border-slate-800 hover:border-slate-700 hover:bg-slate-850"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center space-x-2">
                          <div className="p-1 rounded bg-slate-800 border border-slate-700">
                            {renderStepIcon(step.type)}
                          </div>
                          <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                            {step.type}
                          </span>
                        </div>
                        {step.compensate_with && (
                          <div className="flex items-center text-[10px] text-amber-400 font-mono" title={`Saga Compensation: ${step.compensate_with}`}>
                            <Shield className="w-3 h-3 mr-0.5" />
                            <span>SAGA</span>
                          </div>
                        )}
                      </div>

                      <div className="text-xs font-semibold text-slate-100 font-mono truncate mb-1">
                        {step.id}
                      </div>

                      {step.description && (
                        <div className="text-[11px] text-slate-400 line-clamp-2 leading-snug mb-2">
                          {step.description}
                        </div>
                      )}

                      <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 border-t border-slate-800 pt-2 mt-1">
                        <span>{step.method || "EXEC"}</span>
                        <span>{step.timeout_sec ? `${step.timeout_sec}s` : "default"}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Step Inspector Drawer (Right Panel) */}
            {selectedStep && (
              <div className="w-80 border-l border-slate-800 bg-slate-900/95 p-5 flex flex-col z-20 overflow-y-auto">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <div className="flex items-center space-x-2">
                    <Sliders className="w-4 h-4 text-cyan-400" />
                    <span className="text-xs font-semibold uppercase tracking-wider text-slate-200">
                      Step Inspector
                    </span>
                  </div>
                  <button
                    onClick={() => setSelectedStepId(null)}
                    className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="space-y-4 py-4 text-xs">
                  <div>
                    <label className="text-[10px] uppercase font-mono text-slate-400 block mb-1">
                      Step Identifier
                    </label>
                    <input
                      type="text"
                      disabled
                      value={selectedStep.id}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 font-mono text-slate-300"
                    />
                  </div>

                  <div>
                    <label className="text-[10px] uppercase font-mono text-slate-400 block mb-1">
                      Step Type
                    </label>
                    <input
                      type="text"
                      disabled
                      value={selectedStep.type}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 font-mono text-cyan-400 uppercase font-semibold"
                    />
                  </div>

                  {selectedStep.type === "http" && (
                    <>
                      <div>
                        <label className="text-[10px] uppercase font-mono text-slate-400 block mb-1">
                          HTTP Method & URL
                        </label>
                        <div className="flex space-x-2">
                          <span className="bg-slate-950 border border-slate-800 rounded px-2 py-1.5 font-mono text-emerald-400 font-semibold">
                            {selectedStep.method || "POST"}
                          </span>
                          <input
                            type="text"
                            readOnly
                            value={selectedStep.url || ""}
                            className="flex-1 bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 font-mono text-slate-300 truncate"
                          />
                        </div>
                      </div>

                      <div>
                        <label className="text-[10px] uppercase font-mono text-slate-400 block mb-1">
                          Timeout (Seconds)
                        </label>
                        <input
                          type="number"
                          readOnly
                          value={selectedStep.timeout_sec || 60}
                          className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 font-mono text-slate-300"
                        />
                      </div>
                    </>
                  )}

                  {selectedStep.type === "human_approval" && (
                    <>
                      <div>
                        <label className="text-[10px] uppercase font-mono text-slate-400 block mb-1">
                          Signal Name
                        </label>
                        <input
                          type="text"
                          readOnly
                          value={selectedStep.signal_name || ""}
                          className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 font-mono text-emerald-400 font-semibold"
                        />
                      </div>

                      <div>
                        <label className="text-[10px] uppercase font-mono text-slate-400 block mb-1">
                          Required Approver Role
                        </label>
                        <input
                          type="text"
                          readOnly
                          value={selectedStep.required_role || "Operations Admin"}
                          className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 font-mono text-slate-300"
                        />
                      </div>
                    </>
                  )}

                  <div>
                    <label className="text-[10px] uppercase font-mono text-slate-400 block mb-1">
                      Dependencies (depends_on)
                    </label>
                    <div className="space-y-1">
                      {selectedStep.depends_on && selectedStep.depends_on.length > 0 ? (
                        selectedStep.depends_on.map((dep) => (
                          <div
                            key={dep}
                            className="bg-slate-950 border border-slate-800 px-2 py-1 rounded font-mono text-slate-300 flex items-center justify-between"
                          >
                            <span>{dep}</span>
                            <ArrowRight className="w-3 h-3 text-cyan-400" />
                          </div>
                        ))
                      ) : (
                        <span className="text-slate-500 font-mono italic">None (Root Step)</span>
                      )}
                    </div>
                  </div>

                  {selectedStep.compensate_with && (
                    <div className="p-3 rounded-lg bg-amber-950/20 border border-amber-800/40">
                      <div className="flex items-center space-x-1.5 text-amber-400 font-mono text-[11px] mb-1 font-semibold">
                        <Shield className="w-3.5 h-3.5" />
                        <span>Saga Reverse Compensation</span>
                      </div>
                      <p className="text-[11px] text-slate-400 leading-snug">
                        If this step or any downstream step fails fatally, the engine automatically rolls back via:
                      </p>
                      <div className="font-mono text-xs text-amber-300 mt-1.5 font-semibold">
                        &rarr; {selectedStep.compensate_with}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: YAML Raw View */}
        {activeTab === "yaml" && (
          <div className="flex-1 flex flex-col bg-slate-950 p-6 overflow-hidden">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono text-slate-400">
                Workflow YAML Specification &middot; Event-Sourced Format
              </span>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => {
                    const blob = new Blob([yamlContent], { type: "text/yaml" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `${currentWorkflow.name}.yaml`;
                    a.click();
                  }}
                  className="flex items-center space-x-1 px-2.5 py-1 rounded bg-slate-900 border border-slate-700 text-xs text-slate-300 hover:text-white"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download</span>
                </button>
              </div>
            </div>
            <textarea
              value={yamlContent}
              onChange={(e) => setYamlContent(e.target.value)}
              className="flex-1 w-full bg-slate-900 border border-slate-800 rounded-lg p-4 font-mono text-xs text-slate-200 focus:outline-none focus:border-cyan-500 resize-none leading-relaxed"
              spellCheck={false}
            />
          </div>
        )}

        {/* Tab 3: Execution Runs & Signal Delivery */}
        {activeTab === "runs" && (
          <div className="flex-1 flex overflow-hidden">
            {/* Left: Runs Table */}
            <div className="w-96 border-r border-slate-800 bg-slate-900/40 flex flex-col">
              <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Workflow Execution Runs
                </span>
                <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded">
                  {runs.length} total
                </span>
              </div>
              <div className="flex-1 overflow-y-auto divide-y divide-slate-800">
                {runs.map((r) => {
                  const isSelected = r.id === activeRunId;
                  return (
                    <div
                      key={r.id}
                      onClick={() => setActiveRunId(r.id)}
                      className={`p-3.5 cursor-pointer transition-colors ${
                        isSelected ? "bg-slate-800/80 border-l-2 border-cyan-400" : "hover:bg-slate-800/40"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-mono text-xs font-semibold text-slate-200">
                          {r.id}
                        </span>
                        <span
                          className={`text-[10px] font-mono px-2 py-0.5 rounded uppercase font-semibold ${
                            r.status === "completed"
                              ? "bg-emerald-950/80 text-emerald-300 border border-emerald-800"
                              : r.status === "suspended"
                              ? "bg-amber-950/80 text-amber-300 border border-amber-800 animate-pulse"
                              : "bg-cyan-950/80 text-cyan-300 border border-cyan-800"
                          }`}
                        >
                          {r.status}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-400 font-mono truncate">
                        {r.workflow_name} (v{r.workflow_version})
                      </div>
                      <div className="text-[10px] text-slate-500 font-mono mt-1">
                        Started: {new Date(r.started_at).toLocaleTimeString()}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Right: Active Run Detail & Human Approval Gate */}
            {activeRun && (
              <div className="flex-1 flex flex-col overflow-y-auto p-6 space-y-6">
                {/* Run Status Header */}
                <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between">
                  <div>
                    <div className="flex items-center space-x-3 mb-1">
                      <span className="font-mono text-sm font-bold text-slate-100">
                        {activeRun.id}
                      </span>
                      <span
                        className={`text-xs font-mono px-2.5 py-0.5 rounded-full uppercase font-semibold ${
                          activeRun.status === "completed"
                            ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                            : activeRun.status === "suspended"
                            ? "bg-amber-950 text-amber-300 border border-amber-800 animate-pulse"
                            : "bg-cyan-950 text-cyan-400 border border-cyan-800"
                        }`}
                      >
                        {activeRun.status}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 font-mono">
                      Workflow: <span className="text-slate-200">{activeRun.workflow_name}</span> &middot; Started at:{" "}
                      {new Date(activeRun.started_at).toLocaleString()}
                    </p>
                  </div>
                  {activeRun.duration_ms && (
                    <div className="text-right">
                      <span className="text-[10px] uppercase font-mono text-slate-400 block">Duration</span>
                      <span className="text-xs font-mono text-slate-200">
                        {(activeRun.duration_ms / 1000).toFixed(1)}s
                      </span>
                    </div>
                  )}
                </div>

                {/* Human Approval Gate Action Banner (if suspended) */}
                {activeRun.status === "suspended" && (
                  <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-700/50 shadow-lg shadow-amber-950/20">
                    <div className="flex items-start justify-between">
                      <div className="flex items-start space-x-3">
                        <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                        <div>
                          <h2 className="text-sm font-semibold text-amber-300">
                            Action Required: Human Approval Gate Suspended
                          </h2>
                          <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                            Run is parked at step <code className="text-amber-300 font-mono">{activeRun.suspended_at_step}</code>.
                            Awaiting verification signal from authorized Quality Lead / Operations Admin.
                          </p>
                          <div className="mt-2 text-xs font-mono text-slate-400">
                            Signal Name: <span className="text-amber-400 font-semibold">{activeRun.required_signal}</span>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => handleDeliverSignal(activeRun.required_signal || "promote_approved")}
                          className="flex items-center space-x-1.5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-semibold text-xs transition-colors shadow-md"
                        >
                          <Check className="w-4 h-4" />
                          <span>Approve & Deliver Signal</span>
                        </button>
                      </div>
                    </div>
                    {signalSuccess && (
                      <div className="mt-3 p-2 rounded bg-emerald-950/50 border border-emerald-800 text-emerald-300 text-xs font-mono">
                        {signalSuccess}
                      </div>
                    )}
                  </div>
                )}

                {/* Step Progression Timeline */}
                <div className="p-5 rounded-xl bg-slate-900 border border-slate-800">
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300 mb-4">
                    Step Progression & States
                  </h2>
                  <div className="space-y-3">
                    {Object.entries(activeRun.step_states).map(([stepId, state]) => (
                      <div
                        key={stepId}
                        className="flex items-center justify-between p-3 rounded-lg bg-slate-950 border border-slate-800 font-mono text-xs"
                      >
                        <div className="flex items-center space-x-3">
                          {state === "completed" && <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
                          {state === "running" && <RefreshCw className="w-4 h-4 text-cyan-400 animate-spin" />}
                          {state === "pending" && <Clock className="w-4 h-4 text-slate-500" />}
                          <span className="font-semibold text-slate-200">{stepId}</span>
                        </div>
                        <span
                          className={`text-[10px] uppercase px-2 py-0.5 rounded font-semibold ${
                            state === "completed"
                              ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                              : state === "running"
                              ? "bg-cyan-950 text-cyan-400 border border-cyan-800"
                              : "bg-slate-900 text-slate-400 border border-slate-800"
                          }`}
                        >
                          {state}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Event-Sourced Replay Log */}
                <div className="p-5 rounded-xl bg-slate-900 border border-slate-800">
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300 mb-3">
                    Append-Only Event Sourced Audit Log
                  </h2>
                  <div className="space-y-2">
                    {activeRun.events.map((evt) => (
                      <div
                        key={evt.id}
                        className="p-2.5 rounded bg-slate-950 border border-slate-850 font-mono text-xs flex items-center justify-between"
                      >
                        <div className="flex items-center space-x-3">
                          <span className="text-slate-500 text-[10px]">#{evt.sequence_num}</span>
                          <span className="text-cyan-400 font-semibold">{evt.event_type}</span>
                          {evt.step_id && <span className="text-slate-300">&rarr; {evt.step_id}</span>}
                        </div>
                        <span className="text-slate-500 text-[11px]">
                          {new Date(evt.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Modal: Add Step */}
      {isAddStepOpen && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
              <h2 className="text-sm font-semibold text-slate-100 uppercase tracking-wide">
                Add Workflow Step
              </h2>
              <button
                onClick={() => setIsAddStepOpen(false)}
                className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <label className="text-[10px] uppercase font-mono text-slate-400 block mb-1">
                  Step Identifier
                </label>
                <input
                  type="text"
                  placeholder="e.g. notify_operator"
                  value={newStepId}
                  onChange={(e) => setNewStepId(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="text-[10px] uppercase font-mono text-slate-400 block mb-1">
                  Step Type
                </label>
                <select
                  value={newStepType}
                  onChange={(e) => setNewStepType(e.target.value as StepType)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
                >
                  <option value="http">HTTP Request</option>
                  <option value="wait">Timer Wait</option>
                  <option value="branch">Branch Condition</option>
                  <option value="map">Parallel Map Fan-Out</option>
                  <option value="human_approval">Human Approval Gate</option>
                </select>
              </div>

              {newStepType === "http" && (
                <div>
                  <label className="text-[10px] uppercase font-mono text-slate-400 block mb-1">
                    HTTP Target Endpoint
                  </label>
                  <input
                    type="text"
                    value={newStepUrl}
                    onChange={(e) => setNewStepUrl(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
                  />
                </div>
              )}
            </div>

            <div className="flex items-center justify-end space-x-2 mt-6 pt-4 border-t border-slate-800">
              <button
                onClick={() => setIsAddStepOpen(false)}
                className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs"
              >
                Cancel
              </button>
              <button
                onClick={handleAddStep}
                disabled={!newStepId.trim()}
                className="px-4 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-semibold text-xs disabled:opacity-50"
              >
                Insert Step
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
