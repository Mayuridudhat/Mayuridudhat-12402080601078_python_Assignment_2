# Programming with Python (202044504) - Assignment 2

| | |
|---|---|
| **Enrollment No.** | 12402080601078 |
| **Course** | B.Tech. Information Technology - Semester V |
| **Assignment** | 2 (Q1 - Q10) |
| **Python** | 3.10 or above |

File names follow the rule `Enrollment_AssignmentNo_QNo.py` / `Enrollment_AssignmentNo_QNo_folder`.
Every program starts with a comment block giving the problem, run command, assumptions and
time/space complexity.

## Repository layout

```
12402080601078_2_Q1.py              Regex email extractor
12402080601078_2_Q2.py              Offline HTML scraping ranker
12402080601078_2_Q3_folder/         MySQL student-course analytics  (code, schema.sql, student.csv, registration.csv)
12402080601078_2_Q4_folder/         SQL join query builder          (code, schema.sql, query.json)
12402080601078_2_Q5_folder/         Tkinter contact manager         (code, schema.sql)
12402080601078_2_Q6.py              Log anomaly detector (sliding window)
12402080601078_2_Q7.py              Generator-based JSON ETL
12402080601078_2_Q8.py              Matrix path DP
12402080601078_2_Q9.py              OOP inventory merger
12402080601078_2_Q10_folder/        Data visualization exporter     (code, marks.csv)
sample_data/                        Input files for Q1, Q2, Q6, Q7, Q8, Q9
requirements.txt
```

## Installation

```
pip install -r requirements.txt
```
Only Q3, Q4, Q5 (`mysql-connector-python`, MySQL server needed) and Q10 (`pandas`, `matplotlib`) need
external packages; the other questions use the standard library. Q5 needs Tkinter
(Linux: `sudo apt install python3-tk`).

## How to run

Run every command from the repository root.

| Q | Command |
|---|---------|
| Q1 | `python 12402080601078_2_Q1.py sample_data/q1_noisy.txt` |
| Q2 | `python 12402080601078_2_Q2.py sample_data/q2_input.txt` |
| Q3 | `python 12402080601078_2_Q3_folder/12402080601078_2_Q3.py --user root --database college_db --student-csv 12402080601078_2_Q3_folder/student.csv --registration-csv 12402080601078_2_Q3_folder/registration.csv --course PY101 --threshold 8.0` (password is asked, hidden) |
| Q4 | first `mysql -u root -p < 12402080601078_2_Q4_folder/schema.sql`, then `python 12402080601078_2_Q4_folder/12402080601078_2_Q4.py 12402080601078_2_Q4_folder/query.json --user root` (add `--dry-run` to only build the SQL) |
| Q5 | `python 12402080601078_2_Q5_folder/12402080601078_2_Q5.py` (MySQL password dialog opens; DB and table are created automatically) |
| Q6 | `python 12402080601078_2_Q6.py sample_data/q6_input.txt` |
| Q7 | `python 12402080601078_2_Q7.py sample_data/q7_sensors.jsonl` (optional `--unit F` or `K`) |
| Q8 | `python 12402080601078_2_Q8.py sample_data/q8_input.txt` |
| Q9 | `python 12402080601078_2_Q9.py sample_data/q9_input.txt` |
| Q10 | `python 12402080601078_2_Q10_folder/12402080601078_2_Q10.py 12402080601078_2_Q10_folder/marks.csv output` |

Database schema for Q3, Q4 and Q5 is in the `schema.sql` of each folder.
Q3 and Q4 use the same database `college_db` (tables `Student`, `CourseRegistration`, `Course`).

## Complexity summary

| Q | Time | Space |
|---|------|-------|
| Q1 | O(total characters) | O(unique valid emails) |
| Q2 | O(total HTML size + u log u) | O(u) |
| Q3 | Python O(rows); MySQL index lookups O(log n) | O(batch size) |
| Q4 | validation O(fields + filters) | O(result limit) |
| Q5 | indexed prefix search O(log n); "match anywhere" O(n) (documented) | O(result size, max 1000) |
| Q6 | O(n), each failure enters/leaves its deque once | O(active failures per user) |
| Q7 | O(records) | O(devices) |
| Q8 | O(n*m) | O(m) |
| Q9 | O(n + m + q) average | O(n + m) |
| Q10 | O(n*s) | O(n*s) (streaming alternative explained in the file) |

## Test cases

Each program was tested with the sample from the question, boundary cases and extra self-made cases.
"Expected" is what the program prints.

