"""Governed data access for agents (04_ARCHITECTURE §7).

Two layers: this guard rejects anything that is not a plain SELECT on the marts schema, and the database
user (agent_reader, profile agent_readonly) is read-only with a 10 s timeout and a 500-row cap regardless.
"""
import os
import re
from datetime import date, datetime
from decimal import Decimal

MAX_ROWS = 500
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|attach|detach|rename|grant|revoke|optimize|kill|"
    r"system|outfile|url|s3|file|remote|mysql|postgresql)\b", re.I)
_TABLE = re.compile(r"\b(?:from|join)\s+([A-Za-z_][\w.]*)", re.I)
_CTE = re.compile(r"\b([A-Za-z_]\w*)\s+as\s*\(", re.I)


class UnsafeQuery(ValueError):
    pass


def check_select(sql: str) -> str:
    """Return the query ready to run, or raise UnsafeQuery."""
    sql = sql.strip().rstrip(";").strip()
    bare = re.sub(r"'[^']*'", "''", sql)  # string literals cannot hide keywords or tables
    if ";" in bare:
        raise UnsafeQuery("one statement only")
    if not re.match(r"(?is)^\s*(select|with)\b", bare):
        raise UnsafeQuery("only SELECT queries are allowed")
    if (bad := _FORBIDDEN.search(bare)):
        raise UnsafeQuery(f"forbidden keyword: {bad.group(1)}")
    ctes = {m.lower() for m in _CTE.findall(bare)}
    for table in _TABLE.findall(bare):
        if table.lower() not in ctes and not table.lower().startswith("marts."):
            raise UnsafeQuery(f"only marts.* tables are allowed, got {table}")
    if not re.search(r"\blimit\s+\d+\s*$", bare, re.I):
        sql += f"\nLIMIT {MAX_ROWS}"
    return sql


def plain(value):
    """Make a ClickHouse value JSON-friendly: Decimal -> float, dates -> ISO strings."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10] if isinstance(value, date) and not isinstance(value, datetime) else value.isoformat()
    return value


def marts_client():
    import clickhouse_connect

    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
        username="agent_reader",
        password=os.getenv("CLICKHOUSE_AGENT_PASSWORD", ""),
        autogenerate_session_id=False,
    )


def make_runner(client=None):
    """A run(sql) -> list[dict] function bound to the guarded read-only client."""
    client = client or marts_client()

    def run(sql: str) -> list[dict]:
        result = client.query(check_select(sql))
        return [{k: plain(v) for k, v in row.items()} for row in result.named_results()]

    return run
