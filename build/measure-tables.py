#!/usr/bin/python3
"""Build the machine page's tables from measured files, or refuse a stale page with --check."""

import argparse
import html
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = "<!-- measures:start -->"
END = "<!-- measures:end -->"
SIZES_START = "<!-- sizes:start -->"
SIZES_END = "<!-- sizes:end -->"


SERVICES = ("porelo-forge", "porelo-runner", "porelo-matrix")


def cell(value):
    """Keep labels and reasons inside their own Markdown table cell."""
    return html.escape(str(value)).replace("|", "&#124;").replace("\n", " ").replace("\r", " ")


def shown(row, unit=None):
    """One value as it stands in its file, in the page's unit; an absent one says so."""
    if row is None:
        return "not measured"
    value = row["value"]
    if value is None:
        return "not measured: " + row["why"]
    if unit == "MiB":
        return f"{value // 1024**2} MiB"
    if unit == "GiB":
        return f"{value / 1024**3:.1f} GiB"
    if unit == "s":
        return f"{round(value)} s"
    if isinstance(value, list):
        return ", ".join(value) if value else "none"
    return str(value)


def service(row):
    """An account's memory, or a dash where the shape has no such account."""
    return "-" if row is None else shown(row, "MiB")


def read(path):
    """The facts of one result file, refused where the file is not one this page knows."""
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("v") != 1 or isinstance(report["v"], bool) or not isinstance(report.get("facts"), list):
        raise ValueError(f"unsupported result schema in {path.name}")
    if not report["facts"]:
        raise ValueError(f"no facts in {path.name}")
    for row in report["facts"]:
        if not isinstance(row, dict) or not {"field", "value", "unit", "step"} <= row.keys():
            raise ValueError(f"incomplete fact in {path.name}")
        if row["value"] is None and not (isinstance(row.get("why"), str) and row["why"]):
            raise ValueError(f"absent value without a reason in {path.name}")
        if type(row["value"]) in (int, float) and (not math.isfinite(row["value"]) or row["value"] < 0):
            raise ValueError(f"invalid fact value in {path.name}")
    return report["facts"]