### Q1 - Email extractor
| Type | Input | Expected |
|---|---|---|
| Sample | `Contact a.b+1@adit.edu, root@@bad.com, test-user@x.org and a.b+1@adit.edu` | `adit.edu 1 a.b+1@adit.edu` / `x.org 1 test-user@x.org` |
| Boundary | empty file | no output |
| Boundary | line of 10,000 characters without a valid address | no output, runs in milliseconds |
| Extra | `x@a.COM X@a.com x@a.com y@a.com` and `bad@a.net` | `a.com 3 X@a.com` (.net ignored) |
| Extra | `p@q.com.au m@n.comx -@-.com a@-.com user@@twice.org` | all ignored |
| Extra | `(joe@dept.uni.edu),<ann@uni.edu>;"bob@uni.edu"` | `dept.uni.edu 1 joe@dept.uni.edu` / `uni.edu 2 ann@uni.edu` |
| Extra | `mail me at amy_9@adit.edu.` (full stop after address) | address accepted |
| Large | 109 MB / 1.5 M lines | about 6 s |

### Q2 - HTML ranker
| Type | Input | Expected |
|---|---|---|
| Sample | `2 2` + `q2_page1.html`, `q2_page2.html` | `Python Book 499 4.8` / `USB Keyboard 799 4.7` |
| Boundary | `1 1` + `q2_page2.html` (k = 1) | `USB Keyboard 799 4.7` (highest rating on that page) |
| Extra | two products with rating 4.7 priced 799 and 199 | the cheaper one (199) is listed first (tie-break: lower price, then name) |
| Boundary | `1 1001` | error: constraints are 1 <= p <= 5000 and 1 <= k <= 1000 |
| Extra | k=5, one path is a missing file | warning on stderr, then 3 unique products: Python Book 499 4.8, USB Keyboard 799 4.7, HDMI Cable 199 4.6 |
| Extra | duplicate `Python Book` (499/4.8 and 550/4.5) | only the better record (499, 4.8) is kept |
| Extra | product block with no price (`Broken Item`) | skipped |
| Extra | price `&#8377;1,299.00` | normalized to `1299` |

### Q3 - MySQL analytics (sample CSVs in the folder)
| Type | Input | Expected |
|---|---|---|
| Sample | course `PY101`, threshold `8.0` | `2201 Asha 9.1 PY101` / `2207 Dev 8.4 PY101` |
| Boundary | `PY101`, threshold `9.1` (strictly greater) | `(no matching students)` |
| Boundary | threshold `11` or course `PY101'; DROP TABLE Student;--` | rejected before any SQL runs |
| Extra | run the program twice | no duplicates, same result (upsert / ignore) |
| Extra | registration for unknown student `9999` | row skipped and reported, other rows loaded |
| Extra | CSV rows with bad id, empty name, SPI 11, SPI -1, SPI `abc` | each skipped with a message, valid rows loaded |
| Extra | wrong password / missing CSV file | clean error message, no traceback |

### Q4 - Query builder (`query.json` = sample)
| Type | Input | Expected |
|---|---|---|
| Sample | columns `student.name, course.name`, where `course.id=PY101`, order `student.spi DESC`, limit 2 | `SQL_OK`, SQL with `%s` placeholders, params `['PY101', 2]`, rows `Asha / Programming with Python`, `Dev / Programming with Python` |
| Boundary | `limit` 0, 1001, `"5; DROP"`, `true` | `SQL_REJECTED: limit must be an integer between 1 and 1000` |
| Extra | column `student.password` or `student.name; DROP TABLE Student` | `SQL_REJECTED: ... column ... is not allowed` |
| Extra | value `PY101 OR 1=1`, `x' OR '1'='1`, `a%;DROP`, `a%--` | rejected as unsafe |
| Extra | `LIKE` on `student.spi`, `BETWEEN [9,5]`, operator `; --`, unknown JSON key, invalid JSON | rejected with reason |
| Extra | `student.spi>=8`, `student.name LIKE A%`, `course.credits BETWEEN 3 AND 4` | valid parameterized SQL; returns `Asha` rows |

### Q5 - Tkinter contact manager
| Type | Action | Expected |
|---|---|---|
| Sample | Add name=Asha, email=asha@adit.edu, category=Faculty | record inserted and shown in the list |
| Boundary | Add `ASHA@adit.edu` again | "Duplicate email" warning, nothing inserted |
| Boundary | email `root@@bad.com`, `no-at.com`, `a@b`, empty; phone `12ab`; empty name | "Invalid input" warning, nothing inserted |
| Extra | select a row, change name, Update | list shows new name |
| Extra | Update a contact to another contact's email | rejected as duplicate |
| Extra | search `dev` / by email / by phone / "match anywhere" / no match | correct rows / empty list |
| Extra | sort by email | list re-ordered |
| Extra | Delete (with confirmation) / Delete with nothing selected | row removed / info message |
| Extra | Tools > Add 10,000 demo contacts, then search | table has 10,000+ rows; list capped at 1000 rows, search uses index |

