// Type definitions and mock data for InspectAI Operator Console (Hamburg Plant DE-HAM)

export type InspectionDisposition = "PASS" | "REVIEW" | "REJECT";

export type DefectClass =
  | "good"
  | "crazing"
  | "inclusion"
  | "patches"
  | "pitted_surface"
  | "rolled_in_scale"
  | "scratches";

export interface PolygonPoint {
  x: number;
  y: number;
}

export interface InspectionRecordUI {
  id: string;
  productId: "metal_nut" | "steel_sheet" | "screw" | "grid" | "tile";
  productName: string;
  disposition: InspectionDisposition;
  anomalyScore: number;
  thresholdPass: number;
  thresholdReject: number;
  predictedClass: DefectClass;
  calibratedConfidence: number;
  classProbabilities: Record<DefectClass, number>;
  costExpected: number;
  isAudit: boolean;
  reviewed: boolean;
  operatorNotes?: string;
  reviewedBy?: string;
  reviewedAt?: string;
  timestamp: string;
  latencyMs: number;
  defectPolygons?: PolygonPoint[][];
  surfaceSvgType: "nut" | "sheet" | "screw" | "grid" | "tile";
  hasDefectVisual: boolean;
  defectLocation?: { cx: number; cy: number; r: number; label: string };
}

export interface ReviewQueueItemUI extends InspectionRecordUI {
  priority: "HIGH" | "MEDIUM" | "LOW";
  routingReason: "GREY_ZONE_ANOMALY" | "LOW_CLASSIFIER_CONFIDENCE" | "SEEDED_2PCT_AUDIT";
}

export interface DriftMetricUI {
  productId: string;
  productName: string;
  psiScore: number;
  status: "STABLE" | "WATCH" | "CRITICAL_DRIFT";
  sampleCount: number;
  lastUpdated: string;
  meanScore: number;
  baselineMean: number;
}

export interface ShadowModelReportUI {
  prodModelId: string;
  candModelId: string;
  sampleCount: number;
  decisionAgreementRate: number;
  classConcordanceRate: number;
  meanLatencyDeltaMs: number;
  status: "READY_FOR_PROMOTION" | "COLLECTING_TELEMETRY" | "REGRESSION_DETECTED";
  prodLatencyP95: number;
  candLatencyP95: number;
  lastEvaluatedAt: string;
}

export const MOCK_DRIFT_METRICS: DriftMetricUI[] = [
  {
    productId: "metal_nut",
    productName: "M12 Hex Flange Nut (DIN 6923)",
    psiScore: 0.0412,
    status: "STABLE",
    sampleCount: 420,
    lastUpdated: "2 mins ago",
    meanScore: 0.182,
    baselineMean: 0.179,
  },
  {
    productId: "steel_sheet",
    productName: "Cold-Rolled Coil (DC04 Steel)",
    psiScore: 0.0727,
    status: "STABLE",
    sampleCount: 380,
    lastUpdated: "Just now",
    meanScore: 0.245,
    baselineMean: 0.241,
  },
  {
    productId: "screw",
    productName: "Socket Head Cap Screw (ISO 4762)",
    psiScore: 0.1340,
    status: "WATCH",
    sampleCount: 290,
    lastUpdated: "5 mins ago",
    meanScore: 0.312,
    baselineMean: 0.265,
  },
  {
    productId: "grid",
    productName: "Galvanized Ventilation Mesh",
    psiScore: 0.0521,
    status: "STABLE",
    sampleCount: 310,
    lastUpdated: "12 mins ago",
    meanScore: 0.198,
    baselineMean: 0.195,
  },
  {
    productId: "tile",
    productName: "Refractory Furnace Lining Tile",
    psiScore: 0.2280,
    status: "CRITICAL_DRIFT",
    sampleCount: 195,
    lastUpdated: "1 min ago",
    meanScore: 0.442,
    baselineMean: 0.220,
  },
];

