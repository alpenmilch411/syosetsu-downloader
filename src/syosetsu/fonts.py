"""Cover fonts: open-licensed (SIL OFL) Japanese fonts from Google Fonts, downloaded once into a user cache."""
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import httpx

BASE_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
# name → (Google Fonts directory, regular file, bold file or None for a variable font)
FONTS = {
    "mincho": ("notoserifjp", "NotoSerifJP[wght].ttf", None),
    "gothic": ("notosansjp", "NotoSansJP[wght].ttf", None),
    "shippori": ("shipporimincho", "ShipporiMincho-Regular.ttf", "ShipporiMincho-Bold.ttf"),
    "oldmincho": ("zenoldmincho", "ZenOldMincho-Regular.ttf", "ZenOldMincho-Bold.ttf"),
    "maru": ("zenmarugothic", "ZenMaruGothic-Regular.ttf", "ZenMaruGothic-Bold.ttf"),
    "decol": ("kaiseidecol", "KaiseiDecol-Regular.ttf", "KaiseiDecol-Bold.ttf"),
}
SYSTEM_FONTS = [
    "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc",                    # macOS
    "/System/Library/Fonts/Hiragino Mincho ProN.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",      # Debian/Ubuntu
    "/usr/share/fonts/noto-cjk/NotoSerifCJK-Regular.ttc",           # Arch/Fedora
    r"C:\Windows\Fonts\yumin.ttf",                                   # Windows
    r"C:\Windows\Fonts\msmincho.ttc",
]


@dataclass(frozen=True)
class FontSpec:
    regular: str
    bold: str
    variable: bool = False


def default_cache_dir() -> Path:
    if os.environ.get("SYOSETSU_CACHE_DIR"):
        return Path(os.environ["SYOSETSU_CACHE_DIR"]) / "fonts"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "syosetsu" / "fonts"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "syosetsu" / "fonts"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "syosetsu" / "fonts"


def find_system_font() -> str | None:
    env = os.environ.get("SYOSETSU_COVER_FONT")
    for p in ([env] if env else []) + SYSTEM_FONTS:
        if p and Path(p).is_file():
            return p
    return None


def _download(url: str, dest: Path) -> None:
    r = httpx.get(url, follow_redirects=True, timeout=120)
    r.raise_for_status()
    dest.write_bytes(r.content)


def resolve_font(spec: str, cache_dir: Path | None = None, download=None) -> FontSpec | None:
    """A font name from FONTS (downloaded on first use) or a path to a font file.
    Falls back to an installed system font when the download fails; None if there is no font at all."""
    path = Path(spec).expanduser()
    if path.is_file():
        return FontSpec(str(path), str(path), variable=False)
    if spec not in FONTS:
        raise ValueError(f"unknown cover font {spec!r}: use one of {', '.join(FONTS)} or a path to a .ttf/.otf/.ttc file")
    download = download or _download
    directory, regular, bold = FONTS[spec]
    target = (cache_dir or default_cache_dir()) / spec
    target.mkdir(parents=True, exist_ok=True)
    try:
        for name in [regular] + ([bold] if bold else []) + ["OFL.txt"]:
            dest = target / name
            if dest.exists():
                continue
            part = dest.with_name(dest.name + ".part")
            try:
                download(BASE_URL + directory + "/" + quote(name), part)
                part.replace(dest)
            finally:
                part.unlink(missing_ok=True)
    except Exception as e:  # offline, GitHub down, …
        system = find_system_font()
        print(f"warning: could not download cover font {spec!r} ({e}); "
              + (f"using {system}" if system else "building without a cover"), file=sys.stderr)
        return FontSpec(system, system, False) if system else None
    if bold is None:
        return FontSpec(str(target / regular), str(target / regular), variable=True)
    return FontSpec(str(target / regular), str(target / bold), variable=False)
