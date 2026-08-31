"""
Update Django locale files (vi / en / kr) without GNU gettext tools.

1. Extracts all `_()` msgids from apps/, libs/, services/ (skips migrations).
2. Merges with existing .po translations.
3. Fills new entries from TRANSLATIONS table (part 1 file + part 2 file).
4. Writes .po and compiles .mo (pure-Python msgfmt).

Usage: python scripts/update_locales.py
"""
import os
import re
import struct
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LOCALE = BASE / "locale"
LANGS = ["vi", "en", "kr"]
SCAN_DIRS = ["apps", "libs", "services"]
SKIP = ("migrations", ".venv")

from scripts.translations_table import TRANSLATIONS


import ast


def extract_msgids():
    """Find all _('...') msgids in python sources.

    Uses ast parsing so multi-line implicit string concatenation
    ( "part1 " "part2" ) is folded into one msgid correctly.
    """
    msgids = set()

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id == "_":
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    msgids.add(node.args[0].value)
            self.generic_visit(node)

    for scan in SCAN_DIRS:
        for root, dirs, files in os.walk(BASE / scan):
            if any(s in root for s in SKIP):
                continue
            for f in files:
                if not f.endswith(".py"):
                    continue
                try:
                    tree = ast.parse((Path(root) / f).read_text(encoding="utf-8", errors="ignore"))
                    Visitor().visit(tree)
                except SyntaxError:
                    continue
    return sorted(msgids)


def parse_existing_po(path):
    """Parse an existing .po into {msgid: msgstr}."""
    result = {}
    if not path.exists():
        return result
    msgid = msgstr = None
    key = None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("msgid "):
            key, msgid = "id", _unquote(line[6:])
        elif line.startswith("msgstr "):
            key, msgstr = "str", _unquote(line[7:])
        elif line.startswith('"') and key:
            val = _unquote(line)
            if key == "id":
                msgid += val
            else:
                msgstr += val
        elif not line and msgid is not None:
            result[msgid] = msgstr or ""
            msgid = msgstr = key = None
    if msgid is not None:
        result[msgid] = msgstr or ""
    return result


def _unquote(s):
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1].replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")
    return s


def _quote(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def build_po(lang, entries):
    lines = [
        'msgid ""',
        'msgstr ""',
        '"Project-Id-Version: Django API Server\\n"',
        '"PO-Revision-Date: 2026\\n"',
        f'"Language: {lang}\\n"',
        '"MIME-Version: 1.0\\n"',
        '"Content-Type: text/plain; charset=UTF-8\\n"',
        '"Content-Transfer-Encoding: 8bit\\n"',
        '"Plural-Forms: nplurals=1; plural=0;\\n"',
        "",
    ]
    for msgid, msgstr in entries:
        lines.append(f"msgid {_quote(msgid)}")
        lines.append(f"msgstr {_quote(msgstr)}")
        lines.append("")
    return "\n".join(lines)


def compile_mo(entries):
    """Minimal GNU .mo writer (pure Python, no msgfmt needed)."""
    catalog = {m: s for m, s in entries if s}
    # Required meta entry so gettext detects UTF-8 charset
    catalog[""] = (
        "Project-Id-Version: Django API Server\n"
        "Content-Type: text/plain; charset=UTF-8\n"
        "Content-Transfer-Encoding: 8bit\n"
        "Plural-Forms: nplurals=1; plural=0;\n"
    )
    keys = sorted(catalog)
    # Skip the meta entry when writing .po is handled by build_po; here it's fine.
    n = len(keys)
    # Header(28) + orig table(8n) + trans table(8n) + msgid strings + msgstr strings
    orig_table_off = 28
    trans_table_off = orig_table_off + 8 * n
    msgid_off = trans_table_off + 8 * n
    # Pass 1: byte sizes to compute msgstr block start
    idb = {k: k.encode("utf-8") for k in keys}
    vbt = {k: catalog[k].encode("utf-8") for k in keys}
    msgstr_off = msgid_off + sum(len(b) + 1 for b in idb.values())
    # Pass 2: build offset tables
    koffsets, voffsets = [], []
    o1 = o2 = 0
    for k in keys:
        koffsets += [len(idb[k]), msgid_off + o1]
        voffsets += [len(vbt[k]), msgstr_off + o2]
        o1 += len(idb[k]) + 1
        o2 += len(vbt[k]) + 1
    output = struct.pack("Iiiiiii", 0x950412DE, 0, n, orig_table_off, trans_table_off, 0, 0)
    output += struct.pack(f"{4 * n}I", *(koffsets + voffsets))
    for k in keys:
        output += idb[k] + b"\x00"
    for k in keys:
        output += vbt[k] + b"\x00"
    return output


def main():
    msgids = extract_msgids()
    print(f"Extracted {len(msgids)} msgids from source")
    for lang in LANGS:
        po_path = LOCALE / lang / "LC_MESSAGES" / "django.po"
        existing = parse_existing_po(po_path)
        entries = []
        missing = []
        for msgid in msgids:
            if lang == "en":
                msgstr = msgid  # English = source language
            elif msgid in existing and existing[msgid]:
                msgstr = existing[msgid]
            else:
                msgstr = TRANSLATIONS.get(msgid, {}).get(lang, "")
                if not msgstr:
                    missing.append(msgid)
            entries.append((msgid, msgstr))
        po_path.parent.mkdir(parents=True, exist_ok=True)
        po_path.write_text(build_po(lang, entries), encoding="utf-8")
        mo_path = po_path.with_suffix(".mo")
        mo_path.write_bytes(compile_mo(entries))
        print(f"[{lang}] {len(entries)} entries -> django.po + django.mo; untranslated: {len(missing)}")
        for m in missing:
            print(f"    MISSING: {m!r}")


if __name__ == "__main__":
    main()

