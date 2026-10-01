"""On-disk layout: data/<ncode>/{meta.json, chapters/NNNN.txt, notes/NNNN.{preface,afterword}.txt}."""
import json
import os
from pathlib import Path


def atomic_write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if isinstance(data, str):
        tmp.write_text(data, encoding="utf-8")
    else:
        tmp.write_bytes(data)
    os.replace(tmp, path)


def _join(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


def _split(text: str) -> list[str]:
    return text.removesuffix("\n").split("\n")


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)

    def novel_dir(self, ncode: str) -> Path:
        return self.root / ncode

    def _meta_path(self, ncode: str) -> Path:
        return self.novel_dir(ncode) / "meta.json"

    def load_meta(self, ncode: str) -> dict | None:
        p = self._meta_path(ncode)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def save_meta(self, ncode: str, meta: dict) -> None:
        atomic_write(self._meta_path(ncode), json.dumps(meta, ensure_ascii=False, indent=1))

    def chapter_path(self, ncode: str, n: int) -> Path:
        return self.novel_dir(ncode) / "chapters" / f"{n:04d}.txt"

    def _note_path(self, ncode: str, n: int, kind: str) -> Path:
        return self.novel_dir(ncode) / "notes" / f"{n:04d}.{kind}.txt"

    def has_chapter(self, ncode: str, n: int) -> bool:
        return self.chapter_path(ncode, n).exists()

    def write_chapter(self, ncode, n, title, body, preface=(), afterword=()) -> None:
        for kind, lines in (("preface", preface), ("afterword", afterword)):
            p = self._note_path(ncode, n, kind)
            if lines:
                atomic_write(p, _join(list(lines)))
            elif p.exists():
                p.unlink()
        atomic_write(self.chapter_path(ncode, n), _join([title, ""] + list(body)))

    def read_chapter(self, ncode: str, n: int) -> tuple[str, list[str]]:
        lines = _split(self.chapter_path(ncode, n).read_text(encoding="utf-8"))
        return lines[0], lines[2:]

    def read_notes(self, ncode: str, n: int) -> tuple[list[str], list[str]]:
        out = []
        for kind in ("preface", "afterword"):
            p = self._note_path(ncode, n, kind)
            out.append(_split(p.read_text(encoding="utf-8")) if p.exists() else [])
        return out[0], out[1]

    def chapter_numbers(self, ncode: str) -> list[int]:
        d = self.novel_dir(ncode) / "chapters"
        return sorted(int(p.stem) for p in d.glob("*.txt")) if d.exists() else []

    def novels(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(p.parent.name for p in self.root.glob("*/meta.json"))
