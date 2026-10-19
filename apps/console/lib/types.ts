export type OntologyObjectType =
  | "Supplier"
  | "Part"
  | "Plant"
  | "PurchaseOrder"
  | "Shipment"
  | "QualityIncident"
  | "Certificate";

export interface UserPrincipal {
  username: string;
  name: string;
  roles: string[];
  plant: string | null;
  email: string;
}

export interface PropertyProvenance {
  value: any;
  source_id: string;
  source_row_ref: string;
  run_id: string;
  rule: string;
  recorded_at: string;
}

export interface ObjectDetailResponse {
  object: Record<string, any>;
  provenance: Record<string, PropertyProvenance>;
}

export interface KeysetListResponse {
  type: string;
  count: number;
  items: Record<string, any>[];
  next_cursor: string | null;
}

export interface NeighborItem {
  link: string;
  target_type: string;
  depth: number;
  object: Record<string, any>;
}

export interface NeighborsResponse {
  object_id: string;
  object_type: string;
  depth: number;
  count: number;
  neighbors: NeighborItem[];
}

export interface DriftEvent {
  event_id: string;
  run_id: string;
  source: string;
  event_type: string;
  severity: "BLOCK" | "WARN";
  column_name: string;
  details: Record<string, any>;
  suggestion?: {
    mapping?: { old: string; new: string };
    confidence?: number;
    reason?: string;
  } | null;
  status: "open" | "suggested" | "approved" | "rejected";
  created_at: string;
}

export interface ReviewQueueItem {
  pair_id: string;
  source_a: string;
  record_a: Record<string, any>;
  source_b: string;
  record_b: Record<string, any>;
  match_probability: number;
  llm_confidence?: number | null;
  llm_evidence?: string[];
  status: "PENDING" | "RESOLVED";
  decision?: "match" | "non_match" | null;
  decided_by?: string | null;
  decided_at?: string | null;
}

export interface LineageTransform {
  id: string;
  run_id: string;
  input_dataset: string;
  transform: string;
  output_dataset: string;
  started_at: string;
  ended_at: string;
  facets?: Record<string, any>;
}

export interface PropertyLineageHistoryItem {
  id: string;
  value: any;
  source_id: string;
  source_row_ref: string;
  rule_applied: string;
  run_id: string;
  recorded_at: string;
}

export interface PropertyLineageResponse {
  object_type: string;
  object_id: string;
  property_name: string;
  current_value: string | null;
  provenance_count: number;
  history: PropertyLineageHistoryItem[];
  transforms: LineageTransform[];
}
