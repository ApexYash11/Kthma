import json
import pathlib
import re
import urllib.parse

html = pathlib.Path(r"C:\Users\ACER\AppData\Local\Temp\testcards.html").read_text(
    encoding="utf-8", errors="ignore"
)
m = re.search(r'"compiled":"(.*?)"(?:,")', html)
print("compiled match", bool(m), "len", len(m.group(1)) if m else 0)
if not m:
    raise SystemExit(1)
raw = m.group(1)
compiled = bytes(raw, "utf-8").decode("unicode_escape")
compiled2 = urllib.parse.unquote(compiled)
print("compiled2 len", len(compiled2))
cards = re.findall(r"(?:\d{4}[\s-]?){3}\d{3,4}", compiled2)
print("cards", len(cards))
for c in dict.fromkeys(cards):
    print("CARD", c)
out = pathlib.Path(r"D:\Kthma\.scratch\testcards_compiled.txt")
out.write_text(compiled2, encoding="utf-8")
print("wrote", out, "chars", len(compiled2))
