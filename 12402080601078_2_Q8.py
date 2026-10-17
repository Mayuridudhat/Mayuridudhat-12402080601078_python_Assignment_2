"""
Enrollment : 12402080601078
Assignment : 2          Question : Q8
Title      : Matrix Path Optimizer with Dynamic Programming

Run:
    python 12402080601078_2_Q8.py < sample_data/q8_input.txt
    python 12402080601078_2_Q8.py sample_data/q8_input.txt

Input  : "n m" then n rows of m tokens; 'X' = blocked cell, otherwise an integer
Output : "<max score> <number of max-score paths mod 1000000007>"
         or IMPOSSIBLE when no path exists (start/end blocked included)

Moves allowed : right, down, diagonal down-right (from (0,0) to (n-1,m-1)).

DP
    best[i][j]  = score(i,j) + max(best[i-1][j], best[i][j-1], best[i-1][j-1])
    ways[i][j]  = sum of ways[...] of the predecessors that give that maximum
    Only the previous row is kept  ->  O(m) extra memory.
    Scores can be negative, so "unreachable" is None, never 0.

Complexity
    Time  : O(n * m)
    Space : O(m)  (the grid itself is read row by row from the input text)
"""

import sys

MOD = 1_000_000_007


def solve(grid_rows, n, m):
    """grid_rows: iterable of n lists of m cells (int or None for blocked)."""
    prev_best = [None] * m
    prev_ways = [0] * m

    for i, row in enumerate(grid_rows):
        cur_best = [None] * m
        cur_ways = [0] * m
        for j in range(m):
            cell = row[j]
            if cell is None:                    # blocked
                continue
            if i == 0 and j == 0:
                cur_best[0], cur_ways[0] = cell, 1
                continue

            top = prev_best[j] if i else None
            left = cur_best[j - 1] if j else None
            diag = prev_best[j - 1] if (i and j) else None

            best = None
            for v in (top, left, diag):
                if v is not None and (best is None or v > best):
                    best = v
            if best is None:                    # no way to reach this cell
                continue

            w = 0
            if top == best:
                w += prev_ways[j]
            if left == best:
                w += cur_ways[j - 1]
            if diag == best:
                w += prev_ways[j - 1]

            cur_best[j] = best + cell
            cur_ways[j] = w % MOD
        prev_best, prev_ways = cur_best, cur_ways

    if prev_best[m - 1] is None:
        return None
    return prev_best[m - 1], prev_ways[m - 1]


def read_input(stream):
    tokens = stream.read().split()
    if len(tokens) < 2:
        raise ValueError("missing n and m")
    n, m = int(tokens[0]), int(tokens[1])
    if not (1 <= n <= 2000 and 1 <= m <= 2000):
        raise ValueError("constraints: 1 <= n, m <= 2000")
    if len(tokens) - 2 != n * m:
        raise ValueError(f"expected {n * m} cells, found {len(tokens) - 2}")

    def rows():
        pos = 2
        for _ in range(n):
            row = []
            for tok in tokens[pos:pos + m]:
                if tok in ("X", "x"):
                    row.append(None)
                else:
                    v = int(tok)
                    if not -10**6 <= v <= 10**6:
                        raise ValueError(f"score out of range: {v}")
                    row.append(v)
            pos += m
            yield row

    return n, m, rows()


def main():
    try:
        if len(sys.argv) > 1:
            with open(sys.argv[1], encoding="utf-8") as fh:
                n, m, rows = read_input(fh)
        else:
            n, m, rows = read_input(sys.stdin)
        result = solve(rows, n, m)
    except (ValueError, OSError) as exc:
        print(f"Error: invalid input - {exc}")
        sys.exit(1)

    if result is None:
        print("IMPOSSIBLE")
    else:
        print(result[0], result[1])


if __name__ == "__main__":
    main()
