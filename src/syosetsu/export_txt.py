"""Training export: plain/ (ruby stripped), ruby/ (Aozora notation), ruby.jsonl (offsets into plain/)."""
import json

from . import aozora
from .store import Store, atomic_write


def chapter_lines(store: Store, ncode: str, n: int, with_notes: bool = False) -> list[str]:
    title, body = store.read_chapter(ncode, n)
    lines = [title, ""]
    if with_notes:
        preface, afterword = store.read_notes(ncode, n)
        lines += (preface + [""] if preface else []) + body + ([""] + afterword if afterword else [])
    else:
        lines += body
    return lines


def export_txt(store: Store, ncode: str, with_notes: bool = False) -> tuple[int, int]:
    d = store.novel_dir(ncode)
    records, count = [], 0
    for n in store.chapter_numbers(ncode):
        ruby_lines = chapter_lines(store, ncode, n, with_notes)
        plain_lines = [aozora.strip(l) for l in ruby_lines]
        for i, line in enumerate(ruby_lines, start=1):
            for s in aozora.spans(line):
                records.append({"ch": n, "line": i, "start": s.start, "end": s.end, "base": s.base,
                                "reading": s.reading, "kind": aozora.classify(s.base, s.reading)})
        atomic_write(d / "plain" / f"{n:04d}.txt", "\n".join(plain_lines) + "\n")
        atomic_write(d / "ruby" / f"{n:04d}.txt", "\n".join(ruby_lines) + "\n")
        count += 1
    atomic_write(d / "ruby.jsonl", "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    return count, len(records)
