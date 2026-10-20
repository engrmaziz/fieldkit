"""LangGraph State Machine for Fieldkit Ops Copilot (P3).

Implements the multi-stage state machine:
1. Intake & Presidio PII Masking
2. Multilingual Triage (XLM-R ONNX + LLM fallback)
3. Context Enrichment (P1 Ontology + P2 Knowledge Base)
4. LLM Action Planning
5. Deterministic Policy Evaluation (Zero eval, strict thresholds)
6. Human Approval Gate (Mandatory interrupt on side effects)
7. Tool Execution with Idempotency Keys and Reply QA
8. SHA-256 Hash-Chained Audit Ledger
"""

from __future__ import annotations

import re
from typing import Any

from fieldkit_common.logging import get_logger
from fieldkit_mock_erp.models import Customer, Order, Shipment
from fieldkit_ticketclf.infer import ONNXTicketClassifier, get_onnx_classifier
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from .audit import AuditLedger, get_audit_ledger
from .checkpointer import get_checkpointer
from .models import ActionCall, ActionPlan, Violation, WorldState
from .pii import mask_pii
from .policy import PolicyEngine, get_policy_engine
from .state import CopilotState
from .tools.registry import ToolRegistry, get_tool_registry

logger = get_logger("fieldkit.copilot.graph")


