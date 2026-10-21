export interface CameraInfo {
  camera_id: string;
  name: string;
  location: string;
  plant: string;
  status: "HEALTHY" | "DEGRADED" | "CRITICAL";
  fps: number;
  target_fps: number;
  blur_score: number;
  view_shift_pct: number;
  frozen: boolean;
  black: boolean;
  uptime_pct: number;
  active_tracks: {
    persons: number;
    forklifts: number;
    ppe_violations: number;
  };
  rtsp_url: string;
  resolution: string;
}

export interface VisionZone {
  id: string;
  name: string;
  type: "danger_zone" | "forklift_lane" | "pedestrian_walkway" | "ppe_mandatory_zone" | "tripwire";
  polygon: [number, number][];
  camera_id: string;
  color: string;
}

export interface VisionEventUI {
  event_id: string;
  camera_id: string;
  camera_name: string;
  plant_id: string;
  zone_id: string;
  rule_id: string;
  rule_type: "forklift_pedestrian_proximity" | "zone_ppe_missing" | "line_cross" | "dwell";
  severity: "CRITICAL" | "WARNING" | "INFO";
  track_id: number;
  global_person_id?: string;
  timestamp: string;
  duration_sec: number;
  confidence: number;
  details: string;
  clip_uri: string;
  floor_coords: { x: number; y: number }; // Plant floor map meters
  bounding_box?: [number, number, number, number];
  metrics?: {
    distance_m?: number;
    forklift_speed_mps?: number;
    dwell_duration_s?: number;
    ppe_compliance_pct?: number;
  };
}

export interface PersonJourneyStep {
  camera_id: string;
  camera_name: string;
  location: string;
  entered_at: string;
  exited_at: string;
  duration_sec: number;
  similarity_score: number;
  thumbnail_desc: string;
  associated_events: string[];
}

export interface PersonJourney {
  person_id: string;
  alias: string;
  first_seen: string;
  last_seen: string;
  total_transit_min: number;
  cameras_visited: string[];
  steps: PersonJourneyStep[];
}

export const MOCK_CAMERAS: CameraInfo[] = [
  {
    camera_id: "cam1_press",
    name: "Press Bed Cam 1",
    location: "Stamping Hall A - Press Bed",
    plant: "DE-HAM",
    status: "HEALTHY",
    fps: 5.0,
    target_fps: 5.0,
    blur_score: 142.5,
    view_shift_pct: 3.2,
    frozen: false,
    black: false,
    uptime_pct: 99.98,
    active_tracks: {
      persons: 3,
      forklifts: 1,
      ppe_violations: 1,
    },
    rtsp_url: "rtsp://edge-gateway.ham.halden.internal:8554/cam1_press",
    resolution: "1920x1080 @ 5fps",
  },
  {
    camera_id: "cam2_logistics",
    name: "Logistics Corridor Cam 2",
    location: "Forklift Transit Corridor East",
    plant: "DE-HAM",
    status: "HEALTHY",
    fps: 5.0,
    target_fps: 5.0,
    blur_score: 168.2,
    view_shift_pct: 1.8,
    frozen: false,
    black: false,
    uptime_pct: 100.0,
    active_tracks: {
      persons: 2,
      forklifts: 2,
      ppe_violations: 0,
    },
    rtsp_url: "rtsp://edge-gateway.ham.halden.internal:8554/cam2_logistics",
    resolution: "1920x1080 @ 5fps",
  },
  {
    camera_id: "cam3_assembly",
    name: "Assembly Bay 4 Cam 3",
    location: "Module Assembly Workstation Cluster",
    plant: "DE-HAM",
    status: "DEGRADED",
    fps: 4.8,
    target_fps: 5.0,
    blur_score: 74.6, // Below 80 threshold -> lens smear
    view_shift_pct: 7.4,
    frozen: false,
    black: false,
    uptime_pct: 98.42,
    active_tracks: {
      persons: 4,
      forklifts: 0,
      ppe_violations: 1,
    },
    rtsp_url: "rtsp://edge-gateway.ham.halden.internal:8554/cam3_assembly",
    resolution: "1920x1080 @ 5fps",
  },
  {
    camera_id: "cam4_perimeter",
    name: "Perimeter Gate Cam 4",
    location: "North Facility Security Gate & Staging",
    plant: "DE-HAM",
    status: "HEALTHY",
    fps: 5.0,
    target_fps: 5.0,
    blur_score: 185.1,
    view_shift_pct: 0.9,
    frozen: false,
    black: false,
    uptime_pct: 99.95,
    active_tracks: {
      persons: 1,
      forklifts: 0,
      ppe_violations: 0,
    },
    rtsp_url: "rtsp://edge-gateway.ham.halden.internal:8554/cam4_perimeter",
    resolution: "1920x1080 @ 5fps",
  },
];

