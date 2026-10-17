"""
Enrollment : 12402080601078
Assignment : 2          Question : Q4
Title      : SQL Join Query Builder and Validator

Required package : pip install mysql-connector-python   (only to EXECUTE the query)
Setup            : mysql -u root -p < schema.sql        (tables + sample data)

Run:
    python 12402080601078_2_Q4.py query.json --user root           (build + run)
    python 12402080601078_2_Q4.py query.json --dry-run             (build only, no DB)
    python 12402080601078_2_Q4.py --query '{"columns":["student.name"],"limit":5}' --dry-run
    cat query.json | python 12402080601078_2_Q4.py --user root     (JSON from stdin)

JSON input
    {
      "columns": ["student.name", "course.name"],          # required, projection
      "where":   [{"column": "course.id", "op": "=", "value": "PY101"}],   # optional
      "order":   {"column": "student.spi", "direction": "DESC"},           # optional
      "limit":   2                                          # optional, 1..1000 (default 100)
    }
    Shorthand also accepted:  "where": ["course.id=PY101", "student.spi>=8"],
                              "order": "student.spi DESC"
    Operators: =  !=  <  <=  >  >=  LIKE  BETWEEN (value = [low, high])

Allowed columns (whitelist - anything else is rejected before any SQL exists)
    student.id/name/spi   course.id/name/credits
    courseregistration.student_id / courseregistration.course_id

Safety rules
    * table / column names are NEVER taken from the user text: they are looked up
      in the whitelist and replaced by the fixed names (s.name, c.id ...)
    * values only travel as %s parameters, after type checking
      (int / float / str per column; booleans, NaN, inf, over-long text rejected)
    * LIKE only on text columns; LIMIT must be an integer 1..1000
    * text values: course ids must be 1-20 letters/digits/_/-; ';', '--', '/*', '#',
      backslashes and control characters are rejected (defence in depth)
    * unknown JSON keys, too many columns/filters, bad operators are rejected

Output
    SQL_OK / generated SQL template / parameter list / result table
    or  SQL_REJECTED: <reason>   (exit code 2)

Complexity
    Validation O(columns + filters); result memory O(limit)
"""

import argparse
import getpass
import json
import math
import re
import sys

# --------------------------------------------------------------- whitelist
# user-visible name -> (SQL expression, python type)
COLUMNS = {
    "student.id": ("s.id", int),
    "student.name": ("s.name", str),
    "student.spi": ("s.spi", float),
    "course.id": ("c.id", str),
    "course.name": ("c.name", str),
    "course.credits": ("c.credits", int),
    "courseregistration.student_id": ("r.student_id", int),
    "courseregistration.course_id": ("r.course_id", str),
}
FROM_JOIN = (
    "FROM Student AS s "
    "JOIN CourseRegistration AS r ON r.student_id = s.id "
    "JOIN Course AS c ON c.id = r.course_id"
)
ID_COLUMNS = {"course.id", "courseregistration.course_id"}
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,20}$")
# defence in depth: values are parameters anyway, but statement terminators,
# comment markers, backslashes and control characters are never valid here
UNSAFE_TEXT_RE = re.compile(r"[;\\\x00-\x1f]|--|/\*|\*/|#")
OPERATORS = {"=", "!=", "<", "<=", ">", ">=", "LIKE", "BETWEEN"}
ALLOWED_KEYS = {"columns", "where", "order", "limit"}
MAX_COLUMNS, MAX_FILTERS, MAX_TEXT = 8, 10, 100

COND_RE = re.compile(
    r"^\s*([A-Za-z_.]+)\s*(>=|<=|!=|=|>|<|\bLIKE\b|\bBETWEEN\b)\s*(.+?)\s*$", re.I)


class Rejected(Exception):
    """Raised for any invalid / unsafe request."""


# --------------------------------------------------------------- validation
def column_expr(name, what):
    if not isinstance(name, str):
        raise Rejected(f"{what}: column name must be text")
    key = name.strip().lower()
    if key not in COLUMNS:
        raise Rejected(f"{what}: column '{name}' is not allowed")
    return key, COLUMNS[key][0], COLUMNS[key][1]


