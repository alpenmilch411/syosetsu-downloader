<p align="center">
  <img src="assets/syosetsu-mark.svg" width="120" alt="syosetsu-downloader logo">
</p>

<h1 align="center">syosetsu-downloader</h1>

<p align="center">
  <strong>Download Japanese web novels from 小説家になろう chapter by chapter — as clean text with furigana, or as a good-looking EPUB.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-%233670A0.svg?style=for-the-badge&logo=python&logoColor=ffdd54" alt="Python">
  <img src="https://img.shields.io/badge/uv-%23DE5FE9.svg?style=for-the-badge&logo=uv&logoColor=white" alt="uv">
  <img src="https://img.shields.io/badge/pytest-%23ffffff.svg?style=for-the-badge&logo=pytest&logoColor=2f9fe3" alt="Pytest">
  <img src="https://img.shields.io/github/license/alpenmilch411/syosetsu-downloader?style=for-the-badge" alt="License">
</p>

`syosetsu` is a small command-line tool for [小説家になろう](https://syosetu.com/) (`ncode.syosetu.com`). It downloads a novel chapter by chapter into a local store, and exports it as:

- **plain text** for reading practice, language tools or text analysis — with the author's furigana kept in a separate, machine-readable form, and
- **EPUB 3** for your e-reader — with a generated cover, a nested table of contents and real `<ruby>` furigana.

It is deliberately **polite**: one request at a time, a pause between requests, and automatic back-off when the site asks for it. Downloads are **resumable** — stop it at any time and run the same command again.

> [!NOTE]
> Novels on 小説家になろう are their authors' copyright, and the site's terms do not allow redistributing them. This tool is meant for **personal use**: keep what you download on your own machine.

## Features

- Serials and short stories, any `ncode` or `ncode.syosetu.com` URL
- Resumable and incremental — only missing chapters are fetched; `--refresh` re-fetches chapters the author revised (改稿)
- Arc / volume headings (章) are kept and become the EPUB's table of contents
- Furigana preserved losslessly as `｜漢字《かんじ》`, plus a JSONL file with every reading and its exact position in the plain text
- EPUB 3 with horizontal (default) or vertical 縦書き layout, JPEG cover with a vertical Mincho title, nav + NCX table of contents
- Ranking lists: build a download list of the top novels per genre from the official API, then fetch the whole list in one resumable run
- Atomic writes — an interrupted run never leaves a half-written chapter

## Installation

Requires Python ≥ 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/alpenmilch411/syosetsu-downloader.git
cd syosetsu-downloader
uv sync
```

## Quick start

```bash
# download a novel and build an EPUB
uv run syosetsu get n9669bk --epub

# same thing with a URL
uv run syosetsu get https://ncode.syosetu.com/n9669bk/ --epub
```

The EPUB is written to `data/<ncode>/<title>.epub`.

## Commands

| Command | What it does |
|:---|:---|
| `syosetsu get <ncode\|url> [--epub] [--vertical]` | Fetch (or update) a novel, optionally build the EPUB |
| `syosetsu fetch <ncode\|url> [--from N] [--to M] [--refresh]` | Fetch a novel or a chapter range |
| `syosetsu fetch --list FILE [--export txt\|epub\|both]` | Fetch every novel in a list file, exporting each one as soon as it is complete |
| `syosetsu export txt <ncode> [--with-notes]` | Write the text exports (see below) |
| `syosetsu export epub <ncode> [--vertical] [--with-notes] [--out PATH]` | Build the EPUB |
| `syosetsu rank [--genre G ...] [--top N] [--status completed\|all] [--out FILE]` | Build a list file from the official ranking API (default: top 10 completed novels in each of the 20 genres) |
| `syosetsu list` | Show downloaded novels with chapters stored / total |

Global options: `--data DIR` (default `./data`). `fetch` and `get` accept `--interval SECONDS` (default `1.5`, minimum `0.5`).

`--with-notes` includes the author's prefaces and afterwords (前書き / 後書き), which are left out by default.

### Downloading many novels

```bash
uv run syosetsu rank --top 10 --out lists/top10.tsv          # 200 novels, all genres
uv run syosetsu fetch --list lists/top10.tsv --export txt     # resumable; failures are listed at the end
uv run syosetsu fetch --list lists/top10.tsv --to 30          # only the first 30 chapters of each
```

A list file is a TSV whose first column is the ncode; lines starting with `#` are comments. Large lists take hours at the default pace — the tool is meant to run in the background, and a re-run continues where it stopped. Every retry is logged, so you can see if the site starts throttling.

## Output

```
data/<ncode>/
  meta.json              title, author, genre, synopsis, arcs, chapter list with update dates
  chapters/0001.txt      canonical store: line 1 title, line 2 blank, then one line per paragraph
  notes/0001.preface.txt / 0001.afterword.txt
  plain/0001.txt         text export: furigana removed
  ruby/0001.txt          text export: same lines, furigana inline as ｜漢字《かんじ》
  ruby.jsonl             one record per furigana (see below)
  <title>.epub
```

`plain/` and `ruby/` are line-aligned. Each `ruby.jsonl` record points into `plain/`:

```json
{"ch": 1, "line": 12, "start": 5, "end": 7, "base": "東京", "reading": "とうきょう", "kind": "reading"}
```

`line` is 1-based, `start`/`end` are code-point offsets (end exclusive), so `plain_line[start:end] == base`. `kind` is:

| kind | meaning |
|:---|:---|
| `reading` | kanji base with an all-hiragana reading — most likely a real reading |
| `emphasis` | emphasis dots (傍点) |
| `gloss` | everything else: katakana or creative readings (`魔法《マジック》`), Latin text, … |

Authors use furigana freely, so `reading` means "looks like a reading", not "verified reading" — a creative reading written in hiragana still lands there.

### EPUB layout: horizontal or vertical

EPUBs are **horizontal** by default (left-to-right, like a western book). Add `--vertical` for traditional Japanese **縦書き** (top-to-bottom, right-to-left page turns):

```bash
uv run syosetsu get n9669bk --epub               # horizontal (default)
uv run syosetsu get n9669bk --epub --vertical    # vertical 縦書き

# switch an already downloaded novel — no re-download needed
uv run syosetsu export epub n9669bk --vertical
uv run syosetsu export epub n9669bk --vertical --out ~/Books/mushoku-tate.epub
```

Both layouts render furigana as real `<ruby>`; in vertical mode two-digit numbers are set upright (縦中横).

### Covers

Every EPUB gets a cover: the title set vertically in Mincho over a genre-tinted background. To use your own illustration, put a portrait image at `data/<ncode>/art.png` and export again — the title is laid over it. The cover font is found automatically on macOS (Hiragino Mincho) and Linux (Noto Serif CJK); set `SYOSETSU_COVER_FONT=/path/to/font` to use another one.

## Development

```bash
uv run pytest            # offline test suite (hand-written HTML fixtures, no real novel text)
uv run pytest -m live    # one smoke test against the real site (fetches 2 chapters)
```

If [epubcheck](https://github.com/w3c/epubcheck) is installed, the EPUB test also validates the output with it.

## License

[MIT](LICENSE)
