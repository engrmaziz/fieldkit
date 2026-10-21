"use client";

import { useState, useMemo } from "react";
import {
  Camera,
  Video,
  AlertTriangle,
  ShieldAlert,
  CheckCircle2,
  Clock,
  Search,
  Sparkles,
  Filter,
  Layers,
  Activity,
  Eye,
  Play,
  Maximize2,
  RefreshCw,
  Sliders,
  X,
  User,
  Truck,
  HardHat,
  Crosshair,
  MapPin,
  ArrowRight,
  ChevronRight,
  Info,
  ShieldCheck,
  Check,
} from "lucide-react";
import {
  MOCK_CAMERAS,
  MOCK_EVENTS,
  MOCK_ZONES,
  MOCK_PERSON_JOURNEY,
  CameraInfo,
  VisionEventUI,
  VisionZone,
} from "@/lib/vision-data";

export default function VisionPage() {
  const [cameras, setCameras] = useState<CameraInfo[]>(MOCK_CAMERAS);
  const [events, setEvents] = useState<VisionEventUI[]>(MOCK_EVENTS);
  const [zones, setZones] = useState<VisionZone[]>(MOCK_ZONES);
  const [activeTab, setActiveTab] = useState<
    "wall" | "events" | "journey" | "diagnostics" | "zones"
  >("wall");

  // Filter and Search States
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCameraFilter, setSelectedCameraFilter] = useState<string>("all");
  const [selectedRuleFilter, setSelectedRuleFilter] = useState<string>("all");
  const [selectedSeverityFilter, setSelectedSeverityFilter] = useState<string>("all");
  const [activeChips, setActiveChips] = useState<string[]>([]);

  // Modal States
  const [selectedEvent, setSelectedEvent] = useState<VisionEventUI | null>(null);
  const [zoomedCamera, setZoomedCamera] = useState<CameraInfo | null>(null);
  const [selectedZoneCam, setSelectedZoneCam] = useState<string>("cam1_press");
  const [zoneSaveSuccess, setZoneSaveSuccess] = useState<string | null>(null);

  // Suggestion presets for natural language search
  const NL_SUGGESTIONS = [
    "Critical forklift proximity alerts in logistics",
    "Missing helmet in press bed today",
    "Perimeter boundary cross warning",
    "Loitering dwell alerts in assembly bay",
    "Track person_0001 movements across plant",
  ];

  // Natural Language Search simulation
  const handleNLSearch = (query: string) => {
    setSearchQuery(query);
    const q = query.toLowerCase();
    const chips: string[] = [];

    let cam = "all";
    if (q.includes("press") || q.includes("cam1")) {
      cam = "cam1_press";
      chips.push("Camera: Press Bed (cam1)");
    } else if (q.includes("logistics") || q.includes("cam2")) {
      cam = "cam2_logistics";
      chips.push("Camera: Logistics Corridor (cam2)");
    } else if (q.includes("assembly") || q.includes("cam3")) {
      cam = "cam3_assembly";
      chips.push("Camera: Assembly Bay 4 (cam3)");
    } else if (q.includes("perimeter") || q.includes("cam4")) {
      cam = "cam4_perimeter";
      chips.push("Camera: Perimeter Gate (cam4)");
    }

    let rule = "all";
    if (q.includes("proximity") || q.includes("forklift") || q.includes("near")) {
      rule = "forklift_pedestrian_proximity";
      chips.push("Rule: Proximity (<2.0m)");
    } else if (q.includes("helmet") || q.includes("ppe") || q.includes("hard hat")) {
      rule = "zone_ppe_missing";
      chips.push("Rule: PPE Hard Hat");
    } else if (q.includes("dwell") || q.includes("loiter")) {
      rule = "dwell";
      chips.push("Rule: Zone Dwell");
    } else if (q.includes("perimeter") || q.includes("cross") || q.includes("boundary")) {
      rule = "line_cross";
      chips.push("Rule: Line Crossing");
    }

    let sev = "all";
    if (q.includes("critical") || q.includes("danger")) {
      sev = "CRITICAL";
      chips.push("Severity: CRITICAL");
    } else if (q.includes("warn") || q.includes("warning")) {
      sev = "WARNING";
      chips.push("Severity: WARNING");
    }

    if (q.includes("person_0001")) {
      chips.push("Person: person_0001");
    }

    setSelectedCameraFilter(cam);
    setSelectedRuleFilter(rule);
    setSelectedSeverityFilter(sev);
    setActiveChips(chips);
  };

  const clearFilters = () => {
    setSearchQuery("");
    setSelectedCameraFilter("all");
    setSelectedRuleFilter("all");
    setSelectedSeverityFilter("all");
    setActiveChips([]);
  };

  // Filtered Events
  const filteredEvents = useMemo(() => {
    return events.filter((evt) => {
      if (selectedCameraFilter !== "all" && evt.camera_id !== selectedCameraFilter) return false;
      if (selectedRuleFilter !== "all" && evt.rule_type !== selectedRuleFilter) return false;
      if (selectedSeverityFilter !== "all" && evt.severity !== selectedSeverityFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesText =
          evt.details.toLowerCase().includes(q) ||
          evt.camera_name.toLowerCase().includes(q) ||
          evt.event_id.toLowerCase().includes(q) ||
          (evt.global_person_id && evt.global_person_id.toLowerCase().includes(q));
        if (!matchesText && activeChips.length === 0) return false;
      }
      return true;
    });
  }, [events, selectedCameraFilter, selectedRuleFilter, selectedSeverityFilter, searchQuery, activeChips]);

  // Handle Zone Coordinate Update
  const handleZoneUpdate = (zoneId: string, updatedName: string) => {
    setZones((prev) =>
      prev.map((z) => (z.id === zoneId ? { ...z, name: updatedName } : z))
    );
    setZoneSaveSuccess(`Updated polygon configuration for ${zoneId} on edge node.`);
    setTimeout(() => setZoneSaveSuccess(null), 3500);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8 font-sans">
      {/* Top Banner / Breadcrumb */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-slate-800/80 gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/20 border border-cyan-400/30 flex items-center justify-center text-cyan-400">
              <Camera className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-xl font-bold tracking-tight text-slate-100">
                  Vision Edge Intelligence Wall
                </h1>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-800 text-cyan-300 font-semibold">
                  Project 5: Multi-Camera
                </span>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-800 text-emerald-300 font-semibold flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Edge 5 FPS Ingest
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono">
                DE-HAM Stamping & Assembly Plant • RTSP Stream Farm • ByteTrack & Deterministic Safety Rules
              </p>
            </div>
          </div>
        </div>

        {/* Global Live Stats */}
        <div className="flex items-center space-x-3">
          <div className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center space-x-2">
            <Video className="w-3.5 h-3.5 text-cyan-400" />
            <div className="text-left">
              <span className="text-[10px] text-slate-400 font-mono block">Cameras Active</span>
              <span className="text-xs font-bold text-slate-200">4 / 4 Live (100%)</span>
            </div>
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center space-x-2">
            <Activity className="w-3.5 h-3.5 text-emerald-400" />
            <div className="text-left">
              <span className="text-[10px] text-slate-400 font-mono block">Throughput Rate</span>
              <span className="text-xs font-bold text-slate-200">19.8 FPS Aggregate</span>
            </div>
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center space-x-2">
            <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
            <div className="text-left">
              <span className="text-[10px] text-slate-400 font-mono block">Active Alerts (24h)</span>
              <span className="text-xs font-bold text-rose-400">{events.length} Events Logged</span>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center space-x-2 mt-6 border-b border-slate-800/80 pb-3">
        {[
          { id: "wall", label: "4-Camera Live Wall", icon: Video, badge: "4 Live" },
          { id: "events", label: "Event Log & Clips", icon: ShieldAlert, badge: `${filteredEvents.length}` },
          { id: "journey", label: "Re-ID Person Journey", icon: User, badge: "OSNet 512d" },
          { id: "diagnostics", label: "Camera Diagnostics", icon: Activity, badge: "Health 100%" },
          { id: "zones", label: "Zone Configuration", icon: Layers, badge: `${zones.length} Zones` },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                isActive
                  ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
              <span
                className={`text-[9px] font-mono px-1.5 py-0.2 rounded border ${
                  isActive
                    ? "bg-cyan-950/60 border-cyan-800 text-cyan-300"
                    : "bg-slate-800 border-slate-700 text-slate-400"
                }`}
              >
                {tab.badge}
              </span>
            </button>
          );
        })}
      </div>

      {/* TAB 1: 4-CAMERA LIVE WALL */}
      {activeTab === "wall" && (
        <div className="mt-6 space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {cameras.map((cam) => {
              const camZones = zones.filter((z) => z.camera_id === cam.camera_id);
              return (
                <div
                  key={cam.camera_id}
                  className="rounded-xl border border-slate-800 bg-slate-900/70 overflow-hidden shadow-xl flex flex-col transition-all hover:border-slate-700"
                >
                  {/* Camera Card Header */}
                  <div className="px-4 py-2.5 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between">
                    <div className="flex items-center space-x-2.5">
                      <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                      <div>
                        <span className="text-xs font-bold text-slate-200 block">{cam.name}</span>
                        <span className="text-[10px] text-slate-400 font-mono">{cam.location}</span>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-cyan-300">
                        {cam.fps.toFixed(1)} FPS
                      </span>
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                          cam.status === "HEALTHY"
                            ? "bg-emerald-950/60 border-emerald-800 text-emerald-300"
                            : "bg-amber-950/60 border-amber-800 text-amber-300"
                        }`}
                      >
                        {cam.status}
                      </span>
                      <button
                        onClick={() => setZoomedCamera(cam)}
                        className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
                        title="Expand Stream"
                      >
                        <Maximize2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Synthetic Stream Canvas & Detection Overlays */}
                  <div className="relative aspect-video bg-slate-950 border-b border-slate-800/80 overflow-hidden group">
                    {/* Background Visual Grid */}
                    <div
                      className="absolute inset-0 opacity-15"
                      style={{
                        backgroundImage: `radial-gradient(circle at 1px 1px, #06b6d4 1px, transparent 0)`,
                        backgroundSize: "24px 24px",
                      }}
                    />

                    {/* Industrial Plant Perspective Lines */}
                    <svg className="absolute inset-0 w-full h-full pointer-events-none">
                      {/* Floor Homography Grid Lines */}
                      <line x1="0" y1="90%" x2="50%" y2="40%" stroke="#1e293b" strokeWidth="1" strokeDasharray="4 4" />
                      <line x1="100%" y1="90%" x2="50%" y2="40%" stroke="#1e293b" strokeWidth="1" strokeDasharray="4 4" />
                      <line x1="20%" y1="90%" x2="45%" y2="40%" stroke="#0e7490" strokeWidth="0.8" strokeDasharray="2 2" opacity="0.4" />
                      <line x1="80%" y1="90%" x2="55%" y2="40%" stroke="#0e7490" strokeWidth="0.8" strokeDasharray="2 2" opacity="0.4" />

                      {/* Configured Zones Overlay */}
                      {camZones.map((z) => {
                        const pointsStr = z.polygon
                          .map(([x, y]) => `${(x / 800) * 100}%,${(y / 700) * 100}%`)
                          .join(" ");
                        return (
                          <polygon
                            key={z.id}
                            points={pointsStr}
                            fill={z.color}
                            fillOpacity="0.12"
                            stroke={z.color}
                            strokeWidth="1.5"
                            strokeDasharray="4 2"
                          />
                        );
                      })}
                    </svg>

                    {/* Interactive Detections per Camera */}
                    {cam.camera_id === "cam1_press" && (
                      <>
                        {/* Worker 1: Missing Helmet */}
                        <div className="absolute top-[42%] left-[28%] border-2 border-rose-500 rounded p-1 bg-rose-950/40 backdrop-blur-xs text-[9px] font-mono animate-pulse">
                          <div className="flex items-center space-x-1 text-rose-300">
                            <AlertTriangle className="w-3 h-3 text-rose-400" />
                            <span>PID #88 • NO HELMET</span>
                          </div>
                          <div className="text-[8px] text-slate-300">Press Danger Zone • 0.94</div>
                        </div>

                        {/* Worker 2: Compliant */}
                        <div className="absolute top-[48%] left-[58%] border border-emerald-500 rounded p-1 bg-emerald-950/30 text-[9px] font-mono">
                          <div className="flex items-center space-x-1 text-emerald-300">
                            <ShieldCheck className="w-3 h-3 text-emerald-400" />
                            <span>PID #91 • HELMET OK</span>
                          </div>
                        </div>

                        {/* Stamping Press Machine Model Label */}
                        <div className="absolute top-[20%] left-[34%] px-2 py-0.5 rounded bg-slate-900/90 border border-slate-700 text-[10px] font-mono text-slate-300">
                          HYDRAULIC PRESS 2000T [ACTIVE]
                        </div>
                      </>
                    )}

                    {cam.camera_id === "cam2_logistics" && (
                      <>
                        {/* Forklift 3 with Proximity Box */}
                        <div className="absolute top-[38%] left-[36%] border-2 border-amber-500 rounded p-1.5 bg-amber-950/40 text-[9px] font-mono">
                          <div className="flex items-center space-x-1 text-amber-300">
                            <Truck className="w-3.5 h-3.5 text-amber-400" />
                            <span>FORKLIFT #3 • 1.4 m/s</span>
                          </div>
                          <div className="text-[8px] text-slate-300">Speed: 1.4m/s • Lane East</div>
                        </div>

                        {/* Pedestrian Crossing in Corridor */}
                        <div className="absolute top-[55%] left-[24%] border-2 border-rose-500 rounded p-1 bg-rose-950/40 text-[9px] font-mono animate-pulse">
                          <div className="flex items-center space-x-1 text-rose-300">
                            <AlertTriangle className="w-3 h-3 text-rose-400" />
                            <span>PROXIMITY BREACH (1.38m)</span>
                          </div>
                          <div className="text-[8px] text-slate-300">PID #104 (person_0001)</div>
                        </div>
                      </>
                    )}

                    {cam.camera_id === "cam3_assembly" && (
                      <>
                        {/* Assembly Cell Workstation */}
                        <div className="absolute top-[35%] left-[20%] border border-cyan-500 rounded p-1 bg-cyan-950/30 text-[9px] font-mono">
                          <span className="text-cyan-300">PID #119 • DWELL 320s</span>
                        </div>
                        <div className="absolute top-[45%] left-[62%] border border-emerald-500 rounded p-1 bg-emerald-950/30 text-[9px] font-mono">
                          <span className="text-emerald-300">PID #124 • PPE PASS</span>
                        </div>
                        {/* Lens smear warning badge */}
                        <div className="absolute bottom-2 left-2 px-2 py-1 rounded bg-amber-950/80 border border-amber-700 text-[10px] font-mono text-amber-300 flex items-center space-x-1">
                          <AlertTriangle className="w-3 h-3" />
                          <span>Diagnostics: Lens Smear (Blur Score: 74.6 &lt; 80)</span>
                        </div>
                      </>
                    )}

                    {cam.camera_id === "cam4_perimeter" && (
                      <>
                        <div className="absolute top-[52%] left-[45%] border border-indigo-500 rounded p-1 bg-indigo-950/30 text-[9px] font-mono">
                          <span className="text-indigo-300">PID #202 • Security Gate</span>
                        </div>
                        <div className="absolute top-[68%] left-[10%] px-2 py-0.5 rounded bg-slate-900/90 border border-slate-700 text-[9px] font-mono text-slate-400">
                          ANTI-TRESPASS TRIPWIRE LINE ARMED
                        </div>
                      </>
                    )}

                    {/* Stream Live OSD Watermark */}
                    <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded bg-black/80 font-mono text-[9px] text-slate-400 border border-slate-800">
                      RTSP • 1920x1080 • ByteTrack Active
                    </div>
                  </div>

                  {/* Camera Card Footer Telemetry */}
                  <div className="p-3 bg-slate-900/60 flex items-center justify-between text-xs font-mono">
                    <div className="flex items-center space-x-4">
                      <div>
                        <span className="text-slate-400 text-[10px] block">Tracks</span>
                        <span className="text-slate-200 font-bold">
                          {cam.active_tracks.persons} Persons • {cam.active_tracks.forklifts} Forklifts
                        </span>
                      </div>
                      <div className="hidden sm:block">
                        <span className="text-slate-400 text-[10px] block">Sharpness (Laplacian)</span>
                        <span
                          className={`font-semibold ${
                            cam.blur_score < 80 ? "text-amber-400" : "text-slate-300"
                          }`}
                        >
                          {cam.blur_score.toFixed(1)}
                        </span>
                      </div>
                      <div className="hidden sm:block">
                        <span className="text-slate-400 text-[10px] block">View Shift</span>
                        <span className="text-slate-300 font-semibold">{cam.view_shift_pct.toFixed(1)}%</span>
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        setSelectedZoneCam(cam.camera_id);
                        setActiveTab("zones");
                      }}
                      className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-[11px] font-sans text-cyan-400 border border-slate-700 flex items-center space-x-1"
                    >
                      <Sliders className="w-3 h-3" />
                      <span>Edit Zones</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* TAB 2: EVENTS LOG & NATURAL LANGUAGE SEARCH */}
      {activeTab === "events" && (
        <div className="mt-6 space-y-6">
          {/* Natural Language Query Search Bar & Filter Chips */}
          <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/80 shadow-lg space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Sparkles className="w-4 h-4 text-cyan-400" />
                <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
                  Conversational Safety Query Engine (POST /search/nl)
                </span>
              </div>
              <span className="text-[10px] font-mono text-slate-400">
                Deterministic Tokenizer • Zero SQL Injection • Schema Validated
              </span>
            </div>

            <div className="flex flex-col md:flex-row items-center gap-3">
              <div className="relative flex-1 w-full">
                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleNLSearch(searchQuery);
                  }}
                  placeholder="Ask in natural language: e.g. 'Show critical forklift proximity incidents in logistics corridor'..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-10 pr-4 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
                />
              </div>
              <button
                onClick={() => handleNLSearch(searchQuery)}
                className="w-full md:w-auto px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-semibold text-xs transition-colors flex items-center justify-center space-x-1.5"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Parse & Search</span>
              </button>
              {(searchQuery || activeChips.length > 0) && (
                <button
                  onClick={clearFilters}
                  className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition-colors"
                >
                  Clear
                </button>
              )}
            </div>

            {/* Suggestions Chips */}
            <div className="flex items-center flex-wrap gap-1.5 pt-1">
              <span className="text-[11px] text-slate-400 font-mono mr-1">Presets:</span>
              {NL_SUGGESTIONS.map((sug, idx) => (
                <button
                  key={idx}
                  onClick={() => handleNLSearch(sug)}
                  className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700/60 transition-colors"
                >
                  &ldquo;{sug}&rdquo;
                </button>
              ))}
            </div>

            {/* Active Parsed Chips */}
            {activeChips.length > 0 && (
              <div className="flex items-center flex-wrap gap-2 pt-2 border-t border-slate-800/80">
                <span className="text-[10px] font-mono text-cyan-400 uppercase font-bold">
                  Parsed Query Filters:
                </span>
                {activeChips.map((chip, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded bg-cyan-950/70 border border-cyan-800 text-cyan-300"
                  >
                    <Check className="w-3 h-3 text-cyan-400" />
                    {chip}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Structured Dropdown Filters Bar */}
          <div className="flex items-center justify-between flex-wrap gap-4 text-xs">
            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-1.5 text-slate-400">
                <Filter className="w-3.5 h-3.5" />
                <span>Filter by:</span>
              </div>
              <select
                value={selectedCameraFilter}
                onChange={(e) => setSelectedCameraFilter(e.target.value)}
                className="bg-slate-900 border border-slate-800 rounded px-2.5 py-1 text-slate-300 text-xs focus:outline-none focus:border-cyan-500"
              >
                <option value="all">All Cameras</option>
                {cameras.map((c) => (
                  <option key={c.camera_id} value={c.camera_id}>
                    {c.name}
                  </option>
                ))}
              </select>

              <select
                value={selectedRuleFilter}
                onChange={(e) => setSelectedRuleFilter(e.target.value)}
                className="bg-slate-900 border border-slate-800 rounded px-2.5 py-1 text-slate-300 text-xs focus:outline-none focus:border-cyan-500"
              >
                <option value="all">All Rules</option>
                <option value="forklift_pedestrian_proximity">Proximity (&lt;2.0m)</option>
                <option value="zone_ppe_missing">Missing PPE Helmet</option>
                <option value="line_cross">Line Crossing</option>
                <option value="dwell">Zone Dwell</option>
              </select>

              <select
                value={selectedSeverityFilter}
                onChange={(e) => setSelectedSeverityFilter(e.target.value)}
                className="bg-slate-900 border border-slate-800 rounded px-2.5 py-1 text-slate-300 text-xs focus:outline-none focus:border-cyan-500"
              >
                <option value="all">All Severities</option>
                <option value="CRITICAL">Critical Only</option>
                <option value="WARNING">Warning</option>
                <option value="INFO">Info</option>
              </select>
            </div>

            <div className="text-[11px] font-mono text-slate-400">
              Showing <span className="text-slate-200 font-bold">{filteredEvents.length}</span> of {events.length} safety incidents
            </div>
          </div>

          {/* Events Table */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden shadow-lg">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-mono text-[11px]">
                  <tr>
                    <th className="px-4 py-3">Event ID</th>
                    <th className="px-4 py-3">Timestamp</th>
                    <th className="px-4 py-3">Camera & Zone</th>
                    <th className="px-4 py-3">Rule Type</th>
                    <th className="px-4 py-3">Severity</th>
                    <th className="px-4 py-3">Track / Person</th>
                    <th className="px-4 py-3">Metric / Details</th>
                    <th className="px-4 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {filteredEvents.map((evt) => (
                    <tr
                      key={evt.event_id}
                      className="hover:bg-slate-800/40 transition-colors cursor-pointer"
                      onClick={() => setSelectedEvent(evt)}
                    >
                      <td className="px-4 py-3 font-mono text-cyan-400 font-medium">
                        {evt.event_id}
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-400 text-[11px]">
                        {new Date(evt.timestamp).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                        })}
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-semibold text-slate-200">{evt.camera_name}</div>
                        <div className="text-[10px] text-slate-400 font-mono">{evt.zone_id}</div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1 font-mono text-[11px] text-slate-300">
                          {evt.rule_type === "forklift_pedestrian_proximity" && (
                            <Truck className="w-3.5 h-3.5 text-amber-400" />
                          )}
                          {evt.rule_type === "zone_ppe_missing" && (
                            <HardHat className="w-3.5 h-3.5 text-rose-400" />
                          )}
                          {evt.rule_type === "line_cross" && (
                            <Crosshair className="w-3.5 h-3.5 text-indigo-400" />
                          )}
                          {evt.rule_type === "dwell" && (
                            <Clock className="w-3.5 h-3.5 text-cyan-400" />
                          )}
                          {evt.rule_type.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold border ${
                            evt.severity === "CRITICAL"
                              ? "bg-rose-950/60 border-rose-800 text-rose-400"
                              : evt.severity === "WARNING"
                              ? "bg-amber-950/60 border-amber-800 text-amber-300"
                              : "bg-cyan-950/60 border-cyan-800 text-cyan-300"
                          }`}
                        >
                          <AlertTriangle className="w-3 h-3" />
                          {evt.severity}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-[11px]">
                        <div className="text-slate-200">
                          {evt.global_person_id || `Track #${evt.track_id}`}
                        </div>
                        <div className="text-slate-400 text-[10px]">
                          {(evt.confidence * 100).toFixed(1)}% Conf
                        </div>
                      </td>
                      <td className="px-4 py-3 max-w-xs truncate text-slate-300">
                        {evt.details}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedEvent(evt);
                          }}
                          className="px-2.5 py-1 rounded bg-cyan-600/20 hover:bg-cyan-600/40 text-cyan-300 border border-cyan-500/40 font-mono text-[10px] inline-flex items-center space-x-1"
                        >
                          <Play className="w-3 h-3" />
                          <span>View Clip</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                  {filteredEvents.length === 0 && (
                    <tr>
                      <td colSpan={8} className="px-4 py-8 text-center text-slate-400">
                        No violation events matched the current filter criteria.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: CROSS-CAMERA PERSON JOURNEY RE-ID */}
      {activeTab === "journey" && (
        <div className="mt-6 space-y-6">
          <div className="p-6 rounded-xl border border-slate-800 bg-slate-900/80 shadow-lg space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
              <div>
                <div className="flex items-center space-x-2">
                  <User className="w-5 h-5 text-cyan-400" />
                  <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
                    Cross-Camera Re-ID Worker Journey Visualizer
                  </h2>
                </div>
                <p className="text-xs text-slate-400 font-mono mt-1">
                  Reconstructed from 512-dim OSNet embeddings with Cosine Distance &ge; 0.75 & Spatio-Temporal Transit Gating
                </p>
              </div>

              {/* Target Worker Details */}
              <div className="flex items-center space-x-3 px-3 py-2 rounded-lg bg-slate-950 border border-slate-800">
                <div className="w-7 h-7 rounded-full bg-cyan-600/30 border border-cyan-400 flex items-center justify-center font-bold text-cyan-300 text-xs">
                  01
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-200">
                    {MOCK_PERSON_JOURNEY.person_id}
                  </div>
                  <div className="text-[10px] text-slate-400 font-mono">
                    Shift A • 4 Transit Cameras Visited
                  </div>
                </div>
              </div>
            </div>

            {/* Journey Timeline Progression */}
            <div className="relative pl-6 space-y-8 before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-0.5 before:bg-slate-800">
              {MOCK_PERSON_JOURNEY.steps.map((step, idx) => {
                const hasAlert = step.associated_events.length > 0;
                return (
                  <div key={idx} className="relative group">
                    {/* Node Dot */}
                    <div
                      className={`absolute -left-[27px] top-1.5 w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                        hasAlert
                          ? "bg-rose-950 border-rose-500 text-rose-400 animate-pulse"
                          : "bg-slate-950 border-cyan-400 text-cyan-400"
                      }`}
                    >
                      <div className="w-1.5 h-1.5 rounded-full bg-current" />
                    </div>

                    {/* Step Card */}
                    <div className="p-4 rounded-lg border border-slate-800 bg-slate-950/80 hover:border-slate-700 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4">
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="text-xs font-bold text-slate-100">
                            {step.camera_name}
                          </span>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-cyan-300 border border-slate-700">
                            {step.camera_id}
                          </span>
                          {hasAlert && (
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-950/80 text-rose-300 border border-rose-700 flex items-center gap-1">
                              <AlertTriangle className="w-3 h-3 text-rose-400" />
                              Rule Incident Triggered
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-slate-400 font-mono mt-1">
                          {step.location}
                        </div>
                        <div className="text-xs text-slate-300 mt-2">
                          {step.thumbnail_desc}
                        </div>
                      </div>

                      {/* Right Telemetry */}
                      <div className="flex items-center space-x-6 text-xs font-mono">
                        <div>
                          <span className="text-[10px] text-slate-500 block">Time In / Out</span>
                          <span className="text-slate-300">
                            {step.entered_at} &rarr; {step.exited_at}
                          </span>
                        </div>
                        <div>
                          <span className="text-[10px] text-slate-500 block">Dwell Time</span>
                          <span className="text-slate-300">{step.duration_sec}s</span>
                        </div>
                        <div>
                          <span className="text-[10px] text-slate-500 block">OSNet Cosine</span>
                          <span className="text-emerald-400 font-semibold">
                            {(step.similarity_score * 100).toFixed(0)}% Match
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: CAMERA DIAGNOSTICS & TELEMETRY */}
      {activeTab === "diagnostics" && (
        <div className="mt-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {cameras.map((cam) => (
              <div
                key={cam.camera_id}
                className="p-5 rounded-xl border border-slate-800 bg-slate-900/80 shadow-lg space-y-4"
              >
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div>
                    <h3 className="text-xs font-bold text-slate-200">{cam.name}</h3>
                    <p className="text-[10px] font-mono text-slate-400">{cam.location}</p>
                  </div>
                  <span
                    className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                      cam.status === "HEALTHY"
                        ? "bg-emerald-950/60 border-emerald-800 text-emerald-300"
                        : "bg-amber-950/60 border-amber-800 text-amber-300"
                    }`}
                  >
                    {cam.status}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-4 text-xs font-mono">
                  {/* Blur Score Metric */}
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                    <div className="flex items-center justify-between text-slate-400 text-[10px]">
                      <span>Lens Sharpness (Laplacian)</span>
                      <span>Target &ge; 80.0</span>
                    </div>
                    <div className="text-base font-bold mt-1 flex items-center justify-between">
                      <span className={cam.blur_score < 80 ? "text-amber-400" : "text-emerald-400"}>
                        {cam.blur_score.toFixed(1)}
                      </span>
                      <span className="text-[10px] text-slate-500">
                        {cam.blur_score < 80 ? "DEFOCUS / SMEAR" : "SHARP"}
                      </span>
                    </div>
                    <div className="w-full h-1.5 bg-slate-800 rounded-full mt-2 overflow-hidden">
                      <div
                        className={`h-full ${cam.blur_score < 80 ? "bg-amber-400" : "bg-emerald-400"}`}
                        style={{ width: `${Math.min(100, (cam.blur_score / 200) * 100)}%` }}
                      />
                    </div>
                  </div>

                  {/* View Shift ORB Metric */}
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                    <div className="flex items-center justify-between text-slate-400 text-[10px]">
                      <span>View Shift / Tamper</span>
                      <span>Target &le; 30%</span>
                    </div>
                    <div className="text-base font-bold mt-1 flex items-center justify-between">
                      <span className={cam.view_shift_pct > 30 ? "text-rose-400" : "text-cyan-400"}>
                        {cam.view_shift_pct.toFixed(1)}%
                      </span>
                      <span className="text-[10px] text-slate-500">
                        {cam.view_shift_pct > 30 ? "MOVED" : "ALIGNED"}
                      </span>
                    </div>
                    <div className="w-full h-1.5 bg-slate-800 rounded-full mt-2 overflow-hidden">
                      <div
                        className="h-full bg-cyan-400"
                        style={{ width: `${Math.min(100, cam.view_shift_pct * 3.3)}%` }}
                      />
                    </div>
                  </div>

                  {/* Frame Stability */}
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                    <span className="text-[10px] text-slate-400 block">Frame Anomaly Status</span>
                    <div className="mt-1 space-y-1 text-[11px]">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Frozen Frame:</span>
                        <span className="text-emerald-400 font-semibold">NO (Diff &gt; 1.0)</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Black Frame:</span>
                        <span className="text-emerald-400 font-semibold">NO (Mean &gt; 15.0)</span>
                      </div>
                    </div>
                  </div>

                  {/* FPS & Ingest Health */}
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                    <span className="text-[10px] text-slate-400 block">Stream Reliability</span>
                    <div className="mt-1 space-y-1 text-[11px]">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Processed Rate:</span>
                        <span className="text-cyan-400 font-semibold">{cam.fps.toFixed(1)} / 5.0 FPS</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Uptime (30d):</span>
                        <span className="text-slate-200 font-semibold">{cam.uptime_pct}%</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 5: ZONE CONFIGURATION EDITOR */}
      {activeTab === "zones" && (
        <div className="mt-6 space-y-6">
          <div className="p-6 rounded-xl border border-slate-800 bg-slate-900/80 shadow-lg space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
              <div>
                <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
                  <Layers className="w-4 h-4 text-cyan-400" />
                  <span>Dynamic Safety Zone Polygon Configuration</span>
                </h2>
                <p className="text-xs text-slate-400 font-mono mt-1">
                  GET/POST /cameras/&#123;camera_id&#125;/zones • Real-time Polygon Containment &amp; Tripwire Geometry
                </p>
              </div>

              {/* Camera Switcher for Zones */}
              <div className="flex items-center space-x-2">
                <span className="text-xs text-slate-400 font-mono">Camera:</span>
                <select
                  value={selectedZoneCam}
                  onChange={(e) => setSelectedZoneCam(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-cyan-300 font-mono focus:outline-none focus:border-cyan-500"
                >
                  {cameras.map((c) => (
                    <option key={c.camera_id} value={c.camera_id}>
                      {c.name} ({c.camera_id})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {zoneSaveSuccess && (
              <div className="p-3 rounded-lg bg-emerald-950/60 border border-emerald-800 text-emerald-300 text-xs font-mono flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>{zoneSaveSuccess}</span>
              </div>
            )}

            {/* Configured Zones List for this Camera */}
            <div className="space-y-4">
              {zones
                .filter((z) => z.camera_id === selectedZoneCam)
                .map((zone) => (
                  <div
                    key={zone.id}
                    className="p-4 rounded-lg border border-slate-800 bg-slate-950/90 space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <span
                          className="w-3 h-3 rounded-full border"
                          style={{ backgroundColor: zone.color, borderColor: zone.color }}
                        />
                        <span className="text-xs font-bold text-slate-200">{zone.name}</span>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-400">
                          {zone.type}
                        </span>
                      </div>
                      <span className="text-[11px] font-mono text-slate-400">ID: {zone.id}</span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                      <div>
                        <span className="text-[10px] text-slate-500 block mb-1">
                          Polygon Vertices [X, Y]:
                        </span>
                        <div className="p-2 rounded bg-slate-900 border border-slate-800 text-[11px] text-slate-300">
                          {zone.polygon.map(([x, y]) => `[${x}, ${y}]`).join(" \u2192 ")}
                        </div>
                      </div>
                      <div className="flex items-end justify-end space-x-2">
                        <button
                          onClick={() =>
                            handleZoneUpdate(zone.id, `${zone.name} (Calibrated)`)
                          }
                          className="px-3 py-1.5 rounded bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-300 border border-cyan-500/30 text-xs font-mono"
                        >
                          Push Geometry to Edge
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}

      {/* EVENT DETAIL & VIDEO CLIP MODAL */}
      {selectedEvent && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-4xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
            {/* Modal Header */}
            <div className="px-6 py-4 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div
                  className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                    selectedEvent.severity === "CRITICAL"
                      ? "bg-rose-950 border border-rose-800 text-rose-400"
                      : "bg-amber-950 border border-amber-800 text-amber-300"
                  }`}
                >
                  <ShieldAlert className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <h3 className="text-sm font-bold text-slate-100">
                      Safety Incident: {selectedEvent.event_id}
                    </h3>
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                        selectedEvent.severity === "CRITICAL"
                          ? "bg-rose-950 border-rose-800 text-rose-400 font-bold"
                          : "bg-amber-950 border-amber-800 text-amber-300"
                      }`}
                    >
                      {selectedEvent.severity}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 font-mono">
                    {selectedEvent.camera_name} • {new Date(selectedEvent.timestamp).toLocaleString()}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                className="p-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-6 overflow-y-auto">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* 10s Video Clip Player Simulation */}
                <div className="space-y-2">
                  <span className="text-xs font-mono text-slate-400 uppercase font-semibold">
                    10-Second Event Clip (5s Pre + 5s Post)
                  </span>
                  <div className="relative aspect-video bg-black rounded-lg border border-slate-800 overflow-hidden flex flex-col justify-between p-3">
                    {/* Simulated Player Overlay */}
                    <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                      <span className="flex items-center gap-1.5 text-rose-400 font-bold">
                        <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping" />
                        REC PLAYBACK
                      </span>
                      <span>MinIO: {selectedEvent.clip_uri}</span>
                    </div>

                    {/* Center Action Indicator */}
                    <div className="flex flex-col items-center justify-center space-y-2 my-auto">
                      <div className="w-12 h-12 rounded-full bg-cyan-600/30 border border-cyan-400/60 flex items-center justify-center text-cyan-300">
                        <Play className="w-6 h-6 fill-current pl-1" />
                      </div>
                      <span className="text-[11px] font-mono text-slate-300">
                        1080p MP4 • H.264
                      </span>
                    </div>

                    {/* GDPR Blur Banner */}
                    <div className="p-2 rounded bg-slate-900/90 border border-slate-800 text-[10px] font-mono text-cyan-300 flex items-center space-x-1.5">
                      <ShieldCheck className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                      <span>GDPR Compliance: Gaussian face blur applied at edge buffer</span>
                    </div>
                  </div>
                </div>

                {/* 2D Floor Plan Mini-Map via Homography */}
                <div className="space-y-2">
                  <span className="text-xs font-mono text-slate-400 uppercase font-semibold">
                    Floor Plan Mini-Map (Homography Projection)
                  </span>
                  <div className="relative aspect-video bg-slate-950 rounded-lg border border-slate-800 p-3 overflow-hidden">
                    {/* Mini plant floor plan layout */}
                    <div
                      className="absolute inset-0 opacity-20"
                      style={{
                        backgroundImage: `radial-gradient(circle at 1px 1px, #38bdf8 1px, transparent 0)`,
                        backgroundSize: "16px 16px",
                      }}
                    />

                    {/* Industrial Plant Hall Outline */}
                    <div className="absolute inset-3 border border-slate-800 rounded flex flex-col justify-between p-2 pointer-events-none">
                      <div className="flex justify-between text-[9px] font-mono text-slate-500">
                        <span>STAMPING HALL A</span>
                        <span>LOGISTICS CORRIDOR</span>
                      </div>
                      <div className="flex justify-between text-[9px] font-mono text-slate-500">
                        <span>MODULE ASSEMBLY</span>
                        <span>NORTH PERIMETER</span>
                      </div>
                    </div>

                    {/* Projected Incident Location Pin */}
                    <div
                      className="absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center"
                      style={{
                        left: `${(selectedEvent.floor_coords.x / 30) * 100}%`,
                        top: `${(selectedEvent.floor_coords.y / 20) * 100}%`,
                      }}
                    >
                      <div className="w-5 h-5 rounded-full bg-rose-500/30 border-2 border-rose-500 flex items-center justify-center animate-ping" />
                      <div className="w-2.5 h-2.5 rounded-full bg-rose-500 absolute top-1.5" />
                      <span className="mt-2 text-[9px] font-mono px-1.5 py-0.2 rounded bg-rose-950 border border-rose-700 text-rose-300 font-bold whitespace-nowrap shadow-lg">
                        X: {selectedEvent.floor_coords.x}m, Y: {selectedEvent.floor_coords.y}m
                      </span>
                    </div>

                    {/* Calibration Info */}
                    <div className="absolute bottom-2 right-2 text-[9px] font-mono text-slate-500">
                      Homography Matrix 3x3 • Reprojection Error &lt; 0.5px
                    </div>
                  </div>
                </div>
              </div>

              {/* Event Analytical Metrics */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                <span className="text-xs font-mono text-cyan-400 uppercase font-bold">
                  Deterministic Rule &amp; Incident Telemetry
                </span>
                <p className="text-xs text-slate-200">{selectedEvent.details}</p>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono pt-2 border-t border-slate-800/80">
                  <div>
                    <span className="text-slate-500 text-[10px] block">Rule ID</span>
                    <span className="text-slate-300">{selectedEvent.rule_id}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[10px] block">Violation Duration</span>
                    <span className="text-slate-300">{selectedEvent.duration_sec}s</span>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[10px] block">Confidence</span>
                    <span className="text-emerald-400 font-semibold">
                      {(selectedEvent.confidence * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[10px] block">Worker Re-ID</span>
                    <span className="text-cyan-400 font-semibold">
                      {selectedEvent.global_person_id || "Unassigned"}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ZOOMED STREAM PREVIEW MODAL */}
      {zoomedCamera && (
        <div className="fixed inset-0 z-50 bg-black/90 backdrop-blur-md flex items-center justify-center p-6">
          <div className="w-full max-w-5xl bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
            <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-100">{zoomedCamera.name}</h3>
                <span className="text-xs font-mono text-slate-400">{zoomedCamera.rtsp_url}</span>
              </div>
              <button
                onClick={() => setZoomedCamera(null)}
                className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="aspect-video bg-black flex items-center justify-center relative">
              <span className="text-xs font-mono text-slate-500">
                Live Stream Preview • {zoomedCamera.resolution} • Drop-Oldest Bounded Queue &le; 4 Frames
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
