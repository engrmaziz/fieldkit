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

// ==========================================
// P2 Assistant Console Types
// ==========================================

export interface ChunkCitation {
  citation_index: number;
  chunk_id: string;
  title: string;
  heading_path: string[];
  content: string;
  allowed_roles: string[];
  allowed_plants?: string[] | null;
}

export interface SentenceVerification {
  sentence_index: number;
  text: string;
  citations: number[];
  valid_citations: number[];
  overlap_score: number;
  numeric_match: boolean;
  is_supported: boolean;
  flag?: string | null;
}

export interface VerificationResult {
  is_supported: boolean;
  supported_ratio: number;
  unsupported_count: number;
  sentence_verifications?: SentenceVerification[];
}

export interface UnifiedAssistantResponse {
  query: string;
  rewritten_query: string;
  route: "rag" | "sql" | "both" | string;
  confidence: number;
  answer: string;
  citations: ChunkCitation[];
  sql?: string | null;
  tables_used: string[];
  columns: string[];
  rows: Record<string, any>[];
  row_count: number;
  verification?: VerificationResult | null;
  cached: boolean;
  session_id?: string | null;
  trace_id?: string | null;
}

export interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  content: string;
  timestamp: string;
  route?: "rag" | "sql" | "both" | string;
  confidence?: number;
  rewritten_query?: string;
  citations?: ChunkCitation[];
  sql?: string | null;
  tables_used?: string[];
  columns?: string[];
  rows?: Record<string, any>[];
  row_count?: number;
  verification?: VerificationResult | null;
  cached?: boolean;
  trace_id?: string | null;
  isStreaming?: boolean;
  feedback?: "up" | "down" | null;
}

export interface DocAIDocument {
  document_id: string;
  filename: string;
  mime_type: string;
  file_size_bytes: number;
  document_type: "delivery_note" | "contract" | "other";
  status: "uploaded" | "queued" | "processing" | "auto_accepted" | "review_required" | "completed" | "failed";
  plant?: string;
  created_at: string;
  confidence?: number;
  page_count: number;
}

export interface DeliveryNoteExtraction {
  supplier_name: string;
  supplier_address: string;
  delivery_note_no: string;
  po_number: string;
  delivery_date: string;
  total_qty: number;
  line_items: Array<{
    part_no: string;
    description: string;
    qty: number;
    unit: string;
    unit_price?: number;
  }>;
  validators: Record<string, { status: "PASS" | "FAIL" | "WARN"; message: string }>;
  decision: "AUTO_ACCEPTED" | "VLM_FALLBACK" | "REVIEW_QUEUE";
  confidence: number;
}

export interface ContractExtraction {
  contract_id: string;
  title: string;
  parties: string[];
  governing_law?: string;
  clauses: Array<{
    clause_id: string;
    section_number: string;
    title: string;
    text: string;
    page_idx: number;
    char_start: number;
    char_end: number;
    bbox: number[];
    categories: string[];
    category_scores: Record<string, number>;
  }>;
  playbook_findings: Array<{
    rule_id: string;
    rule_name: string;
    status: "PASS" | "FAIL" | "WARN";
    severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
    clause_id?: string;
    message: string;
    fallback_recommendation?: string;
  }>;
}

export interface ContractDiffItem {
  clause_v1_id?: string;
  clause_v2_id?: string;
  section_v1?: string;
  section_v2?: string;
  status: "UNCHANGED" | "MODIFIED" | "ADDED" | "DELETED";
  similarity_score: number;
  v1_text: string;
  v2_text: string;
  text_diff: string;
  is_material: boolean;
  material_reasons: string[];
  severity: string;
}