export const MOCK_ZONES: VisionZone[] = [
  {
    id: "zone_press_danger",
    name: "Hydraulic Press Danger Envelope",
    type: "danger_zone",
    camera_id: "cam1_press",
    polygon: [
      [200, 320],
      [680, 320],
      [740, 640],
      [140, 640],
    ],
    color: "#ef4444",
  },
  {
    id: "zone_press_forklift_lane",
    name: "Stamping Supply Transit Lane",
    type: "forklift_lane",
    camera_id: "cam1_press",
    polygon: [
      [50, 160],
      [780, 160],
      [780, 310],
      [50, 310],
    ],
    color: "#f59e0b",
  },
  {
    id: "zone_corridor_speed_lane",
    name: "Heavy Forklift Expressway",
    type: "forklift_lane",
    camera_id: "cam2_logistics",
    polygon: [
      [160, 120],
      [540, 120],
      [580, 680],
      [110, 680],
    ],
    color: "#f59e0b",
  },
  {
    id: "zone_pedestrian_walkway",
    name: "Designated Safe Pedestrian Crossway",
    type: "pedestrian_walkway",
    camera_id: "cam2_logistics",
    polygon: [
      [100, 380],
      [600, 380],
      [600, 480],
      [100, 480],
    ],
    color: "#10b981",
  },
  {
    id: "zone_assembly_ppe_zone",
    name: "High-Bay PPE Mandatory Enclosure",
    type: "ppe_mandatory_zone",
    camera_id: "cam3_assembly",
    polygon: [
      [90, 90],
      [720, 90],
      [720, 680],
      [90, 680],
    ],
    color: "#06b6d4",
  },
  {
    id: "zone_perimeter_tripwire",
    name: "Facility Perimeter Anti-Trespass Line",
    type: "tripwire",
    camera_id: "cam4_perimeter",
    polygon: [
      [40, 420],
      [760, 420],
      [760, 460],
      [40, 460],
    ],
    color: "#a855f7",
  },
];

export const MOCK_EVENTS: VisionEventUI[] = [
  {
    event_id: "evt_20261021_001",
    camera_id: "cam2_logistics",
    camera_name: "Logistics Corridor Cam 2",
    plant_id: "DE-HAM",
    zone_id: "zone_corridor_speed_lane",
    rule_id: "rule_forklift_prox",
    rule_type: "forklift_pedestrian_proximity",
    severity: "CRITICAL",
    track_id: 104,
    global_person_id: "person_0001",
    timestamp: "2026-10-21T18:42:10Z",
    duration_sec: 1.8,
    confidence: 0.965,
    details: "Forklift #3 approached Worker (person_0001) within 1.38m at 1.4 m/s in main corridor",
    clip_uri: "/vision-clips/evt_20261021_001.mp4",
    floor_coords: { x: 14.2, y: 8.5 },
    metrics: {
      distance_m: 1.38,
      forklift_speed_mps: 1.4,
    },
  },
  {
    event_id: "evt_20261021_002",
    camera_id: "cam1_press",
    camera_name: "Press Bed Cam 1",
    plant_id: "DE-HAM",
    zone_id: "zone_press_danger",
    rule_id: "rule_press_hard_hat",
    rule_type: "zone_ppe_missing",
    severity: "WARNING",
    track_id: 88,
    global_person_id: "person_0003",
    timestamp: "2026-10-21T18:28:44Z",
    duration_sec: 2.6,
    confidence: 0.942,
    details: "Worker operating near press tooling without required safety helmet (>70% over 2.0s)",
    clip_uri: "/vision-clips/evt_20261021_002.mp4",
    floor_coords: { x: 4.8, y: 12.1 },
    metrics: {
      ppe_compliance_pct: 12.5,
    },
  },
  {
    event_id: "evt_20261021_003",
    camera_id: "cam4_perimeter",
    camera_name: "Perimeter Gate Cam 4",
    plant_id: "DE-HAM",
    zone_id: "zone_perimeter_tripwire",
    rule_id: "rule_perimeter_crossing",
    rule_type: "line_cross",
    severity: "WARNING",
    track_id: 202,
    global_person_id: "person_0002",
    timestamp: "2026-10-21T17:55:02Z",
    duration_sec: 0.8,
    confidence: 0.978,
    details: "Pedestrian crossed facility perimeter tripwire outside normal shift clearance hours",
    clip_uri: "/vision-clips/evt_20261021_003.mp4",
    floor_coords: { x: 28.6, y: 3.4 },
  },
  {
    event_id: "evt_20261021_004",
    camera_id: "cam3_assembly",
    camera_name: "Assembly Bay 4 Cam 3",
    plant_id: "DE-HAM",
    zone_id: "zone_assembly_ppe_zone",
    rule_id: "rule_assembly_dwell",
    rule_type: "dwell",
    severity: "INFO",
    track_id: 119,
    global_person_id: "person_0001",
    timestamp: "2026-10-21T17:15:30Z",
    duration_sec: 320.0,
    confidence: 0.912,
    details: "Worker loitering in staging corridor exceeded max dwell limit (320s > 180s threshold)",
    clip_uri: "/vision-clips/evt_20261021_004.mp4",
    floor_coords: { x: 19.4, y: 16.8 },
    metrics: {
      dwell_duration_s: 320,
    },
  },
  {
    event_id: "evt_20261021_005",
    camera_id: "cam1_press",
    camera_name: "Press Bed Cam 1",
    plant_id: "DE-HAM",
    zone_id: "zone_press_forklift_lane",
    rule_id: "rule_forklift_prox",
    rule_type: "forklift_pedestrian_proximity",
    severity: "CRITICAL",
    track_id: 74,
    global_person_id: "person_0004",
    timestamp: "2026-10-21T16:30:18Z",
    duration_sec: 1.6,
    confidence: 0.958,
    details: "Forklift transit lane proximity breach (1.62m separation at 0.9 m/s)",
    clip_uri: "/vision-clips/evt_20261021_005.mp4",
    floor_coords: { x: 6.2, y: 9.8 },
    metrics: {
      distance_m: 1.62,
      forklift_speed_mps: 0.9,
    },
  },
  {
    event_id: "evt_20261021_006",
    camera_id: "cam3_assembly",
    camera_name: "Assembly Bay 4 Cam 3",
    plant_id: "DE-HAM",
    zone_id: "zone_assembly_ppe_zone",
    rule_id: "rule_ppe_mandatory",
    rule_type: "zone_ppe_missing",
    severity: "WARNING",
    track_id: 95,
    global_person_id: "person_0005",
    timestamp: "2026-10-21T15:10:45Z",
    duration_sec: 2.2,
    confidence: 0.934,
    details: "Subcontractor technician entered Bay 4 assembly zone without high-vis safety vest",
    clip_uri: "/vision-clips/evt_20261021_006.mp4",
    floor_coords: { x: 21.0, y: 15.2 },
    metrics: {
      ppe_compliance_pct: 20.0,
    },
  },
];

