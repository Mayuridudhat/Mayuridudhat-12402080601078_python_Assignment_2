"""
Enrollment : 12402080601078
Assignment : 2          Question : Q10
Title      : Python Data Visualization Dashboard Exporter

Required packages : pip install pandas matplotlib   (use of pandas/matplotlib is
                    assumed to be permitted by the faculty, as the question allows)

Run:
    python 12402080601078_2_Q10.py marks.csv output
    python 12402080601078_2_Q10.py              (asks for both paths)

Input  : marks CSV with columns  enrollment, name, <subject 1> ... <subject s>
         (s <= 20, marks 0..100 or empty)
Output (written into the output folder, created if missing):
    cleaned_marks.csv        cleaned data + Average + Grade columns
    summary.csv              subject-wise statistics
    grade_distribution.png   number of students per grade
    subject_average.png      average mark of every subject
    top_performers.png       top 10 students by average

Cleaning rules (assumptions)
    * header names are trimmed; 'enrollment' and 'name' are found ignoring case
    * rows with an empty enrollment are dropped; duplicate enrollments -> first kept
    * a mark that is not a number or is outside 0..100 is treated as MISSING
    * missing marks are filled with the mean of that subject (2 decimals);
      a subject that has no valid mark at all is dropped (with a warning)
    * Average = mean of the cleaned marks of the student
    * Grade (average): A+ >=90, A >=80, B+ >=70, B >=60, C >=50, D >=40, F <40
Summary statistics are computed on the RECORDED (valid) marks only, so imputed
values do not influence them; 'Missing_Filled' shows how many were imputed and
'Pass_Percentage' is the share of recorded marks >= 40.

Complexity
    Time  : O(n * s)
    Space : O(n * s)  - the whole table is held by pandas (about 160 MB for the
            maximum 1,000,000 students x 20 subjects).  A streaming alternative
            would read the CSV in chunks and keep running sums per subject, but
            the cleaned file and the top-10 chart need every row anyway.
"""

import os
import sys

try:
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")                 # draw to files, no window needed
    import matplotlib.pyplot as plt
except ImportError:                                        # pragma: no cover
    print("Missing packages. Install them with:  pip install pandas matplotlib")
    sys.exit(1)

PASS_MARK = 40
MAX_SUBJECTS = 20
GRADE_LABELS = ["F", "D", "C", "B", "B+", "A", "A+"]
GRADE_BINS = [-0.01, 40, 50, 60, 70, 80, 90, 100.01]          # [low, high) per grade
BAR_COLOR = "#2a6f97"
TOP_N = 10


# -------------------------------------------------------------- cleaning
def load_and_clean(path):
    """Return (cleaned_df, summary_df, info_dict, id_col, name_col, subjects)."""
    raw = pd.read_csv(path, dtype=str, keep_default_na=False, skipinitialspace=True)
    raw.columns = [c.strip() for c in raw.columns]
    if raw.empty:
        raise ValueError("the CSV file has no data rows")

    lookup = {c.lower(): c for c in raw.columns}
    if "enrollment" not in lookup or "name" not in lookup:
        raise ValueError("CSV must contain 'enrollment' and 'name' columns "
                         f"(found: {', '.join(raw.columns)})")
    id_col, name_col = lookup["enrollment"], lookup["name"]
    subjects = [c for c in raw.columns if c not in (id_col, name_col)]
    if not subjects:
        raise ValueError("CSV has no subject columns")
    if len(subjects) > MAX_SUBJECTS:
        raise ValueError(f"at most {MAX_SUBJECTS} subjects are allowed, found {len(subjects)}")

    info = {"rows_in": len(raw)}

    # ---- identity columns
    raw[id_col] = raw[id_col].str.strip()
    raw[name_col] = raw[name_col].str.strip().replace("", "Unknown")
    no_id = raw[id_col] == ""
    info["dropped_no_enrollment"] = int(no_id.sum())
    raw = raw[~no_id]
    dup = raw.duplicated(subset=id_col, keep="first")
    info["dropped_duplicates"] = int(dup.sum())
    raw = raw[~dup].reset_index(drop=True)
    if raw.empty:
        raise ValueError("no valid rows left after removing bad enrollments")

    # ---- marks: text -> number, invalid -> NaN
    marks = raw[subjects].apply(lambda col: pd.to_numeric(col.str.strip(), errors="coerce"))
    was_filled = raw[subjects].apply(lambda col: col.str.strip() != "")
    out_of_range = (marks < 0) | (marks > 100)
    info["invalid_marks"] = int((out_of_range | (marks.isna() & was_filled)).sum().sum())
    marks = marks.mask(out_of_range)                    # outside 0..100 -> missing

    empty_subjects = [s for s in subjects if marks[s].notna().sum() == 0]
    if empty_subjects:
        info["dropped_subjects"] = empty_subjects
        marks = marks.drop(columns=empty_subjects)
        subjects = [s for s in subjects if s not in empty_subjects]
    if not subjects:
        raise ValueError("no subject has any valid mark")

    # ---- summary on recorded marks, then imputation
    pass_pct = (marks >= PASS_MARK).sum() / marks.notna().sum() * 100
    summary = pd.DataFrame({
        "Subject": subjects,
        "Count": [int(marks[s].notna().sum()) for s in subjects],
        "Missing_Filled": [int(marks[s].isna().sum()) for s in subjects],
        "Mean": marks.mean().round(2).values,
        "Median": marks.median().round(2).values,
        "Std_Dev": marks.std(ddof=0).round(2).values,
        "Min": marks.min().values,
        "Max": marks.max().values,
        "Pass_Percentage": pass_pct.round(2).values,
    })
    info["missing_filled"] = int(marks.isna().sum().sum())
    cleaned_marks = marks.fillna(marks.mean()).round(2)

    cleaned = pd.concat([raw[[id_col, name_col]], cleaned_marks], axis=1)
    cleaned["Average"] = cleaned_marks.mean(axis=1).round(2)
    cleaned["Grade"] = pd.cut(cleaned["Average"], bins=GRADE_BINS, labels=GRADE_LABELS,
                              right=False).astype(str)
    info["rows_out"] = len(cleaned)
    return cleaned, summary, info, id_col, name_col, subjects


