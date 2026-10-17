"""
Enrollment : 12402080601078
Assignment : 2          Question : Q7
Title      : Generator-Based JSON ETL Pipeline

Run:
    python 12402080601078_2_Q7.py sample_data/q7_sensors.jsonl
    python 12402080601078_2_Q7.py sample_data/q7_sensors.jsonl --unit F
    (without an argument the program asks for the path)

Pipeline (every stage is a generator -> the file is never fully in memory)
    read_lines   : yields raw lines of the JSONL file
    parse_json   : yields (device_id_or_None, record_or_None)  [None = corrupt JSON]
    validate     : yields (device_id, clean_temp_c) or marks corruption
    transform    : converts the unit (Celsius default, --unit F / K optional)
    aggregate    : consumes the stream once and keeps only per-device counters

A record is CORRUPTED when
    * the line is not valid JSON or not a JSON object
    * device_id is missing/empty
    * temperature_c is missing, not numeric (strings like "bad", booleans,
      null, NaN, infinity)
    * humidity is present but not numeric or outside 0..100
      (humidity / timestamp may be absent - the sample record has no timestamp)
Corrupted records that still carry a device_id are counted against that device;
the others (broken JSON / no device_id) are reported on a final "(unattributed)"
line.

Output per device (sorted by device_id):
    D1 count=1 min=30 max=30 avg=30.00 corrupted=1

Complexity
    Time  : O(number of records)
    Space : O(number of devices)   (5 numbers per device)
"""

import json
import math
import sys


def read_lines(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield line


def parse_json(lines):
    for line in lines:
        try:
            rec = json.loads(line)
        except (ValueError, RecursionError):
            yield None, None
            continue
        if not isinstance(rec, dict):
            yield None, None
            continue
        dev = rec.get("device_id")
        if isinstance(dev, (str, int)) and not isinstance(dev, bool) and str(dev).strip():
            yield str(dev).strip(), rec
        else:
            yield None, None


def as_number(value):
    """Return float for real numbers (or numeric strings), else None."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        num = float(value)
    else:
        return None            # "bad" and also "30" strings are rejected on purpose
    return num if math.isfinite(num) else None


def validate(pairs):
    """Yield (device, temp_c) for good records, (device, None) for corrupted."""
    for dev, rec in pairs:
        if dev is None:
            yield None, None
            continue
        temp = as_number(rec.get("temperature_c"))
        if temp is None:
            yield dev, None
            continue
        if "humidity" in rec:
            hum = as_number(rec["humidity"])
            if hum is None or not (0 <= hum <= 100):
                yield dev, None
                continue
        yield dev, temp


def transform(items, unit):
    for dev, temp in items:
        if temp is not None:
            if unit == "F":
                temp = temp * 9 / 5 + 32
            elif unit == "K":
                temp = temp + 273.15
        yield dev, temp


def aggregate(items):
    stats = {}          # dev -> [count, min, max, total, corrupted]
    unattributed = 0
    for dev, temp in items:
        if dev is None:
            unattributed += 1
            continue
        s = stats.get(dev)
        if s is None:
            s = stats[dev] = [0, math.inf, -math.inf, 0.0, 0]
        if temp is None:
            s[4] += 1
        else:
            s[0] += 1
            s[3] += temp
            if temp < s[1]:
                s[1] = temp
            if temp > s[2]:
                s[2] = temp
    return stats, unattributed


def fmt(v):
    text = f"{v:.2f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def main():
    args = sys.argv[1:]
    unit = "C"
    if "--unit" in args:
        i = args.index("--unit")
        try:
            unit = args[i + 1].upper()
            del args[i:i + 2]
        except IndexError:
            pass
        if unit not in ("C", "F", "K"):
            print("Error: --unit must be C, F or K")
            sys.exit(1)
    path = args[0] if args else input("Path of JSONL file: ").strip()

    try:
        pipeline = transform(validate(parse_json(read_lines(path))), unit)
        stats, unattributed = aggregate(pipeline)
    except OSError as exc:
        print(f"Error: cannot read file: {exc}")
        sys.exit(1)

    for dev in sorted(stats):
        cnt, lo, hi, total, bad = stats[dev]
        if cnt:
            print(f"{dev} count={cnt} min={fmt(lo)} max={fmt(hi)} "
                  f"avg={total / cnt:.2f} corrupted={bad}")
        else:
            print(f"{dev} count=0 min=NA max=NA avg=NA corrupted={bad}")
    if unattributed:
        print(f"(unattributed) corrupted={unattributed}")


if __name__ == "__main__":
    main()
