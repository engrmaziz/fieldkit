export interface Ticket {
  ticket_id: string;
  customer_name: string;
  customer_id: string;
  plant: string;
  order_id: string;
  language: "de" | "en";
  queue: "returns_rma" | "order_delivery" | "quality_defect" | "technical_spec" | "billing_inquiry" | "general_inquiry";
  priority: "critical" | "high" | "medium" | "low";
  status: "awaiting_approval" | "in_progress" | "completed" | "escalated" | "rejected";
  confidence: number;
  raw_text: string;
  masked_text: string;
  pii_detected: string[];
  created_at: string;
  order_total_eur?: number;
  legal_hold?: boolean;
  action_plan?: ActionPlan;
  violations?: PolicyViolation[];
  audit_events?: AuditEventItem[];
}

export interface ActionCall {
  tool: "create_rma" | "issue_credit" | "lookup_order" | "get_shipments" | "search_kb" | "escalate" | "send_reply";
  args: Record<string, any>;
  rationale: string;
  side_effect: boolean;
  status?: "pending" | "approved" | "executed" | "rejected";
}

export interface ActionPlan {
  ticket_id: string;
  actions: ActionCall[];
  reply_draft: string;
  requires_approval: boolean;
}

export interface PolicyViolation {
  rule: string;
  tool: string;
  message: string;
  severity: "error" | "warning";
}

export interface AuditEventItem {
  sequence: number;
  event_type: string;
  state_name: string;
  timestamp: string;
  prev_hash: string;
  event_hash: string;
  payload: Record<string, any>;
}

export interface DefectCluster {
  cluster_id: number;
  topic_title: string;
  top_terms: string[];
  part_numbers: string[];
  current_count: number;
  baseline_count: number;
  growth_rate: number;
  severity: "critical" | "warning" | "normal";
  tracehub_alert_id?: string;
  sample_ticket_ids: string[];
}
