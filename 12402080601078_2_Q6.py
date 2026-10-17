"""
Enrollment : 12402080601078
Assignment : 2          Question : Q6
Title      : Log Anomaly Detector using Sliding Window

Run:
    python 12402080601078_2_Q6.py < sample_data/q6_input.txt
    python 12402080601078_2_Q6.py sample_data/q6_input.txt

Input  : "X T" / n / n lines of "timestamp user ip status"
         timestamp = HH:MM | HH:MM:SS | YYYY-MM-DD HH:MM[:SS]   (logs sorted)
         status    = FAIL | SUCCESS
Output : suspicious users in lexicographic order with the timestamp of their
         FIRST suspicious success:   "u1 00:07"

Definition used (assumptions made explicit)
    * A "burst" = at least X FAIL events of a user inside a window of length
      T minutes (last_fail_time - first_fail_time <= T).
    * After a burst, a SUCCESS from an IP different from the IP of the latest
      failed attempt makes the user suspicious.
    * A SUCCESS from the same IP as the latest failure is a normal login: the
      failure history of that user is cleared (the burst is forgiven).
    * With plain HH:MM timestamps, a time that goes backwards means the log
      rolled over midnight and 1440 minutes are added.
    * Malformed lines are skipped (counted, reported on stderr).

Algorithm
    One deque of failure times per user.  Each failure is appended once and
    popped at most once -> amortised O(1) per log line.
    Regex parses each line.

Complexity
    Time  : O(n)
    Space : O(active failures per user)  (+ one flag/IP per user)
"""

import re
import sys
from collections import deque

LINE_RE = re.compile(
    r"^\s*((?:\d{4}-\d{2}-\d{2}[ T])?\d{1,2}:\d{2}(?::\d{2})?)\s+"
    r"(\S+)\s+"
    r"(\d{1,3}(?:\.\d{1,3}){3}|[0-9A-Fa-f:]+)\s+"
    r"(FAIL|SUCCESS)\s*$",
    re.IGNORECASE,
)
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[ T](.*)$")


def days_from_civil(y, m, d):
    """Days since 1970-01-01 (no datetime import needed, fast)."""
    y -= m <= 2
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def to_minutes(ts):
    """(minutes, has_date).  Seconds become fractions of a minute."""
    base = 0
    has_date = False
    m = DATE_RE.match(ts)
    if m:
        has_date = True
        base = days_from_civil(int(m[1]), int(m[2]), int(m[3])) * 1440
        ts = m[4]
    parts = ts.split(":")
    mins = int(parts[0]) * 60 + int(parts[1])
    if len(parts) == 3:
        mins += int(parts[2]) / 60.0
    return base + mins, has_date


def detect(lines, x_limit, t_window):
    fails = {}          # user -> deque of failure times (the sliding window)
    last_fail_ip = {}   # user -> ip of the latest failure
    burst = set()       # users that had >= X failures inside one T-minute window
    flagged = {}        # user -> timestamp text of the first suspicious success
    day_offset = 0
    last_time = -1.0
    bad_lines = 0

    for raw in lines:
        m = LINE_RE.match(raw)
        if not m:
            if raw.strip():
                bad_lines += 1
            continue
        ts_text, user, ip, status = m.group(1), m.group(2), m.group(3), m.group(4).upper()
        try:
            minutes, has_date = to_minutes(ts_text)
        except ValueError:
            bad_lines += 1
            continue
        if not has_date:                      # HH:MM only -> handle midnight rollover
            if minutes < last_time - day_offset:
                day_offset += 1440
            minutes += day_offset
        last_time = minutes

        if user in flagged:                   # already reported, first success only
            continue

        if status == "FAIL":
            dq = fails.get(user)
            if dq is None:
                dq = fails[user] = deque()
            dq.append(minutes)
            last_fail_ip[user] = ip
            while minutes - dq[0] > t_window:     # slide the window
                dq.popleft()
            if len(dq) >= x_limit:                # burst detected
                burst.add(user)
        else:  # SUCCESS
            if user in burst and ip != last_fail_ip[user]:
                flagged[user] = ts_text
                fails.pop(user, None)             # free memory, user is done
                continue
            # normal login (or no burst yet): forgive earlier failures
            fails.pop(user, None)
            burst.discard(user)
            last_fail_ip.pop(user, None)
    return flagged, bad_lines


def main():
    src = open(sys.argv[1], encoding="utf-8") if len(sys.argv) > 1 else sys.stdin
    try:
        x_limit, t_window = map(int, src.readline().split())
        n = int(src.readline())
    except ValueError:
        print("Error: expected first line 'X T' and second line 'n'")
        sys.exit(1)
    if not (1 <= x_limit <= 100 and 1 <= t_window <= 1440 and 1 <= n <= 2_000_000):
        print("Error: constraints 1<=X<=100, 1<=T<=1440, 1<=n<=2000000")
        sys.exit(1)

    def take(limit):
        for _ in range(limit):
            line = src.readline()
            if not line:
                break
            yield line

    flagged, bad = detect(take(n), x_limit, t_window)
    for user in sorted(flagged):
        print(f"{user} {flagged[user]}")
    if bad:
        print(f"(skipped {bad} malformed line(s))", file=sys.stderr)


if __name__ == "__main__":
    main()
