"""Deterministic SQL AST safety validator using sqlglot."""

from __future__ import annotations

import sqlglot
from sqlglot import exp

from fieldkit_nl2sql.schemas import ValidationResult

ALLOWED_TABLES: set[str] = {
    "suppliers",
    "parts",
    "plants",
    "purchase_orders",
    "shipments",
    "quality_incidents",
    "certificates",
}

ALLOWED_FUNCTIONS: set[str] = {
    "count",
    "sum",
    "avg",
    "min",
    "max",
    "round",
    "coalesce",
    "date_trunc",
    "datetrunc",
    "timestamptrunc",
    "extract",
    "lower",
    "upper",
    "length",
    "substr",
    "substring",
    "trim",
    "concat",
    "now",
    "current_date",
    "currentdate",
    "current_timestamp",
    "currenttimestamp",
    "current_time",
    "currenttime",
    "date",
    "abs",
    "ceil",
    "floor",
    "nullif",
    "cast",
    "try_cast",
    "interval",
    "year",
    "month",
    "day",
}

DISALLOWED_FUNCTIONS: set[str] = {
    "pg_sleep",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "dblink",
    "dblink_exec",
    "lo_export",
    "lo_import",
    "current_setting",
    "set_config",
    "query_to_xml",
    "inet_client_addr",
    "version",
    "format",
}


class SQLValidator:
    """Validates and sanitizes SQL queries using sqlglot AST parsing."""

    def __init__(
        self,
        allowed_tables: set[str] | None = None,
        max_subquery_depth: int = 3,
        max_limit: int = 1000,
    ) -> None:
        self.allowed_tables = set(allowed_tables or ALLOWED_TABLES)
        self.max_subquery_depth = max_subquery_depth
        self.max_limit = max_limit

    def _calculate_subquery_depth(self, node: exp.Expression, current_depth: int = 0) -> int:
        """Compute the maximum nesting depth of subqueries and nested SELECTs."""
        max_child_depth = current_depth
        for child in node.args.values():
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, (exp.Select, exp.Subquery)):
                        depth = self._calculate_subquery_depth(item, current_depth + 1)
                        max_child_depth = max(max_child_depth, depth)
                    elif isinstance(item, exp.Expression):
                        depth = self._calculate_subquery_depth(item, current_depth)
                        max_child_depth = max(max_child_depth, depth)
            elif isinstance(child, (exp.Select, exp.Subquery)):
                depth = self._calculate_subquery_depth(child, current_depth + 1)
                max_child_depth = max(max_child_depth, depth)
            elif isinstance(child, exp.Expression):
                depth = self._calculate_subquery_depth(child, current_depth)
                max_child_depth = max(max_child_depth, depth)
        return max_child_depth

    def validate(self, sql_query: str) -> ValidationResult:
        """Validate an input SQL string for security, schema conformance, and bounded execution."""
        clean_sql = sql_query.strip()

        # 1. Reject comment tricks (-- or /* */)
        if "--" in clean_sql or "/*" in clean_sql:
            return ValidationResult(
                is_valid=False,
                error="SQL comments (-- or /* */) are disallowed for security",
            )

        # 2. Reject multiple statements (semicolon inside query)
        # Allow trailing semicolon at the very end
        normalized = clean_sql.rstrip(";\t\n ")
        if ";" in normalized:
            return ValidationResult(
                is_valid=False,
                error="Multiple SQL statements or embedded semicolons are disallowed",
            )

        # 3. Parse AST using sqlglot with PostgreSQL dialect
        try:
            parsed_statements = sqlglot.parse(normalized, read="postgres")
        except Exception as exc:
            return ValidationResult(is_valid=False, error=f"SQL parsing error: {exc}")

        if not parsed_statements:
            return ValidationResult(is_valid=False, error="Empty SQL query")

        if len(parsed_statements) > 1:
            return ValidationResult(
                is_valid=False,
                error="Multiple SQL statements detected; only single statements are permitted",
            )

        stmt = parsed_statements[0]
        if stmt is None:
            return ValidationResult(is_valid=False, error="Invalid SQL statement")

        # 4. Enforce Read-Only root statement (Select or Union of Selects)
        # Check for CTEs with data-modifying statements
        with_clause = stmt.args.get("with")
        if with_clause is not None and isinstance(with_clause, exp.With):
            for cte in with_clause.expressions:
                if not isinstance(cte.this, (exp.Select, exp.Union)):
                    return ValidationResult(
                        is_valid=False,
                        error="Data modification in Common Table Expressions (CTE) is disallowed",
                    )

        if not isinstance(stmt, (exp.Select, exp.Union)):
            return ValidationResult(
                is_valid=False,
                error=f"Disallowed statement type: {stmt.key.upper()}. Only SELECT queries are permitted",
            )

        # 5. Check for disallowed commands (into outfile, lo_export, etc.)
        if stmt.find(exp.Into):
            return ValidationResult(
                is_valid=False,
                error="SELECT INTO / OUTFILE statements are disallowed",
            )

        # 6. Tables allowlist verification
        tables_found: set[str] = set()
        for tbl in stmt.find_all(exp.Table):
            tbl_name = tbl.name.lower()
            # If schema qualifier exists (e.g. pg_catalog.x), verify
            schema_name = tbl.db.lower() if tbl.db else ""
            if schema_name and schema_name not in ("public", ""):
                return ValidationResult(
                    is_valid=False,
                    error=f"Access to schema '{schema_name}' is disallowed",
                )
            if tbl_name not in self.allowed_tables:
                return ValidationResult(
                    is_valid=False,
                    error=f"Disallowed table: '{tbl.name}'. Only ontology tables are accessible",
                )
            tables_found.add(tbl_name)

        # 7. Functions allowlist verification
        for func in stmt.find_all(exp.Func, exp.Anonymous):
            if isinstance(func, (exp.Connector, exp.Binary)):
                continue

            func_name = func.key.lower() if func.key else ""
            if not func_name and isinstance(func, exp.Anonymous):
                func_name = func.name.lower()

            if func_name in DISALLOWED_FUNCTIONS:
                return ValidationResult(
                    is_valid=False,
                    error=f"Dangerous function disallowed: '{func_name}'",
                )
            if func_name and func_name not in ALLOWED_FUNCTIONS:
                return ValidationResult(
                    is_valid=False,
                    error=f"Disallowed function: '{func_name}'",
                )

        # 8. Check Subquery depth
        depth = self._calculate_subquery_depth(stmt)
        if depth > self.max_subquery_depth:
            return ValidationResult(
                is_valid=False,
                error=f"Subquery nesting depth ({depth}) exceeds limit of {self.max_subquery_depth}",
            )

        # 9. Clamp or Inject LIMIT 1000
        limit_expr = stmt.args.get("limit")
        limit_val = self.max_limit
        if limit_expr is not None:
            try:
                # Extract numeric limit
                existing_limit = int(limit_expr.expression.this)
                if existing_limit > self.max_limit or existing_limit <= 0:
                    limit_expr.set("expression", exp.Literal.number(self.max_limit))
                else:
                    limit_val = existing_limit
            except Exception:
                limit_expr.set("expression", exp.Literal.number(self.max_limit))
        else:
            # Inject LIMIT 1000
            stmt.set("limit", exp.Limit(expression=exp.Literal.number(self.max_limit)))

        sanitized_sql = stmt.sql(dialect="postgres")

        return ValidationResult(
            is_valid=True,
            sanitized_sql=sanitized_sql,
            tables=sorted(tables_found),
            statement_type="SELECT",
            has_limit=True,
            limit_value=limit_val,
        )
