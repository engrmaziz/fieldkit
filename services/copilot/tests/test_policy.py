"""Unit tests for deterministic policy engine rules (Zero dynamic eval)."""

from datetime import UTC, datetime, timedelta

from fieldkit_common.auth import Principal
from fieldkit_copilot.models import ActionCall, ActionPlan, WorldState
from fieldkit_copilot.policy import PolicyEngine
from fieldkit_mock_erp.models import Customer, Order, OrderItem


def _make_world(
    order_status: str = "delivered",
    days_ago: int = 14,
    legal_hold: bool = False,
    order_id: str = "PO-1001",
) -> WorldState:
    now = datetime.now(UTC)
    deliv_at = (now - timedelta(days=days_ago)).isoformat() if order_status == "delivered" else None
    order = Order(
        order_id=order_id,
        customer_id="CUST-001",
        plant="DE-HAM",
        status=order_status,
        order_date=(now - timedelta(days=days_ago + 5)).isoformat(),
        delivered_at=deliv_at,
        total_eur=2400.0,
        items=[
            OrderItem(
                part_id="HX-400", part_name="Control Valve", quantity=2, unit_price_eur=1200.0
            )
        ],
    )
    customer = Customer(
        customer_id="CUST-001",
        name="Test Customer GmbH",
        country="DE",
        plant="DE-HAM",
        tier="standard",
        legal_hold=legal_hold,
    )
    return WorldState(
        ticket_id="TCK-9901",
        customer=customer,
        order=order,
    )


def test_issue_credit_policy_rules() -> None:
    """Verifies credit amount ceiling (<= €500.00) and positive amount rules."""
    engine = PolicyEngine()
    world = _make_world()
    support_user = Principal(sub="lukas-1", username="lukas", roles=["support"], plant="DE-STR")

    # Positive: Credit €250.00 <= €500.00
    plan_ok = ActionPlan(
        actions=[
            ActionCall(
                tool="issue_credit",
                args={"order_id": "PO-1001", "amount_eur": 250.0},
                rationale="Goodwill",
            )
        ]
    )
    violations = engine.check(plan_ok, world, principal=support_user)
    assert len(violations) == 0

    # Boundary: Exactly €500.00
    plan_boundary = ActionPlan(
        actions=[
            ActionCall(
                tool="issue_credit",
                args={"order_id": "PO-1001", "amount_eur": 500.0},
                rationale="Max goodwill",
            )
        ]
    )
    assert len(engine.check(plan_boundary, world, support_user)) == 0

    # Negative: Credit €500.01 > €500.00
    plan_exceeded = ActionPlan(
        actions=[
            ActionCall(
                tool="issue_credit",
                args={"order_id": "PO-1001", "amount_eur": 500.01},
                rationale="Exceeded",
            )
        ]
    )
    v_exceeded = engine.check(plan_exceeded, world, support_user)
    assert len(v_exceeded) == 1
    assert v_exceeded[0].rule == "credit_limit_exceeded"
    assert "exceeds policy limit" in v_exceeded[0].message

    # Negative: Zero or negative credit
    plan_zero = ActionPlan(
        actions=[
            ActionCall(
                tool="issue_credit",
                args={"order_id": "PO-1001", "amount_eur": 0.0},
                rationale="Zero",
            )
        ]
    )
    v_zero = engine.check(plan_zero, world, support_user)
    assert len(v_zero) == 1
    assert v_zero[0].rule == "credit_positive_amount"


