"""
Compile .po -> .mo translation files without GNU gettext (pure Python).

Usage:
    python scripts/compile_mo.py [locale_dir]

Default locale_dir = <project root>/locale
"""
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_po(path: Path):
    """Minimal .po parser: returns dict {msgid: msgstr}."""
    entries = {}
    msgid = msgstr = None
    state = None  # 'id' | 'str'

    def unquote(line: str) -> str:
        s = line.strip()
        if s.startswith("msgid "):
            s = s[6:]
        elif s.startswith("msgstr "):
            s = s[7:]
        s = s.strip()
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            s = s[1:-1]
        return s.encode("utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8")

    for raw in io.open(path, encoding="utf-8").read().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("msgid "):
            if msgid is not None and msgstr is not None:
                entries[msgid] = msgstr
            msgid, msgstr, state = unquote(line), None, "id"
        elif line.startswith("msgstr "):
            msgstr, state = unquote(line), "str"
        elif line.startswith('"'):
            value = unquote(line)
            if state == "id":
                msgid += value
            elif state == "str":
                msgstr += value
    if msgid is not None and msgstr is not None:
        entries[msgid] = msgstr
    return entries


def write_mo(path: Path, entries: dict):
    import struct

    keys = sorted(entries)
    offsets = []
    ids = b""
    strs = b""
    for k in keys:
        v = entries[k]
        kb, vb = k.encode("utf-8"), v.encode("utf-8")
        offsets.append((len(ids), len(kb), len(strs), len(vb)))
        ids += kb + b"\x00"
        strs += vb + b"\x00"

    n = len(keys)
    keystart = 7 * 4 + 16 * n
    valuestart = keystart + len(ids)
    koffsets = []
    voffsets = []
    for o1, l1, o2, l2 in offsets:
        koffsets += [l1, o1 + keystart]
        voffsets += [l2, o2 + valuestart]
    output = struct.pack("Iiiiiii", 0x950412DE, 0, n, 7 * 4, 7 * 4 + n * 8, 0, 0)
    output += struct.pack("i" * len(koffsets), *koffsets)
    output += struct.pack("i" * len(voffsets), *voffsets)
    output += ids + strs
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(output)


def main():
    locale_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "locale"
    for po in sorted(locale_dir.glob("*/LC_MESSAGES/django.po")):
        mo = po.with_suffix(".mo")
        entries = parse_po(po)
        write_mo(mo, entries)
        print(f"{po.relative_to(locale_dir)} -> {mo.name} ({len(entries)} strings)")


if __name__ == "__main__":
    main()