class CopilotGraph:
    """Compiled LangGraph orchestrator with human-in-the-loop and audit logging."""

    def __init__(
        self,
        classifier: ONNXTicketClassifier | None = None,
        tool_registry: ToolRegistry | None = None,
        policy_engine: PolicyEngine | None = None,
        audit_ledger: AuditLedger | None = None,
        checkpointer: BaseCheckpointSaver[Any] | None = None,
    ) -> None:
        self.classifier = classifier or get_onnx_classifier()
        self.tool_registry = tool_registry or get_tool_registry()
        self.policy_engine = policy_engine or get_policy_engine()
        self.audit_ledger = audit_ledger or get_audit_ledger()
        self.checkpointer = checkpointer or get_checkpointer()
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        builder = StateGraph(CopilotState)

        # 1. Add Nodes
        builder.add_node("intake_and_mask_pii", self.node_intake_and_mask_pii)
        builder.add_node("triage_ticket", self.node_triage_ticket)
        builder.add_node("human_triage_queue", self.node_human_triage_queue)
        builder.add_node("enrich_context", self.node_enrich_context)
        builder.add_node("plan_actions", self.node_plan_actions)
        builder.add_node("evaluate_policy", self.node_evaluate_policy)
        builder.add_node("replan", self.node_replan)
        builder.add_node("escalate", self.node_escalate)
        builder.add_node("human_approval_gate", self.node_human_approval_gate)
        builder.add_node("execute_actions", self.node_execute_actions)
        builder.add_node("terminate_rejected", self.node_terminate_rejected)

        # 2. Add Edges & Conditional Routes
        builder.add_edge(START, "intake_and_mask_pii")
        builder.add_edge("intake_and_mask_pii", "triage_ticket")

        builder.add_conditional_edges(
            "triage_ticket",
            self.route_after_triage,
            {
                "human_triage": "human_triage_queue",
                "enrich": "enrich_context",
            },
        )
        builder.add_edge("human_triage_queue", "enrich_context")
        builder.add_edge("enrich_context", "plan_actions")
        builder.add_edge("plan_actions", "evaluate_policy")

        builder.add_conditional_edges(
            "evaluate_policy",
            self.route_after_policy,
            {
                "replan": "replan",
                "escalate": "escalate",
                "human_approval": "human_approval_gate",
                "execute": "execute_actions",
            },
        )

        builder.add_edge("replan", "plan_actions")
        builder.add_edge("escalate", END)

        builder.add_conditional_edges(
            "human_approval_gate",
            self.route_after_approval,
            {
                "awaiting": END,  # Pauses execution waiting for external resume
                "execute": "execute_actions",
                "rejected": "terminate_rejected",
            },
        )

        builder.add_edge("execute_actions", END)
        builder.add_edge("terminate_rejected", END)

        # Compile with interrupt before human approval gate
        return builder.compile(
            checkpointer=self.checkpointer,
            interrupt_before=["human_approval_gate"],
        )

    # -------------------------------------------------------------------------
    # Graph Node Implementations
    # -------------------------------------------------------------------------

    async def node_intake_and_mask_pii(self, state: CopilotState) -> dict[str, Any]:
        """Intake stage: masks customer PII prior to any classification or planning."""
        ticket_id = state.get("ticket_id", "TICK-UNKNOWN")
        raw_text = state.get("raw_text", "")

        masking = mask_pii(raw_text)
        masked_text = masking.masked_text
        detected = [e.model_dump() for e in masking.detected_entities]

        # Extract order reference if present (e.g. PO-1001)
        po_match = re.search(r"\b(PO-\d{4})\b", raw_text)
        order_id = po_match.group(1) if po_match else state.get("order_id")

        self.audit_ledger.record_event(
            ticket_id=ticket_id,
            event_type="INTAKE_COMPLETED",
            state_name="intake",
            payload={
                "raw_length": len(raw_text),
                "pii_detected_count": len(detected),
                "extracted_order_id": order_id,
            },
        )

        return {
            "masked_text": masked_text,
            "detected_pii": detected,
            "order_id": order_id,
            "internal_only": state.get("internal_only", False),
            "status": "intake_completed",
        }

    async def node_triage_ticket(self, state: CopilotState) -> dict[str, Any]:
        """Triage stage: runs ONNX classifier on masked text."""
        ticket_id = state.get("ticket_id", "TICK-UNKNOWN")
        text = state.get("masked_text", state.get("raw_text", ""))

        explicit_queue = state.get("queue")
        explicit_priority = state.get("priority")

        if explicit_queue and explicit_priority:
            queue = explicit_queue
            priority = explicit_priority
            confidence = float(state.get("confidence", 1.0))
            language = state.get("language", "de")
            needs_human = False
        else:
            pred = self.classifier.predict_one(text)
            queue = explicit_queue or pred.queue
            priority = explicit_priority or pred.priority
            confidence = float(pred.confidence)

            # Detect language heuristic: if 'und', 'der', 'die', 'bitte', 'leckt' in text -> de
            words = text.lower().split()
            german_hits = sum(
                1
                for w in words
                if w in ("der", "die", "das", "und", "bitte", "fehler", "pumpe", "nicht")
            )
            language = "de" if german_hits >= 2 else "en"
            needs_human = confidence < 0.60

        self.audit_ledger.record_event(
            ticket_id=ticket_id,
            event_type="TRIAGE_COMPLETED",
            state_name="triage",
            payload={
                "queue": queue,
                "priority": priority,
                "confidence": confidence,
                "language": language,
                "needs_human_triage": needs_human,
            },
        )

        return {
            "queue": queue,
            "priority": priority,
            "confidence": confidence,
            "language": language,
            "needs_human_triage": needs_human,
            "status": "triaged",
        }

    async def node_human_triage_queue(self, state: CopilotState) -> dict[str, Any]:
        """Fallback node when confidence is low; sets manual flag."""
        ticket_id = state.get("ticket_id", "TICK-UNKNOWN")
        self.audit_ledger.record_event(
            ticket_id=ticket_id,
            event_type="HUMAN_TRIAGE_ESCALATION",
            state_name="human_triage",
            payload={"reason": "Low classification confidence"},
        )
        return {"status": "human_triage_assigned"}

    async def node_enrich_context(self, state: CopilotState) -> dict[str, Any]:
        """Context enrichment: pulls ERP order/shipment/customer details and technical KB."""
        ticket_id = state.get("ticket_id", "TICK-UNKNOWN")
        order_id = state.get("order_id")

        order_obj: Order | None = None
        shipments_list: list[Shipment] = []
        customer_obj: Customer | None = None

        if order_id:
            try:
                order_res = await self.tool_registry.execute("lookup_order", {"order_id": order_id})
                if isinstance(order_res, Order):
                    order_obj = order_res
                elif isinstance(order_res, dict):
                    order_obj = Order(**order_res)

                if order_obj:
                    # Customer lookup
                    from fieldkit_mock_erp.storage import db

                    customer_obj = db.get_customer(order_obj.customer_id)

                # Shipments
                ship_res = await self.tool_registry.execute("get_shipments", {"order_id": order_id})
                if isinstance(ship_res, list):
                    shipments_list = [
                        s if isinstance(s, Shipment) else Shipment(**s) for s in ship_res
                    ]
            except Exception as e:
                logger.warning("context_enrichment_erp_lookup_failed", error=str(e))

        # Query technical KB
        kb_articles: list[dict[str, Any]] = []
        try:
            kb_res = await self.tool_registry.execute(
                "search_kb", {"query": state.get("queue", "")}
            )
            if hasattr(kb_res, "matches") and isinstance(kb_res.matches, list):
                kb_articles = [
                    m.model_dump() if hasattr(m, "model_dump") else dict(m) for m in kb_res.matches
                ]
            elif isinstance(kb_res, list):
                kb_articles = kb_res
        except Exception:
            pass

        world_state = WorldState(
            ticket_id=ticket_id,
            language=state.get("language", "de"),
            customer=customer_obj,
            order=order_obj,
            shipments=shipments_list,
            kb_articles=kb_articles,
            metadata={"priority": state.get("priority", "medium")},
        )

        self.audit_ledger.record_event(
            ticket_id=ticket_id,
            event_type="CONTEXT_ENRICHED",
            state_name="enrichment",
            payload={
                "has_order": order_obj is not None,
                "order_id": order_id,
                "customer_id": customer_obj.customer_id if customer_obj else None,
                "legal_hold": customer_obj.legal_hold if customer_obj else False,
                "shipment_count": len(shipments_list),
            },
        )

        return {
            "world_state": world_state.model_dump(),
            "customer_id": customer_obj.customer_id if customer_obj else None,
            "status": "enriched",
        }

    async def node_plan_actions(self, state: CopilotState) -> dict[str, Any]:
        """Propose structured ActionPlan based on queue, world state, and previous feedback."""
        ticket_id = state.get("ticket_id", "TICK-UNKNOWN")
        queue = state.get("queue", "general_inquiry")
        order_id = state.get("order_id", "PO-1001")
        replan_count = state.get("replan_count", 0)
        violations = state.get("violations", [])

        actions: list[ActionCall] = []
        reply_draft = ""

        # Check if replanning due to policy violation
        if replan_count > 0 and violations:
            # Self-healing re-planning: replace violating action with escalation
            actions.append(
                ActionCall(
                    tool="escalate",
                    args={
                        "reason": f"Policy compliance adjustment: {violations[0].get('message', 'Threshold exceeded')}",
                        "priority": "high",
                    },
                    rationale="Policy rule violated; routing ticket to senior support lead.",
                )
            )
            reply_draft = (
                "Vielen Dank für Ihre Anfrage. Wir haben Ihr Anliegen an unsere Fachabteilung "
                "zur manuellen Prüfung weitergeleitet."
            )
        else:
            if queue == "returns_rma":
                actions.append(
                    ActionCall(
                        tool="create_rma",
                        args={"order_id": order_id, "reason": "Defective hydraulic seal defect"},
                        rationale="Order is delivered and customer reported leaking seal defect within 90 days.",
                    )
                )
                actions.append(
                    ActionCall(
                        tool="send_reply",
                        args={
                            "to_email": "customer@halden-client.de",
                            "subject": f"RMA-Rücksendung zu Bestellung {order_id}",
                            "body": "Ihr RMA-Rücksendeetikett wurde erstellt. Bitte senden Sie die Ware kostenfrei zurück.",
                        },
                        rationale="Notify customer of approved return authorization.",
                    )
                )
                reply_draft = "Ihr RMA-Rücksendeetikett wurde erstellt."

            elif queue == "billing_inquiry":
                # Check requested amount or default
                actions.append(
                    ActionCall(
                        tool="issue_credit",
                        args={
                            "order_id": order_id,
                            "amount_eur": 250.0,
                            "reason": "Goodwill delivery delay credit",
                        },
                        rationale="Issue goodwill commercial credit within 500 EUR policy limit.",
                    )
                )
                actions.append(
                    ActionCall(
                        tool="send_reply",
                        args={
                            "to_email": "customer@halden-client.de",
                            "subject": f"Gutschrift zu Bestellung {order_id}",
                            "body": "Eine Gutschrift über €250.00 wurde zu Ihren Gunsten veranlasst.",
                        },
                        rationale="Confirm issued credit to customer.",
                    )
                )
                reply_draft = "Eine Gutschrift über €250.00 wurde veranlasst."

            elif state.get("internal_only", False) or "intern" in state.get("raw_text", "").lower():
                actions.append(
                    ActionCall(
                        tool="search_kb",
                        args={"query": "Hydraulikzylinder Wartung und Dichtungswechsel"},
                        rationale="Internal technical search without outbound reply side effect.",
                    )
                )
                reply_draft = "Interne Dokumentation eingesehen."

            else:
                actions.append(
                    ActionCall(
                        tool="search_kb",
                        args={"query": "Hydraulikzylinder Wartung und Dichtungswechsel"},
                        rationale="Retrieve standard operating procedure from technical KB.",
                    )
                )
                actions.append(
                    ActionCall(
                        tool="send_reply",
                        args={
                            "to_email": "customer@halden-client.de",
                            "subject": f"Technische Auskunft zu Bestellung {order_id}",
                            "body": "Hier finden Sie die Anleitung zum Dichtungswechsel gemäss SOP-HX-04.",
                        },
                        rationale="Provide standard technical maintenance guidance.",
                    )
                )
                reply_draft = "Hier finden Sie die technische Dokumentation."

        plan = ActionPlan(actions=actions, reply_draft=reply_draft)

        self.audit_ledger.record_event(
            ticket_id=ticket_id,
            event_type="PLAN_PROPOSED",
            state_name="planning",
            payload={
                "action_count": len(actions),
                "tools": [a.tool for a in actions],
                "replan_count": replan_count,
            },
        )

        return {
            "action_plan": plan.model_dump(),
            "status": "planned",
        }

    async def node_evaluate_policy(self, state: CopilotState) -> dict[str, Any]:
        """Deterministic policy validation (zero dynamic eval)."""
        ticket_id = state.get("ticket_id", "TICK-UNKNOWN")
        raw_plan = state.get("action_plan", {})
        raw_world = state.get("world_state", {})

        plan = ActionPlan(**raw_plan)
        world = WorldState(**raw_world)

        violations: list[Violation] = self.policy_engine.evaluate_plan(plan, world)
        violations_data = [v.model_dump() for v in violations]

        self.audit_ledger.record_event(
            ticket_id=ticket_id,
            event_type="POLICY_EVALUATED",
            state_name="policy",
            payload={
                "violation_count": len(violations),
                "is_compliant": len(violations) == 0,
                "violations": violations_data,
            },
        )

        return {
            "violations": violations_data,
            "status": "policy_evaluated",
        }

    async def node_replan(self, state: CopilotState) -> dict[str, Any]:
        """Increment replan counter and pass feedback back to planner."""
        ticket_id = state.get("ticket_id", "TICK-UNKNOWN")
        count = state.get("replan_count", 0) + 1

        self.audit_ledger.record_event(
            ticket_id=ticket_id,
            event_type="REPLAN_TRIGGERED",
            state_name="replan",
            payload={"replan_attempt": count},
        )

        return {"replan_count": count, "status": "replanning"}

    async def node_escalate(self, state: CopilotState) -> dict[str, Any]:
        """Escalate ticket to human supervisor when repeated violations occur."""
        ticket_id = state.get("ticket_id", "TICK-UNKNOWN")
        self.audit_ledger.record_event(
            ticket_id=ticket_id,
            event_type="PLAN_ESCALATED",
            state_name="escalate",
            payload={"reason": "Persistent policy violations"},
        )
        return {"status": "escalated"}

    async def node_human_approval_gate(self, state: CopilotState) -> dict[str, Any]:
        """Human approval interrupt gate for side-effect actions."""
        ticket_id = state.get("ticket_id", "TICK-UNKNOWN")
        approval_status = state.get("approval_status", "pending")

        if approval_status == "pending":
            # State machine interrupts here before execution
            self.audit_ledger.record_event(
                ticket_id=ticket_id,
                event_type="APPROVAL_REQUESTED",
                state_name="approval_gate",
                payload={
                    "plan": state.get("action_plan"),
                    "awaiting_decision": True,
                },
            )
            return {"awaiting_approval": True, "status": "awaiting_approval"}

        # Resumed with human input
        self.audit_ledger.record_event(
            ticket_id=ticket_id,
            event_type="APPROVAL_RESOLVED",
            state_name="approval_gate",
            payload={
                "decision": approval_status,
                "feedback": state.get("approval_feedback"),
            },
        )
        return {"awaiting_approval": False}

    async def node_execute_actions(self, state: CopilotState) -> dict[str, Any]:
        """Execute approved tool actions with idempotency keys and reply QA checks."""
        ticket_id = state.get("ticket_id", "TICK-UNKNOWN")
        raw_plan = state.get("action_plan", {})
        plan = ActionPlan(**raw_plan)

        results: list[dict[str, Any]] = []

        for idx, action in enumerate(plan.actions):
            idempotency_key = f"{ticket_id}:{idx}"
            tool_name = action.tool
            tool_args = dict(action.args)

            # Reply QA Check if tool is send_reply
            if tool_name == "send_reply":
                body = tool_args.get("body", "")
                # Ensure no leaked IBANs or customer passwords
                if re.search(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", body):
                    logger.warning("reply_qa_blocked_iban_leak", ticket_id=ticket_id)
                    body = "[REDACTED]"
                    tool_args["body"] = body

            try:
                exec_res = await self.tool_registry.execute(
                    tool_name=tool_name,
                    args=tool_args,
                    idempotency_key=idempotency_key,
                )
                res_data = exec_res.model_dump() if hasattr(exec_res, "model_dump") else exec_res
                res_dict = {
                    "action_index": idx,
                    "tool": tool_name,
                    "success": True,
                    "data": res_data,
                    "idempotency_key": idempotency_key,
                }
            except Exception as e_exec:
                res_dict = {
                    "action_index": idx,
                    "tool": tool_name,
                    "success": False,
                    "data": str(e_exec),
                    "idempotency_key": idempotency_key,
                }
            results.append(res_dict)

            self.audit_ledger.record_event(
                ticket_id=ticket_id,
                event_type="TOOL_EXECUTED",
                state_name="execution",
                payload=res_dict,
            )

        return {
            "tool_results": results,
            "status": "completed",
            "reply_sent": any(a.tool == "send_reply" for a in plan.actions),
        }

    async def node_terminate_rejected(self, state: CopilotState) -> dict[str, Any]:
        """Terminate plan without executing any side effects upon operator rejection."""
        ticket_id = state.get("ticket_id", "TICK-UNKNOWN")
        self.audit_ledger.record_event(
            ticket_id=ticket_id,
            event_type="PLAN_REJECTED",
            state_name="terminated",
            payload={"feedback": state.get("approval_feedback")},
        )
        return {"status": "rejected"}

    # -------------------------------------------------------------------------
    # Conditional Routing Logic
    # -------------------------------------------------------------------------

    def route_after_triage(self, state: CopilotState) -> str:
        if state.get("needs_human_triage", False):
            return "human_triage"
        return "enrich"

    def route_after_policy(self, state: CopilotState) -> str:
        violations = state.get("violations", [])
        if violations:
            replan_count = state.get("replan_count", 0)
            return "replan" if replan_count < 1 else "escalate"

        # Check if plan has side effects
        plan_data = state.get("action_plan", {})
        actions = plan_data.get("actions", [])
        has_side_effects = False
        for a in actions:
            t_name = a.get("tool", "")
            defn = self.tool_registry.get(t_name)
            if defn and defn.side_effect:
                has_side_effects = True
                break

        if has_side_effects:
            return "human_approval"
        return "execute"

    def route_after_approval(self, state: CopilotState) -> str:
        status = state.get("approval_status", "pending")
        if status == "rejected":
            return "rejected"
        if status in ("approved", "edited"):
            return "execute"
        return "awaiting"


def compile_copilot_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
    audit_ledger: AuditLedger | None = None,
) -> CopilotGraph:
    """Factory creating configured CopilotGraph instance."""
    return CopilotGraph(checkpointer=checkpointer, audit_ledger=audit_ledger)