# ---------------------------------------------------------------- charts
def style_axes(ax, title, xlabel, ylabel):
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.spines[["top", "right"]].set_visible(False)


def chart_grade_distribution(cleaned, path):
    counts = cleaned["Grade"].value_counts().reindex(GRADE_LABELS[::-1], fill_value=0)
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(counts.index, counts.values, color=BAR_COLOR)
    ax.bar_label(bars, padding=3)
    style_axes(ax, "Grade Distribution", "Grade (by average marks)", "Number of students")
    ax.set_ylim(0, max(counts.max() * 1.15, 1))
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def chart_subject_average(summary, path):
    fig, ax = plt.subplots(figsize=(max(7, 1.0 * len(summary) + 3), 5))
    bars = ax.bar(summary["Subject"], summary["Mean"], color=BAR_COLOR)
    ax.bar_label(bars, fmt="%.1f", padding=3)
    style_axes(ax, "Subject-wise Average Marks", "Subject", "Average marks (out of 100)")
    ax.set_ylim(0, 105)
    ax.axhline(PASS_MARK, color="#b23a48", linestyle="--", linewidth=1,
               label=f"Pass mark ({PASS_MARK})")
    ax.legend(loc="upper right", frameon=False)
    if len(summary) > 8:
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def chart_top_performers(cleaned, id_col, name_col, path):
    top = cleaned.sort_values(["Average", id_col], ascending=[False, True]).head(TOP_N)
    labels = [f"{n} ({e})" for n, e in zip(top[name_col], top[id_col])]
    fig, ax = plt.subplots(figsize=(9, max(4, 0.55 * len(top) + 1.5)))
    bars = ax.barh(labels, top["Average"], color=BAR_COLOR)
    ax.bar_label(bars, fmt="%.2f", padding=3)
    ax.invert_yaxis()                                   # best student on top
    style_axes(ax, f"Top {len(top)} Performers (average marks)", "Average marks", "")
    ax.set_xlim(0, 105)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ------------------------------------------------------------------ main
def main():
    if len(sys.argv) >= 3:
        csv_path, out_dir = sys.argv[1], sys.argv[2]
    else:
        csv_path = input("Path of marks CSV: ").strip()
        out_dir = input("Output folder path: ").strip()

    try:
        cleaned, summary, info, id_col, name_col, subjects = load_and_clean(csv_path)
    except FileNotFoundError:
        sys.exit(f"Error: file not found: {csv_path}")
    except (ValueError, pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        sys.exit(f"Error: {exc}")

    try:
        os.makedirs(out_dir, exist_ok=True)
        cleaned.to_csv(os.path.join(out_dir, "cleaned_marks.csv"), index=False, float_format="%g")
        summary.to_csv(os.path.join(out_dir, "summary.csv"), index=False, float_format="%g")
        chart_grade_distribution(cleaned, os.path.join(out_dir, "grade_distribution.png"))
        chart_subject_average(summary, os.path.join(out_dir, "subject_average.png"))
        chart_top_performers(cleaned, id_col, name_col, os.path.join(out_dir, "top_performers.png"))
    except OSError as exc:
        sys.exit(f"Error: cannot write output: {exc}")

    print(f"Rows read: {info['rows_in']}  ->  rows kept: {info['rows_out']} "
          f"(no enrollment: {info['dropped_no_enrollment']}, duplicates: {info['dropped_duplicates']})")
    print(f"Invalid marks treated as missing: {info['invalid_marks']}, "
          f"missing marks filled with subject mean: {info['missing_filled']}")
    if info.get("dropped_subjects"):
        print("Warning: subjects with no valid marks were dropped:", ", ".join(info["dropped_subjects"]))
    print(f"Subjects analysed: {', '.join(subjects)}")
    print("Files written to", os.path.abspath(out_dir))
    for name in ("cleaned_marks.csv", "summary.csv", "grade_distribution.png",
                 "subject_average.png", "top_performers.png"):
        print("  ", name)


if __name__ == "__main__":
    main()