def test_create_rma_policy_rules() -> None:
    """Verifies RMA delivery window (<= 90 days) and delivered status constraints."""
    engine = PolicyEngine()
    support_user = Principal(sub="lukas-1", username="lukas", roles=["support"], plant="DE-STR")
    rma_args = {
        "order_id": "PO-1001",
        "reason": "Defective valve",
        "items": [{"part_id": "HX-400", "quantity": 1}],
    }

    # Positive: Delivered 14 days ago (<= 90 days)
    world_valid = _make_world(order_status="delivered", days_ago=14)
    plan_valid = ActionPlan(
        actions=[ActionCall(tool="create_rma", args=rma_args, rationale="Valid return")]
    )
    assert len(engine.check(plan_valid, world_valid, support_user)) == 0

    # Negative: Delivered 120 days ago (> 90 days)
    world_expired = _make_world(order_status="delivered", days_ago=120)
    v_expired = engine.check(plan_valid, world_expired, support_user)
    assert len(v_expired) == 1
    assert v_expired[0].rule == "rma_window_expired"
    assert "expired" in v_expired[0].message.lower()

    # Negative: Order status in_transit (!= delivered)
    world_transit = _make_world(order_status="in_transit", days_ago=5)
    v_transit = engine.check(plan_valid, world_transit, support_user)
    assert len(v_transit) == 1
    assert v_transit[0].rule == "rma_order_not_delivered"

    # Negative: Missing order entirely
    world_no_order = WorldState(ticket_id="TCK-9902", customer=None, order=None)
    v_no_order = engine.check(plan_valid, world_no_order, support_user)
    assert len(v_no_order) == 1
    assert v_no_order[0].rule == "rma_order_required"


def test_legal_hold_blocks_side_effects_only() -> None:
    """Verifies that customer legal hold blocks mutating tools while permitting read-only and escalate."""
    engine = PolicyEngine()
    support_user = Principal(sub="lukas-1", username="lukas", roles=["support"], plant="DE-STR")
    world_hold = _make_world(legal_hold=True)

    # 1. Mutating tools are strictly blocked
    mutating_plan = ActionPlan(
        actions=[
            ActionCall(
                tool="create_rma",
                args={"order_id": "PO-1001", "reason": "Leak", "items": []},
                rationale="RMA",
            ),
            ActionCall(
                tool="issue_credit",
                args={"order_id": "PO-1001", "amount_eur": 100.0},
                rationale="Credit",
            ),
            ActionCall(
                tool="send_reply",
                args={"ticket_id": "TCK-1", "to_email": "c@h.de", "subject": "S", "body": "B"},
                rationale="Reply",
            ),
        ]
    )
    v_hold = engine.check(mutating_plan, world_hold, support_user)
    assert len(v_hold) == 3
    for v in v_hold:
        assert v.rule == "legal_hold"
        assert "legal hold" in v.message.lower()

    # 2. Read-only tools and escalate are allowed even under legal hold
    safe_plan = ActionPlan(
        actions=[
            ActionCall(tool="lookup_order", args={"order_id": "PO-1001"}, rationale="Inspect"),
            ActionCall(tool="get_shipments", args={"order_id": "PO-1001"}, rationale="Tracking"),
            ActionCall(tool="search_kb", args={"query": "leak"}, rationale="Check spec"),
            ActionCall(
                tool="escalate",
                args={"ticket_id": "TCK-1", "reason": "Legal hold customer inquiry"},
                rationale="Escalate to legal",
            ),
        ]
    )
    v_safe = engine.check(safe_plan, world_hold, support_user)
    assert len(v_safe) == 0


def test_escalate_always_permitted() -> None:
    """Verifies that escalate is unconditionally allowed regardless of user role or policy."""
    engine = PolicyEngine()
    world = _make_world(legal_hold=True)
    unauthorized_viewer = Principal(
        sub="view-1", username="viewer", roles=["viewer"], plant="DE-STR"
    )

    plan = ActionPlan(
        actions=[
            ActionCall(
                tool="escalate",
                args={"ticket_id": "TCK-9901", "reason": "Complex hydraulic defect"},
                rationale="Escalate",
            )
        ]
    )
    violations = engine.check(plan, world, principal=unauthorized_viewer)
    assert len(violations) == 0


def test_role_permissions_enforced() -> None:
    """Verifies that actions enforce required_role (support)."""
    engine = PolicyEngine()
    world = _make_world()
    viewer_user = Principal(sub="view-1", username="viewer", roles=["viewer"], plant="DE-STR")
    admin_user = Principal(sub="jana-1", username="jana", roles=["admin"], plant=None)

    plan = ActionPlan(
        actions=[ActionCall(tool="lookup_order", args={"order_id": "PO-1001"}, rationale="Lookup")]
    )

    # Viewer fails
    v_viewer = engine.check(plan, world, principal=viewer_user)
    assert len(v_viewer) == 1
    assert v_viewer[0].rule == "role_permission"

    # Admin passes
    v_admin = engine.check(plan, world, principal=admin_user)
    assert len(v_admin) == 0
