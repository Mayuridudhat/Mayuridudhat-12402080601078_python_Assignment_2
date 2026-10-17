"""
Enrollment : 12402080601078
Assignment : 2          Question : Q1
Title      : Regex-Based Email Intelligence Extractor

Run:
    python 12402080601078_2_Q1.py                      (asks for the file path)
    python 12402080601078_2_Q1.py sample_data/q1_noisy.txt

What it does
    Streams the text file line by line (never loads the whole file), pulls out
    valid e-mail addresses whose TLD is com / edu / org and prints, for every
    domain (lexicographic order):  domain  unique_user_count  smallest_email

Validity rules (assumptions)
    * username : letters, digits, + . _ -   (at least one character)
    * domain   : labels of letters/digits/hyphen (not starting or ending with a
                 hyphen) separated by dots, ending in .com / .edu / .org
                 (TLD is case-insensitive, domain is stored in lower case)
    * an address glued to other address characters (root@@bad.com,
      a@b.com.au, a@b.comx) is NOT valid and is ignored
    * a sentence-ending dot after the address ("mail me at a@b.com.") is fine
    * "unique users" of a domain = distinct usernames seen for that domain
      (usernames are case-sensitive: Zed@x.com and zed@x.com are 2 users)

Complexity
    Time  : O(total characters)  - one regex scan per line
    Space : O(unique valid emails)  - only unique emails are remembered
"""

import re
import sys

# (?<![...])  : the username must not be glued to a previous address character
# (?![...])   : the TLD must not continue (blocks .comx, .com.au, ...)
EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9+._@-])"
    r"([A-Za-z0-9+._-]+)"
    r"@"
    r"((?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+(?:com|edu|org))"
    r"(?![A-Za-z0-9-]|\.[A-Za-z0-9])",
    re.IGNORECASE,
)

MAX_LINE = 10000  # constraint from the question


def scan_file(path):
    """Return {domain: [set_of_usernames, smallest_email]} by streaming the file."""
    domains = {}
    # errors="replace": noisy files may contain bad bytes; never crash on them
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if len(line) > MAX_LINE + 1:      # defensive: ignore absurd lines
                line = line[:MAX_LINE]
            for m in EMAIL_RE.finditer(line):
                user = m.group(1)
                domain = m.group(2).lower()
                email = f"{user}@{domain}"
                entry = domains.get(domain)
                if entry is None:
                    domains[domain] = [{user}, email]
                else:
                    entry[0].add(user)
                    if email < entry[1]:
                        entry[1] = email
    return domains


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else input("Path of text file: ").strip()
    try:
        domains = scan_file(path)
    except FileNotFoundError:
        print(f"Error: file not found: {path}")
        sys.exit(1)
    except (PermissionError, IsADirectoryError, OSError) as exc:
        print(f"Error: cannot read file: {exc}")
        sys.exit(1)

    for domain in sorted(domains):
        users, smallest = domains[domain]
        print(f"{domain} {len(users)} {smallest}")


if __name__ == "__main__":
    main()
