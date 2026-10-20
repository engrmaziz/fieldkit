"""Deterministic business policy engine for Halden Ops Copilot.

Enforces strict compliance constraints:
- issue_credit.amount_eur <= 500.0
- create_rma requires order.status == 'delivered' and delivered_at within 90 days
- any tool with side_effect == True is blocked if customer.legal_hold == True
- escalate is always permitted regardless of customer status or policy
- caller must have required_role
ZERO dynamic code evaluation (eval/exec is strictly prohibited).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml
from fieldkit_common.auth import Principal
from fieldkit_common.logging import get_logger

from .models import ActionPlan, Violation, WorldState

logger = get_logger("fieldkit.copilot.policy")

DEFAULT_POLICY_PATH = Path(__file__).resolve().parent / "policy.yaml"

# Default metadata for tool side-effects and roles
TOOL_METADATA: dict[str, dict[str, object]] = {
    "lookup_order": {"side_effect": False, "required_role": "support"},
    "get_shipments": {"side_effect": False, "required_role": "support"},
    "search_kb": {"side_effect": False, "required_role": "support"},
    "create_rma": {"side_effect": True, "required_role": "support"},
    "issue_credit": {"side_effect": True, "required_role": "support"},
    "escalate": {"side_effect": False, "required_role": "support"},
    "send_reply": {"side_effect": True, "required_role": "support"},
}


class PolicyEngine:
    """Deterministic policy validator checking ActionPlans against policy rules."""

    def __init__(self, policy_path: Path | str | None = None) -> None:
        self.policy_path = Path(policy_path) if policy_path else DEFAULT_POLICY_PATH
        self.rules: dict[str, object] = {}
        self.max_credit_eur: float = 500.0
        self.max_rma_days: int = 90
        self.load_rules()

    def load_rules(self) -> None:
        """Load and parse policy.yaml rules."""
        if self.policy_path.exists():
            try:
                content = self.policy_path.read_text(encoding="utf-8")
                data = yaml.safe_load(content) or {}
                self.rules = data.get("rules", {})
                credit_rule = self.rules.get("issue_credit", {})
                if isinstance(credit_rule, dict):
                    self.max_credit_eur = float(credit_rule.get("max_amount_eur", 500.0))
                rma_rule = self.rules.get("create_rma", {})
                if isinstance(rma_rule, dict):
                    self.max_rma_days = int(rma_rule.get("max_delivered_days", 90))
            except Exception as exc:
                logger.warning("failed_to_load_policy_yaml_using_defaults", error=str(exc))

    def check(
        self,
        plan: ActionPlan,
        world: WorldState,
        principal: Principal | None = None,
    ) -> list[Violation]:
        """Verify action plan against deterministic business policies.

        Returns list of Violations. If empty, the plan is compliant.
        """
        violations: list[Violation] = []

        for idx, action in enumerate(plan.actions):
            tool_name = action.tool
            meta = TOOL_METADATA.get(tool_name, {"side_effect": True, "required_role": "support"})
            is_side_effect = bool(meta.get("side_effect", True))
            req_role = str(meta.get("required_role", "support"))

            # Exemption: 'escalate' is ALWAYS allowed unconditionally
            if tool_name == "escalate":
                continue

            # 1. Role-based permission check
            if principal is not None:
                if not principal.has_role(req_role) and not principal.has_role("admin"):
                    violations.append(
                        Violation(
                            action_index=idx,
                            rule="role_permission",
                            message=(
                                f"Action '{tool_name}' requires role '{req_role}', "
                                f"but user '{principal.username}' possesses roles {principal.roles}."
                            ),
                            tool=tool_name,
                        )
                    )

            # 2. Strict Legal Hold Check: block all side-effect mutating tools
            if world.customer and world.customer.legal_hold and is_side_effect:
                violations.append(
                    Violation(
                        action_index=idx,
                        rule="legal_hold",
                        message=(
                            f"Customer '{world.customer.customer_id}' ({world.customer.name}) is under strict "
                            f"legal hold. Mutating side-effect action '{tool_name}' is forbidden."
                        ),
                        tool=tool_name,
                    )
                )

            # 3. Tool-Specific Policy: issue_credit
            if tool_name == "issue_credit":
                amount = float(action.args.get("amount_eur", 0.0))
                if amount <= 0.0:
                    violations.append(
                        Violation(
                            action_index=idx,
                            rule="credit_positive_amount",
                            message="Credit amount must be greater than €0.00.",
                            tool=tool_name,
                        )
                    )
                elif amount > self.max_credit_eur:
                    violations.append(
                        Violation(
                            action_index=idx,
                            rule="credit_limit_exceeded",
                            message=(
                                f"Requested credit of €{amount:.2f} exceeds policy limit of "
                                f"€{self.max_credit_eur:.2f} without executive sign-off."
                            ),
                            tool=tool_name,
                        )
                    )

            # 4. Tool-Specific Policy: create_rma
            if tool_name == "create_rma":
                if world.order is None:
                    violations.append(
                        Violation(
                            action_index=idx,
                            rule="rma_order_required",
                            message="RMA creation requires an identified customer order in world state.",
                            tool=tool_name,
                        )
                    )
                else:
                    # Check 4a: Order status must be 'delivered'
                    if world.order.status != "delivered":
                        violations.append(
                            Violation(
                                action_index=idx,
                                rule="rma_order_not_delivered",
                                message=(
                                    f"RMA can only be created for delivered orders; "
                                    f"order '{world.order.order_id}' has status '{world.order.status}'."
                                ),
                                tool=tool_name,
                            )
                        )
                    # Check 4b: Delivery date must be within 90 days
                    elif world.order.delivered_at is None:
                        violations.append(
                            Violation(
                                action_index=idx,
                                rule="rma_missing_delivery_date",
                                message=f"Order '{world.order.order_id}' has no delivery timestamp recorded.",
                                tool=tool_name,
                            )
                        )
                    else:
                        try:
                            deliv_dt = datetime.fromisoformat(world.order.delivered_at)
                            elapsed_days = (datetime.now(UTC) - deliv_dt).days
                            if elapsed_days > self.max_rma_days:
                                violations.append(
                                    Violation(
                                        action_index=idx,
                                        rule="rma_window_expired",
                                        message=(
                                            f"RMA return window expired: order '{world.order.order_id}' was delivered "
                                            f"{elapsed_days} days ago (policy limit: {self.max_rma_days} days)."
                                        ),
                                        tool=tool_name,
                                    )
                                )
                        except Exception as exc:
                            violations.append(
                                Violation(
                                    action_index=idx,
                                    rule="rma_invalid_delivery_date",
                                    message=f"Failed to parse order delivery timestamp: {exc}",
                                    tool=tool_name,
                                )
                            )

        return violations