export const MOCK_SHADOW_REPORT: ShadowModelReportUI = {
  prodModelId: "inspect_v1.0.0_fp32",
  candModelId: "inspect_v2.0.0_candidate",
  sampleCount: 50,
  decisionAgreementRate: 1.0, // 100% agreement
  classConcordanceRate: 0.98,
  meanLatencyDeltaMs: -1.2, // Candidate is 1.2ms faster
  prodLatencyP95: 12.8,
  candLatencyP95: 11.6,
  status: "READY_FOR_PROMOTION",
  lastEvaluatedAt: "2026-10-21 21:05 UTC",
};

export const MOCK_INSPECTION_RECORDS: InspectionRecordUI[] = [
  {
    id: "insp-deham-9401",
    productId: "metal_nut",
    productName: "M12 Hex Flange Nut (DIN 6923)",
    disposition: "PASS",
    anomalyScore: 0.142,
    thresholdPass: 0.385,
    thresholdReject: 0.650,
    predictedClass: "good",
    calibratedConfidence: 0.984,
    classProbabilities: {
      good: 0.984,
      crazing: 0.003,
      inclusion: 0.002,
      patches: 0.004,
      pitted_surface: 0.002,
      rolled_in_scale: 0.003,
      scratches: 0.002,
    },
    costExpected: 0.02,
    isAudit: false,
    reviewed: false,
    timestamp: "21:18:42",
    latencyMs: 8.4,
    surfaceSvgType: "nut",
    hasDefectVisual: false,
  },
  {
    id: "insp-deham-9402",
    productId: "steel_sheet",
    productName: "Cold-Rolled Coil (DC04 Steel)",
    disposition: "REJECT",
    anomalyScore: 0.892,
    thresholdPass: 0.350,
    thresholdReject: 0.620,
    predictedClass: "scratches",
    calibratedConfidence: 0.962,
    classProbabilities: {
      good: 0.008,
      crazing: 0.004,
      inclusion: 0.012,
      patches: 0.006,
      pitted_surface: 0.003,
      rolled_in_scale: 0.005,
      scratches: 0.962,
    },
    costExpected: 1.0,
    isAudit: false,
    reviewed: false,
    timestamp: "21:18:40",
    latencyMs: 9.1,
    surfaceSvgType: "sheet",
    hasDefectVisual: true,
    defectLocation: { cx: 140, cy: 95, r: 35, label: "Deep Longitudinal Scratch" },
  },
  {
    id: "insp-deham-9403",
    productId: "steel_sheet",
    productName: "Cold-Rolled Coil (DC04 Steel)",
    disposition: "REVIEW",
    anomalyScore: 0.445,
    thresholdPass: 0.350,
    thresholdReject: 0.620,
    predictedClass: "inclusion",
    calibratedConfidence: 0.724,
    classProbabilities: {
      good: 0.185,
      crazing: 0.012,
      inclusion: 0.724,
      patches: 0.045,
      pitted_surface: 0.014,
      rolled_in_scale: 0.012,
      scratches: 0.008,
    },
    costExpected: 0.30,
    isAudit: false,
    reviewed: false,
    timestamp: "21:18:35",
    latencyMs: 10.2,
    surfaceSvgType: "sheet",
    hasDefectVisual: true,
    defectLocation: { cx: 88, cy: 150, r: 24, label: "Surface Smelt Inclusion" },
  },
  {
    id: "insp-deham-9404",
    productId: "screw",
    productName: "Socket Head Cap Screw (ISO 4762)",
    disposition: "PASS",
    anomalyScore: 0.205,
    thresholdPass: 0.410,
    thresholdReject: 0.680,
    predictedClass: "good",
    calibratedConfidence: 0.971,
    classProbabilities: {
      good: 0.971,
      crazing: 0.004,
      inclusion: 0.005,
      patches: 0.006,
      pitted_surface: 0.004,
      rolled_in_scale: 0.005,
      scratches: 0.005,
    },
    costExpected: 0.03,
    isAudit: true, // Seeded 2% random audit
    reviewed: false,
    timestamp: "21:18:31",
    latencyMs: 8.8,
    surfaceSvgType: "screw",
    hasDefectVisual: false,
  },
  {
    id: "insp-deham-9405",
    productId: "grid",
    productName: "Galvanized Ventilation Mesh",
    disposition: "PASS",
    anomalyScore: 0.118,
    thresholdPass: 0.370,
    thresholdReject: 0.640,
    predictedClass: "good",
    calibratedConfidence: 0.992,
    classProbabilities: {
      good: 0.992,
      crazing: 0.001,
      inclusion: 0.001,
      patches: 0.002,
      pitted_surface: 0.001,
      rolled_in_scale: 0.002,
      scratches: 0.001,
    },
    costExpected: 0.01,
    isAudit: false,
    reviewed: false,
    timestamp: "21:18:27",
    latencyMs: 7.9,
    surfaceSvgType: "grid",
    hasDefectVisual: false,
  },
  {
    id: "insp-deham-9406",
    productId: "tile",
    productName: "Refractory Furnace Lining Tile",
    disposition: "REJECT",
    anomalyScore: 0.915,
    thresholdPass: 0.360,
    thresholdReject: 0.630,
    predictedClass: "crazing",
    calibratedConfidence: 0.945,
    classProbabilities: {
      good: 0.005,
      crazing: 0.945,
      inclusion: 0.015,
      patches: 0.015,
      pitted_surface: 0.008,
      rolled_in_scale: 0.006,
      scratches: 0.006,
    },
    costExpected: 1.0,
    isAudit: false,
    reviewed: true,
    operatorNotes: "Thermal crazing fracture confirmed on bottom flange",
    reviewedBy: "M. Yilmaz (DE-HAM)",
    reviewedAt: "21:18:05",
    timestamp: "21:18:01",
    latencyMs: 11.4,
    surfaceSvgType: "tile",
    hasDefectVisual: true,
    defectLocation: { cx: 160, cy: 120, r: 42, label: "Thermal Crazing Fracture" },
  },
  {
    id: "insp-deham-9407",
    productId: "metal_nut",
    productName: "M12 Hex Flange Nut (DIN 6923)",
    disposition: "REVIEW",
    anomalyScore: 0.512,
    thresholdPass: 0.385,
    thresholdReject: 0.650,
    predictedClass: "pitted_surface",
    calibratedConfidence: 0.685,
    classProbabilities: {
      good: 0.215,
      crazing: 0.008,
      inclusion: 0.012,
      patches: 0.035,
      pitted_surface: 0.685,
      rolled_in_scale: 0.025,
      scratches: 0.020,
    },
    costExpected: 0.30,
    isAudit: false,
    reviewed: false,
    timestamp: "21:17:54",
    latencyMs: 8.9,
    surfaceSvgType: "nut",
    hasDefectVisual: true,
    defectLocation: { cx: 128, cy: 128, r: 28, label: "Flange Pitting Corrosion" },
  },
  {
    id: "insp-deham-9408",
    productId: "steel_sheet",
    productName: "Cold-Rolled Coil (DC04 Steel)",
    disposition: "PASS",
    anomalyScore: 0.095,
    thresholdPass: 0.350,
    thresholdReject: 0.620,
    predictedClass: "good",
    calibratedConfidence: 0.995,
    classProbabilities: {
      good: 0.995,
      crazing: 0.001,
      inclusion: 0.001,
      patches: 0.001,
      pitted_surface: 0.001,
      rolled_in_scale: 0.001,
      scratches: 0.000,
    },
    costExpected: 0.01,
    isAudit: false,
    reviewed: false,
    timestamp: "21:17:48",
    latencyMs: 8.1,
    surfaceSvgType: "sheet",
    hasDefectVisual: false,
  },
];

export const MOCK_REVIEW_QUEUE: ReviewQueueItemUI[] = [
  {
    ...MOCK_INSPECTION_RECORDS[2], // insp-deham-9403
    priority: "HIGH",
    routingReason: "GREY_ZONE_ANOMALY",
  },
  {
    ...MOCK_INSPECTION_RECORDS[3], // insp-deham-9404 (2% seeded random audit)
    priority: "LOW",
    routingReason: "SEEDED_2PCT_AUDIT",
  },
  {
    ...MOCK_INSPECTION_RECORDS[6], // insp-deham-9407
    priority: "MEDIUM",
    routingReason: "LOW_CLASSIFIER_CONFIDENCE",
  },
];