### Q6 - Log anomaly detector
| Type | Input | Expected |
|---|---|---|
| Sample | `3 10`, 5 lines from the question | `u1 00:07` |
| Boundary | `X=1, T=1`: `10:00 z 1.1.1.1 FAIL`, `10:01 z 2.2.2.2 SUCCESS` | `z 10:01` |
| Extra | failures at 00:00, 00:06, 00:12 with T=10, X=3, then success from a new IP | no output (never 3 inside 10 minutes) |
| Extra | 2 failures, then success from the same IP, then success from a new IP | no output (normal login resets) |
| Extra | users a and b, times crossing midnight (23:55 ... 00:02), one garbage line | `a 00:05` / `b 00:02`, malformed line counted on stderr |
| Large | n = 2,000,000 lines, 50,000 users | about 6 s |

### Q7 - JSON ETL
| Type | Input | Expected |
|---|---|---|
| Sample | the two JSON lines from the question | `D1 count=1 min=30 max=30 avg=30.00 corrupted=1` |
| Extra | `sample_data/q7_sensors.jsonl` | `D2 count=2 min=21.5 max=23.25 avg=22.38 corrupted=1`, `D3 count=0 ... corrupted=1` (humidity 150), `D4 count=1 min=-5.5 ...`, `(unattributed) corrupted=2` (no device_id, broken JSON) |
| Extra | same file with `--unit F` | D1 min=86 max=86 |
| Boundary | missing file | clean error |
| Large | 1,000,000 records | about 5 s, memory stays small (generators) |

### Q8 - Matrix path DP
| Type | Input | Expected |
|---|---|---|
| Sample | `3 3 / 1 2 3 / 4 X 6 / 7 8 9` | `29 1` |
| Boundary | `1 1 / -7` | `-7 1` |
| Boundary | `2 2 / 1 2 / 3 X` (end blocked) | `IMPOSSIBLE` |
| Extra | `2 3 / 1 X 2 / X X 3` (walled in) | `IMPOSSIBLE` |
| Extra | `2 2` all ones / all zeros | `3 2` / `0 3` (ties counted) |
| Extra | missing cell in input | `Error: invalid input - expected 4 cells, found 3` |
| Large | 2000 x 2000, random scores and blocks | about 2.5 s |

### Q9 - Inventory merger
| Type | Input | Expected |
|---|---|---|
| Sample | A: `P1 Pen 10 5 8`, B: `P1 Pen 7 4 9`, `MERGE` | `P1 Pen stock=17 purchase=4 selling=9` |
| Extra | `COMPARE` on sample files | `COMPARE A(650) > B(88)` |
| Extra | `DELETE A P404` | `DELETE FAILED product P404 not found` |
| Extra | `ADD C ...` / negative price | failure message, inventories unchanged |
| Extra | `UPDATE A P1 0`, then `COMPARE` | valuation recalculated |
| Extra | malformed line inside an inventory file | warning on stderr, line skipped |

### Q10 - Dashboard exporter
| Type | Input | Expected |
|---|---|---|
| Sample | `marks.csv` (38 rows incl. messy rows) | `cleaned_marks.csv`, `summary.csv`, 3 PNG charts; 36 rows kept, 3 invalid marks, 5 filled |
| Boundary | 1,000,000 students x 10 subjects | finishes in about 17 s |
| Extra | empty enrollment / duplicate enrollment | row dropped / first row kept |
| Extra | mark `abs`, `105`, `-4`, blank | treated as missing and filled with subject mean |
| Extra | missing file, missing `enrollment`/`name` column, empty file, subject with no valid marks | clean error message |

## Main assumptions (details are in each file's header comment)

* **Q1** usernames are case-sensitive, domains are lower-cased; addresses glued to other address characters are invalid.
* **Q2** product pages use class names `product`, `name`, `price`, `rating`; duplicates compared by name ignoring case.
* **Q6** a burst is X failures inside T minutes; the success IP must differ from the last failed IP.
* **Q7** `timestamp` and `humidity` are optional; humidity, if present, must be numeric in 0..100.
* **Q9** valuation = stock x purchase price; `UPDATE` sets the stock to the given value.
* **Q10** missing marks are filled with the subject mean; statistics use recorded marks only.