def coerce(value, typ, column):
    """Check a filter value against the column type -> python value."""
    if isinstance(value, bool) or value is None:
        raise Rejected(f"value for {column} must be a {typ.__name__}")
    if typ is str:
        if not isinstance(value, (str, int, float)):
            raise Rejected(f"value for {column} must be text")
        text = str(value)
        if len(text) > MAX_TEXT or not text.strip():
            raise Rejected(f"value for {column} must be 1-{MAX_TEXT} characters")
        if column in ID_COLUMNS and not ID_RE.match(text):
            raise Rejected(f"value for {column} must be 1-20 letters, digits, _ or -")
        if UNSAFE_TEXT_RE.search(text):
            raise Rejected(f"value for {column} contains unsafe characters")
        return text
    try:
        if typ is int:
            if isinstance(value, float) and not value.is_integer():
                raise ValueError
            return int(value)
        num = float(value)
        if not math.isfinite(num):
            raise ValueError
        return num
    except (ValueError, TypeError, OverflowError):
        raise Rejected(f"value for {column} must be a valid {typ.__name__}")


def parse_condition(cond):
    """dict or 'col op value' string -> (column, op, raw_value)."""
    if isinstance(cond, str):
        m = COND_RE.match(cond)
        if not m:
            raise Rejected(f"cannot read filter: {cond!r}")
        col, op, val = m.group(1), m.group(2).upper(), m.group(3)
        if op == "BETWEEN":
            parts = re.split(r"\s+AND\s+|,", val, flags=re.I)
            if len(parts) != 2:
                raise Rejected("BETWEEN needs two values: 'a AND b'")
            val = [p.strip() for p in parts]
        else:
            val = val.strip().strip("'\"")
        return col, op, val
    if isinstance(cond, dict):
        if set(cond) - {"column", "op", "value"} or not {"column", "op", "value"} <= set(cond):
            raise Rejected("a filter needs exactly: column, op, value")
        return cond["column"], str(cond["op"]).strip().upper(), cond["value"]
    raise Rejected("each filter must be an object or a string")


def build_query(request):
    """Validate the request dict -> (sql_template, params).  Raises Rejected."""
    if not isinstance(request, dict):
        raise Rejected("input must be a JSON object")
    unknown = set(request) - ALLOWED_KEYS
    if unknown:
        raise Rejected(f"unknown key(s): {', '.join(sorted(map(str, unknown)))}")

    # ---- projection
    cols = request.get("columns")
    if not isinstance(cols, list) or not cols:
        raise Rejected("'columns' must be a non-empty list")
    if len(cols) > MAX_COLUMNS:
        raise Rejected(f"at most {MAX_COLUMNS} columns allowed")
    select, seen = [], set()
    for c in cols:
        key, expr, _ = column_expr(c, "columns")
        if key not in seen:
            seen.add(key)
            select.append(f"{expr} AS {key.replace('.', '_')}")   # unique header names

    # ---- filters
    where_sql, params = [], []
    conditions = request.get("where", [])
    if not isinstance(conditions, list):
        raise Rejected("'where' must be a list")
    if len(conditions) > MAX_FILTERS:
        raise Rejected(f"at most {MAX_FILTERS} filters allowed")
    for cond in conditions:
        col, op, raw = parse_condition(cond)
        key, expr, typ = column_expr(col, "where")
        if op not in OPERATORS:
            raise Rejected(f"operator '{op}' is not allowed")
        if op == "LIKE":
            if typ is not str:
                raise Rejected(f"LIKE only works on text columns, not {key}")
            where_sql.append(f"{expr} LIKE %s")
            params.append(coerce(raw, str, key))
        elif op == "BETWEEN":
            if not (isinstance(raw, list) and len(raw) == 2):
                raise Rejected("BETWEEN needs a list of exactly two values")
            low, high = coerce(raw[0], typ, key), coerce(raw[1], typ, key)
            if low > high:
                raise Rejected("BETWEEN: low value is greater than high value")
            where_sql.append(f"{expr} BETWEEN %s AND %s")
            params.extend([low, high])
        else:
            where_sql.append(f"{expr} {op} %s")
            params.append(coerce(raw, typ, key))

    # ---- ordering
    order_sql = ""
    order = request.get("order")
    if order is not None:
        if isinstance(order, str):
            bits = order.split()
            if len(bits) not in (1, 2):
                raise Rejected("order must look like 'student.spi DESC'")
            order = {"column": bits[0], "direction": bits[1] if len(bits) == 2 else "ASC"}
        if not isinstance(order, dict) or set(order) - {"column", "direction"} \
                or "column" not in order:
            raise Rejected("order needs: column and optional direction")
        _, expr, _ = column_expr(order["column"], "order")
        direction = str(order.get("direction", "ASC")).strip().upper()
        if direction not in ("ASC", "DESC"):
            raise Rejected("direction must be ASC or DESC")
        order_sql = f" ORDER BY {expr} {direction}"

    # ---- limit
    limit = request.get("limit", 100)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise Rejected("limit must be an integer between 1 and 1000")

    sql = "SELECT " + ", ".join(select) + " " + FROM_JOIN
    if where_sql:
        sql += " WHERE " + " AND ".join(where_sql)
    sql += order_sql + " LIMIT %s"
    params.append(limit)
    return sql, params