def machine_table(path):
    """One machine: what it is, each reading of each shape, what the run left and what it did not measure."""
    facts = read(path)

    def one(field, step, sample=None, subject=None):
        for row in facts:
            if (row["field"], row["step"], row.get("sample"), row.get("subject")) == (field, step, sample, subject):
                return row
        return None

    def named(field):
        row = one(field, "machine")
        return shown(row) if row and row["value"] is not None else "not known"

    memory = one("memory.total", "machine")
    lines = [
        f"### {path.stem}",
        "",
        f"{named('provider')} {named('offer')}: {named('cpu.count')} CPUs of {named('cpu.model')}, "
        f"{shown(memory, 'MiB')}, {named('system')}, `/dev/kvm` answers: {named('kvm')}; "
        f"collection {named('collection.version')}, from {named('distribution')}.",
        "",
        "| Shape | Reading | `up` took | In use | With page cache | Forge's account | Runner's account "
        "| Homeserver's account | Disk used at `/` |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for shape in ("before", "none", "room", "forge", "both"):
        step = "before" if shape == "before" else f"idle.{shape}"
        for sample in ("first", "second", "third"):
            taken = one("up.time", step, sample)
            if shape != "before" and taken is None and one("memory.anon", step, sample, "host") is None:
                continue
            if taken is not None and taken["value"] is None:
                lines.append(f"| {shape} | {sample} | {cell(shown(taken))} | | | | | | |")
                continue
            columns = [
                shape,
                sample,
                "" if shape == "before" else shown(taken, "s"),
                shown(one("memory.anon", step, sample, "host"), "MiB"),
                shown(one("memory.current", step, sample, "host"), "MiB"),
                *(service(one("memory.anon", step, sample, s)) for s in SERVICES),
                shown(one("disk.used", step, sample, "/"), "GiB"),
            ]
            lines.append("| " + " | ".join(cell(column) for column in columns) + " |")
    left = [(row["field"].removeprefix("changes."), row) for row in facts if row["field"].startswith("changes.")]
    left = [f"{name}: {cell(shown(row))}" for name, row in left if row["value"] != []]
    lines += ["", "What the run left: " + ("; ".join(left) if left else "nothing it could name") + "."]
    absent = sorted({row["step"] for row in facts if row["step"] in ("task", "agent", "job") and row["value"] is None})
    if absent:
        lines += ["", "Not measured: " + ", ".join(absent) + "."]
    return "\n".join(lines) + "\n"


def tables(directory):
    """Each machine's own table, with every reading; no figure a run did not read."""
    files = sorted(directory.glob("*.json"))
    if not files:
        return "Nothing is measured until a result file exists under `doc/measures/`.\n"
    return "\n".join(machine_table(path) for path in files)


def ranged(held, rows, form):
    """What the readings hold, smallest to largest, how many of three if not all; with none, why."""
    if not held:
        return shown(rows[0]) if rows else "not measured"
    values = [form(row["value"]) for row in held]
    unit = "MiB" if isinstance(values[0], int) else "GiB"

    def text(value):
        return str(value) if unit == "MiB" else f"{value:.1f}"

    told = (
        text(min(values)) if text(min(values)) == text(max(values)) else f"{text(min(values))} to {text(max(values))}"
    )
    return f"{told} {unit}" + (f", {len(held)} of 3 readings" if len(held) < 3 else "")


def summary(directory):
    """Each machine's in-use range by shape, saying how many readings hold it; what no reading holds says so."""
    files = sorted(directory.glob("*.json"))
    if not files:
        return "Nothing is measured until a result file exists under `doc/measures/`.\n"
    lines = [
        "| Machine | Its memory | Shape | In use, idle | Disk used at `/`, idle |",
        "| --- | --- | --- | --- | --- |",
    ]
    for path in files:
        facts = read(path)
        total = next((r for r in facts if r["field"] == "memory.total" and r["step"] == "machine"), None)
        for shape in ("none", "room", "forge", "both"):

            def told(field, subject, form):
                rows = [
                    row
                    for row in facts
                    if row["step"] == f"idle.{shape}" and row["field"] == field and row.get("subject") == subject
                ]
                return ranged([row for row in rows if row["value"] is not None], rows, form)

            columns = [
                path.stem,
                shown(total, "MiB"),
                f"`{shape}`",
                told("memory.anon", "host", lambda v: v // 1024**2),
                told("disk.used", "/", lambda v: v / 1024**3),
            ]
            lines.append("| " + " | ".join(cell(column) for column in columns) + " |")
    return "\n".join(lines) + "\n"


def block(text, start, end, content):
    """Replace one marked block, refusing a page without its one ordered pair."""
    if text.count(start) != 1 or text.count(end) != 1 or text.index(end) < text.index(start):
        raise ValueError("the machine page needs one ordered pair of measure markers")
    before, rest = text.split(start)
    return before + start + "\n\n" + content + "\n" + end + rest.split(end)[1]


def main(arguments=None, directory=None, page=None):
    """Replace only the marked block, or compare without writing."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    options = parser.parse_args(arguments)
    directory = directory if directory is not None else ROOT / "doc/measures"
    page = page if page is not None else ROOT / "doc/machines.md"
    original = page.read_text(encoding="utf-8")
    wanted = block(original, START, END, tables(directory))
    if SIZES_START in original:
        wanted = block(wanted, SIZES_START, SIZES_END, summary(directory))
    if options.check:
        if original != wanted:
            print("machine tables differ from result files; run python3 build/measure-tables.py", file=sys.stderr)
            return 1
    else:
        page.write_text(wanted, encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"cannot build machine tables: {error}", file=sys.stderr)
        sys.exit(2)
