"""
Enrollment : 12402080601078
Assignment : 2          Question : Q3
Title      : MySQL Student-Course Analytics Engine

Required package : pip install mysql-connector-python
Needs            : a running MySQL server (account that may CREATE DATABASE/TABLE)

Run (everything missing is asked interactively, the password is hidden):
    python 12402080601078_2_Q3.py --user root --database college_db \
           --student-csv student.csv --registration-csv registration.csv \
           --course PY101 --threshold 8.0

Files
    student.csv       : id,name,spi
    registration.csv  : student_id,course_id
    schema.sql        : table definitions (also created by the program itself)

Steps performed
    1. connect (host/port/user/password)      -> create database if missing
    2. CREATE TABLE IF NOT EXISTS Student, CourseRegistration (+ indexes)
    3. stream both CSVs, validate every row, insert in batches (executemany)
    4. SELECT students of the course with spi > threshold
       ORDER BY spi DESC, id ASC  and print  "id name spi course"

Safety
    * every value goes through %s placeholders (parameterized queries); only the
      database name is placed in SQL text, after a strict [A-Za-z0-9_] check
    * mysql.connector.Error is caught; each batch is committed or rolled back
    * duplicate student ids are updated (re-running the program is safe),
      duplicate registrations / registrations of unknown students are skipped
      and reported

Complexity
    Python : O(total rows) time, O(batch_size) memory (rows are streamed)
    MySQL  : PRIMARY KEY(course_id, student_id) gives O(log n) course lookup,
             idx_student_spi supports the SPI filter/ordering
"""

import argparse
import csv
import getpass
import re
import sys
from decimal import Decimal, InvalidOperation

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except ImportError:                                   # pragma: no cover
    print("Missing package. Install it with:  pip install mysql-connector-python")
    sys.exit(1)

DB_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,64}$")
COURSE_RE = re.compile(r"^[A-Za-z0-9_-]{1,20}$")
MAX_REPORTED_ERRORS = 5

CREATE_STUDENT = """
CREATE TABLE IF NOT EXISTS Student (
    id    INT          NOT NULL PRIMARY KEY,
    name  VARCHAR(100) NOT NULL,
    spi   DECIMAL(4,2) NOT NULL,
    CHECK (spi >= 0 AND spi <= 10),
    KEY idx_student_spi (spi)
)"""

CREATE_REGISTRATION = """
CREATE TABLE IF NOT EXISTS CourseRegistration (
    student_id INT         NOT NULL,
    course_id  VARCHAR(20) NOT NULL,
    PRIMARY KEY (course_id, student_id),
    KEY idx_reg_student (student_id),
    FOREIGN KEY (student_id) REFERENCES Student(id)
)"""

INSERT_STUDENT = ("INSERT INTO Student (id, name, spi) VALUES (%s, %s, %s) "
                  "ON DUPLICATE KEY UPDATE name = VALUES(name), spi = VALUES(spi)")
INSERT_REGISTRATION = ("INSERT IGNORE INTO CourseRegistration (student_id, course_id) "
                       "VALUES (%s, %s)")

QUERY = (
    "SELECT s.id, s.name, s.spi, r.course_id "
    "FROM Student AS s "
    "JOIN CourseRegistration AS r ON r.student_id = s.id "
    "WHERE r.course_id = %s AND s.spi > %s "
    "ORDER BY s.spi DESC, s.id ASC"
)


# ----------------------------------------------------------------- validation
def parse_student(row):
    """row dict -> (id, name, Decimal spi); raises ValueError on bad data."""
    sid = int(row["id"])
    name = (row["name"] or "").strip()
    if sid <= 0:
        raise ValueError("id must be positive")
    if not name or len(name) > 100:
        raise ValueError("name must be 1-100 characters")
    try:
        spi = Decimal(row["spi"].strip())
    except (InvalidOperation, AttributeError):
        raise ValueError("spi is not a number")
    if not spi.is_finite() or not Decimal("0") <= spi <= Decimal("10"):
        raise ValueError("spi must be between 0.0 and 10.0")
    return sid, name, spi.quantize(Decimal("0.01"))


def parse_registration(row):
    sid = int(row["student_id"])
    course = (row["course_id"] or "").strip()
    if sid <= 0:
        raise ValueError("student_id must be positive")
    if not COURSE_RE.match(course):
        raise ValueError("course_id must be 1-20 letters/digits/_/-")
    return sid, course