export const MOCK_PERSON_JOURNEY: PersonJourney = {
  person_id: "person_0001",
  alias: "Technician Track #0001 (DE-HAM Shift A)",
  first_seen: "2026-10-21T08:14:22Z",
  last_seen: "2026-10-21T18:42:10Z",
  total_transit_min: 628,
  cameras_visited: ["cam4_perimeter", "cam2_logistics", "cam1_press", "cam3_assembly"],
  steps: [
    {
      camera_id: "cam4_perimeter",
      camera_name: "Perimeter Gate Cam 4",
      location: "North Facility Security Gate & Turnstile",
      entered_at: "08:14:22",
      exited_at: "08:15:10",
      duration_sec: 48,
      similarity_score: 1.0,
      thumbnail_desc: "Gate badge check, high-vis jacket detected",
      associated_events: [],
    },
    {
      camera_id: "cam2_logistics",
      camera_name: "Logistics Corridor Cam 2",
      location: "Forklift Transit Corridor East",
      entered_at: "08:17:40",
      exited_at: "08:22:15",
      duration_sec: 275,
      similarity_score: 0.88,
      thumbnail_desc: "Walking along yellow walkway line, passing bay 2",
      associated_events: [],
    },
    {
      camera_id: "cam1_press",
      camera_name: "Press Bed Cam 1",
      location: "Stamping Hall A - Press Bed",
      entered_at: "08:24:10",
      exited_at: "08:48:30",
      duration_sec: 1460,
      similarity_score: 0.85,
      thumbnail_desc: "Inspecting press die tooling calibration",
      associated_events: [],
    },
    {
      camera_id: "cam3_assembly",
      camera_name: "Assembly Bay 4 Cam 3",
      location: "Module Assembly Workstation Cluster",
      entered_at: "08:52:00",
      exited_at: "09:35:10",
      duration_sec: 2590,
      similarity_score: 0.82,
      thumbnail_desc: "Assisting module wiring cell, staging dwell alert",
      associated_events: ["evt_20261021_004"],
    },
    {
      camera_id: "cam2_logistics",
      camera_name: "Logistics Corridor Cam 2",
      location: "Forklift Transit Corridor East",
      entered_at: "18:39:15",
      exited_at: "18:43:00",
      duration_sec: 225,
      similarity_score: 0.86,
      thumbnail_desc: "Returning toward exit, proximity incident with Forklift #3",
      associated_events: ["evt_20261021_001"],
    },
  ],
};
