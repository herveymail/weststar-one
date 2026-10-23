"""Reads a MariaDB/MySQL dump file (from mysqldump / mariadb-dump / phpMyAdmin) directly, so the old
data can be imported from an uploaded backup without running a MariaDB server.

Only CREATE TABLE (for column names) and INSERT statements are looked at; nothing in the file is
ever executed. Values come back as Python types: None, int, Decimal, str (dates stay text, which the
importer already understands) or bytes for binary/hex values.
"""
import gzip
import io
import re
import zipfile
from decimal import Decimal, InvalidOperation

_CREATE = re.compile(r"^CREATE TABLE `([^`]+)`", re.I)
_COLUMN = re.compile(r"^\s+`([^`]+)`\s+\w")
_INSERT = re.compile(r"^(?:INSERT|REPLACE)\s+(?:IGNORE\s+)?INTO\s+`([^`]+)`\s*(\(([^)]*)\))?\s*VALUES\s*", re.I)
_ESCAPES = {"0": "\0", "b": "\b", "n": "\n", "r": "\r", "t": "\t", "Z": "\x1a", "\\": "\\", "'": "'", '"': '"', "%": "\\%", "_": "\\_"}
_NUM = re.compile(r"-?(\d+\.?\d*([eE][-+]?\d+)?|\.\d+)")


class DumpError(ValueError):
    pass


def open_dump(path: str) -> io.TextIOBase:
    """Opens .sql, .sql.gz, or a .zip holding one .sql/.sql.gz file, as text."""
    with open(path, "rb") as fh:
        head = fh.read(4)
    if head[:2] == b"\x1f\x8b":
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", errors="replace")
    if head[:4] == b"PK\x03\x04":
        zf = zipfile.ZipFile(path)
        names = [n for n in zf.namelist() if n.lower().endswith((".sql", ".sql.gz")) and not n.startswith("__MACOSX")]
        if len(names) != 1:
            raise DumpError("The zip file should contain exactly one .sql (or .sql.gz) file.")
        raw = zf.open(names[0])
        if names[0].lower().endswith(".gz"):
            raw = gzip.GzipFile(fileobj=raw)
        return io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
    return open(path, encoding="utf-8", errors="replace")


def _parse_values(s: str, i: int, line_no: int):
    """Yields one tuple per (…) group in an INSERT … VALUES list, starting at s[i]."""
    n = len(s)
    while i < n:
        while i < n and s[i] in " \t\r\n,":
            i += 1
        if i >= n or s[i] == ";":
            return
        if s[i] != "(":
            raise DumpError(f"Unexpected text in the backup near line {line_no}.")
        i += 1
        row = []
        while True:
            while s[i] in " \t":
                i += 1
            c = s[i]
            if c == "'" or (c == "_" and s.startswith("_binary '", i)):
                if c == "_":
                    i += 8
                i += 1
                buf, start = [], i
                while True:
                    j = s.find("'", i)
                    k = s.find("\\", i)
                    if j < 0:
                        raise DumpError(f"Unfinished text value near line {line_no}.")
                    if 0 <= k < j:
                        buf.append(s[start:k])
                        buf.append(_ESCAPES.get(s[k + 1], s[k + 1]))
                        i = start = k + 2
                        continue
                    if j + 1 < n and s[j + 1] == "'":  # '' inside a string
                        buf.append(s[start:j] + "'")
                        i = start = j + 2
                        continue
                    buf.append(s[start:j])
                    i = j + 1
                    break
                row.append("".join(buf))
            elif s.startswith("NULL", i):
                row.append(None)
                i += 4
            elif s.startswith("0x", i) or s.startswith("0X", i):
                m = re.compile(r"0[xX]([0-9a-fA-F]*)").match(s, i)
                row.append(bytes.fromhex(m.group(1)))
                i = m.end()
            elif s.startswith("b'", i):
                j = s.index("'", i + 2)
                bits = s[i + 2:j]
                row.append(int(bits, 2) if bits else 0)
                i = j + 1
            else:
                m = _NUM.match(s, i)
                if not m:
                    raise DumpError(f"Couldn't read a value near line {line_no}.")
                text = m.group(0)
                if re.fullmatch(r"-?\d+", text):
                    row.append(int(text))
                else:
                    try:
                        row.append(Decimal(text))
                    except InvalidOperation:
                        row.append(text)
                i = m.end()
            while s[i] in " \t":
                i += 1
            if s[i] == ",":
                i += 1
                continue
            if s[i] == ")":
                i += 1
                yield tuple(row)
                break
            raise DumpError(f"Unexpected text in the backup near line {line_no}.")


class DumpSource:
    """Same interface the importer uses for a live database: has(table) and read(table, order)."""

    def __init__(self, path: str):
        self.columns: dict[str, list[str]] = {}
        self.rows: dict[str, list[tuple]] = {}
        current = None
        with open_dump(path) as fh:
            pending = ""
            for line_no, line in enumerate(fh, 1):
                if pending:  # an INSERT that a dump tool wrapped over several lines
                    pending += line
                    if not pending.rstrip().endswith(";"):
                        continue
                    line, pending = pending, ""
                m = _CREATE.match(line)
                if m:
                    current = m.group(1)
                    self.columns[current] = []
                    self.rows.setdefault(current, [])
                    continue
                if current is not None:
                    c = _COLUMN.match(line)
                    if c:
                        self.columns[current].append(c.group(1))
                        continue
                    if line.startswith(")"):
                        current = None
                        continue
                m = _INSERT.match(line)
                if m:
                    if not line.rstrip().endswith(";"):
                        pending = line
                        continue
                    table = m.group(1)
                    if m.group(3):
                        self.columns[table] = [c.strip().strip("`") for c in m.group(3).split(",")]
                    self.rows.setdefault(table, []).extend(_parse_values(line, m.end(), line_no))
        if not self.columns:
            raise DumpError("This doesn't look like a database backup (no tables found).")

    def has(self, table: str) -> bool:
        return table in self.columns

    def read(self, table: str, order: str) -> list[dict]:
        cols = self.columns.get(table)
        if not cols:
            return []
        out = []
        for r in self.rows.get(table, []):
            if len(r) != len(cols):
                raise DumpError(f"Table {table}: a row has {len(r)} values but the table has {len(cols)} columns.")
            out.append(dict(zip(cols, r)))
        if order in cols:
            out.sort(key=lambda d: (d[order] is None, d[order] if not isinstance(d[order], bytes) else b""))
        return out

    def summary(self) -> dict:
        return {t: len(r) for t, r in self.rows.items()}