def batches(csv_path, parser, size, report):
    """Yield lists of valid parsed rows (at most `size` rows in memory)."""
    batch = []
    with open(csv_path, "r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for lineno, row in enumerate(reader, start=2):
            try:
                batch.append(parser(row))
            except (ValueError, KeyError, TypeError) as exc:
                report["bad"] += 1
                if report["bad"] <= MAX_REPORTED_ERRORS:
                    print(f"  skipped {csv_path} line {lineno}: {exc}")
                continue
            if len(batch) >= size:
                yield batch
                batch = []
    if batch:
        yield batch


# ------------------------------------------------------------------- database
FK_ERRORS = (1452,)      # "Cannot add or update a child row: a foreign key constraint fails"


def insert_rows_one_by_one(conn, cur, sql, batch, label):
    """Fallback for a failed batch: insert row by row, skip rows with unknown students."""
    done = skipped = 0
    for row in batch:
        try:
            cur.execute(sql, row)
            done += max(cur.rowcount, 0)
        except MySQLError as exc:
            if getattr(exc, "errno", None) in FK_ERRORS:
                skipped += 1
                if skipped <= MAX_REPORTED_ERRORS:
                    print(f"  skipped {label} row {row}: student id does not exist")
            else:
                conn.rollback()
                raise
    conn.commit()
    return done, skipped


def load_csv(conn, csv_path, parser, sql, size, label):
    report = {"bad": 0}
    inserted = total = unknown = 0
    cur = conn.cursor()
    try:
        for batch in batches(csv_path, parser, size, report):
            try:
                cur.executemany(sql, batch)
                conn.commit()
                inserted += max(cur.rowcount, 0)
            except MySQLError as exc:
                conn.rollback()
                if getattr(exc, "errno", None) not in FK_ERRORS:
                    raise
                done, skipped = insert_rows_one_by_one(conn, cur, sql, batch, label)
                inserted += done
                unknown += skipped
            total += len(batch)
    finally:
        cur.close()
    extra = f", {unknown} rows skipped (unknown student)" if unknown else ""
    print(f"{label}: {total} valid rows processed, {inserted} rows affected, "
          f"{report['bad']} invalid rows skipped{extra}")
    return total


def fmt_spi(value):
    """9.10 -> '9.1', 9.00 -> '9.0', 9.25 -> '9.25'"""
    text = f"{Decimal(str(value)):.2f}"
    return text[:-1] if text.endswith("0") else text


def ask(value, prompt, secret=False, default=None):
    if value not in (None, ""):
        return value
    shown = f"{prompt} [{default}]: " if default is not None else f"{prompt}: "
    try:
        text = getpass.getpass(shown) if secret else input(shown)
    except EOFError:                      # no keyboard (e.g. piped run): use default
        text = ""
    return text.strip() or default


def get_args():
    ap = argparse.ArgumentParser(description="MySQL student-course analytics")
    ap.add_argument("--host")
    ap.add_argument("--port", type=int)
    ap.add_argument("--user")
    ap.add_argument("--password")
    ap.add_argument("--database")
    ap.add_argument("--student-csv")
    ap.add_argument("--registration-csv")
    ap.add_argument("--course")
    ap.add_argument("--threshold")
    ap.add_argument("--batch-size", type=int, default=5000)
    a = ap.parse_args()
    a.host = ask(a.host, "MySQL host", default="localhost")
    a.port = int(ask(a.port, "MySQL port", default="3306"))
    a.user = ask(a.user, "MySQL user", default="root")
    a.password = ask(a.password, "MySQL password", secret=True, default="")
    a.database = ask(a.database, "Database name", default="college_db")
    a.student_csv = ask(a.student_csv, "Path of student.csv", default="student.csv")
    a.registration_csv = ask(a.registration_csv, "Path of registration.csv",
                             default="registration.csv")
    a.course = ask(a.course, "course_id (e.g. PY101)")
    a.threshold = ask(a.threshold, "spi_threshold (0.0-10.0)")
    return a


def main():
    args = get_args()

    # ---- validate user input before touching the database
    if not DB_NAME_RE.match(args.database or ""):
        sys.exit("Error: database name may contain only letters, digits and _")
    if not COURSE_RE.match(args.course or ""):
        sys.exit("Error: course_id must be 1-20 letters/digits/_/-")
    try:
        threshold = Decimal(args.threshold)
        if not threshold.is_finite() or not Decimal("0") <= threshold <= Decimal("10"):
            raise InvalidOperation
    except (InvalidOperation, TypeError):
        sys.exit("Error: spi_threshold must be a number between 0.0 and 10.0")
    if args.batch_size < 1:
        sys.exit("Error: --batch-size must be >= 1")

    conn = None
    try:
        conn = mysql.connector.connect(host=args.host, port=args.port,
                                       user=args.user, password=args.password)
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{args.database}`")
        cur.execute(f"USE `{args.database}`")
        cur.execute(CREATE_STUDENT)
        cur.execute(CREATE_REGISTRATION)
        conn.commit()
        cur.close()
        print(f"Connected. Tables ready in database '{args.database}'.")

        load_csv(conn, args.student_csv, parse_student, INSERT_STUDENT,
                 args.batch_size, "Student")
        load_csv(conn, args.registration_csv, parse_registration, INSERT_REGISTRATION,
                 args.batch_size, "CourseRegistration")

        print(f"\nStudents of {args.course} with SPI > {threshold}:")
        cur = conn.cursor()                      # non-buffered: rows are streamed
        cur.execute(QUERY, (args.course, threshold))
        count = 0
        for sid, name, spi, course in cur:
            print(f"{sid} {name} {fmt_spi(spi)} {course}")
            count += 1
        cur.close()
        if count == 0:
            print("(no matching students)")
    except FileNotFoundError as exc:
        print(f"Error: file not found: {exc.filename}")
        sys.exit(1)
    except MySQLError as exc:
        print(f"Database error: {exc}")
        sys.exit(1)
    finally:
        if conn is not None:
            try:
                conn.close()
            except MySQLError:
                pass


if __name__ == "__main__":
    main()