# --------------------------------------------------------------- output
def cell(v):
    if isinstance(v, float) or (v is not None and type(v).__name__ == "Decimal"):
        text = f"{float(v):.2f}"
        return text[:-1] if text.endswith("0") else text
    return str(v)


def print_table(headers, rows):
    body = [[cell(v) for v in r] for r in rows]
    widths = [max([len(h)] + [len(r[i]) for r in body]) for i, h in enumerate(headers)]
    line = lambda items: "  ".join(t.ljust(w) for t, w in zip(items, widths)).rstrip()
    print(line(headers))
    print(line(["-" * w for w in widths]))
    for r in body:
        print(line(r))
    print(f"({len(body)} row{'s' if len(body) != 1 else ''})")


def execute(args, sql, params):
    try:
        import mysql.connector
        from mysql.connector import Error as MySQLError
    except ImportError:
        sys.exit("Missing package. Install it with:  pip install mysql-connector-python")
    conn = None
    try:
        password = args.password
        if password is None:
            try:
                password = getpass.getpass("MySQL password: ")
            except EOFError:
                password = ""
        conn = mysql.connector.connect(host=args.host, port=args.port, user=args.user,
                                       password=password, database=args.database)
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        headers = [d[0] for d in cur.description]
        cur.close()
        return headers, rows
    except MySQLError as exc:
        print(f"Database error: {exc}")
        sys.exit(1)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def main():
    ap = argparse.ArgumentParser(description="Safe SQL join query builder")
    ap.add_argument("json_file", nargs="?", help="JSON request file (or use --query / stdin)")
    ap.add_argument("--query", help="JSON request as a string")
    ap.add_argument("--dry-run", action="store_true", help="only build and print the SQL")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=3306)
    ap.add_argument("--user", default="root")
    ap.add_argument("--password")
    ap.add_argument("--database", default="college_db")
    args = ap.parse_args()

    try:
        if args.query is not None:
            text = args.query
        elif args.json_file:
            with open(args.json_file, "r", encoding="utf-8") as fh:
                text = fh.read()
        else:
            text = sys.stdin.read()
        try:
            request = json.loads(text)
        except ValueError as exc:
            raise Rejected(f"invalid JSON ({exc})")
        sql, params = build_query(request)
    except OSError as exc:
        print(f"Error: cannot read input: {exc}")
        sys.exit(1)
    except Rejected as exc:
        print(f"SQL_REJECTED: {exc}")
        sys.exit(2)

    print("SQL_OK")
    print("SQL    :", sql)
    print("PARAMS :", params)
    if args.dry_run:
        return
    print()
    headers, rows = execute(args, sql, params)
    print_table(headers, rows)


if __name__ == "__main__":
    main()
