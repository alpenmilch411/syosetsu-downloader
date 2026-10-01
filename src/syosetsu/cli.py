"""syosetsu command-line interface."""
import argparse
import sys
from datetime import date
from pathlib import Path

from . import api
from .client import Client, FetchError
from .epub import build_epub
from .export_txt import export_txt
from .fetch import fetch_novel
from .parse import LayoutError
from .rank import GENRES, rank, read_list, write_list
from .store import Store


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="syosetsu", description="Polite Syosetu downloader")
    p.add_argument("--data", default="data", help="data directory (default: ./data)")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="download / update novels")
    f.add_argument("target", nargs="?", help="ncode or ncode.syosetu.com URL")
    f.add_argument("--list", dest="list_file", help="list file (TSV, first column ncode)")
    f.add_argument("--from", dest="frm", type=int)
    f.add_argument("--to", type=int)
    f.add_argument("--refresh", action="store_true", help="re-download chapters revised on the site")
    f.add_argument("--export", choices=["txt", "epub", "both"])
    f.add_argument("--interval", type=float, default=1.5, help="seconds between requests (default 1.5)")

    e = sub.add_parser("export", help="export a downloaded novel")
    esub = e.add_subparsers(dest="fmt", required=True)
    et = esub.add_parser("txt")
    et.add_argument("ncode")
    et.add_argument("--with-notes", action="store_true")
    ee = esub.add_parser("epub")
    ee.add_argument("ncode")
    ee.add_argument("--vertical", action="store_true")
    ee.add_argument("--with-notes", action="store_true")
    ee.add_argument("--out")

    g = sub.add_parser("get", help="fetch + optionally build the EPUB")
    g.add_argument("target")
    g.add_argument("--epub", action="store_true")
    g.add_argument("--vertical", action="store_true")
    g.add_argument("--interval", type=float, default=1.5, help="seconds between requests (default 1.5)")

    sub.add_parser("list", help="show downloaded novels")

    r = sub.add_parser("rank", help="build a download list from the rankings")
    r.add_argument("--genre", type=int, action="append", choices=sorted(GENRES))
    r.add_argument("--top", type=int, default=10)
    r.add_argument("--status", choices=["completed", "all"], default="completed")
    r.add_argument("--order", default="hyoka")
    r.add_argument("--out", default=f"lists/top-{date.today().isoformat()}.tsv")
    return p


def _client(interval: float = 1.5) -> Client:
    if interval < 0.5:
        raise ValueError("--interval below 0.5 s is too aggressive for Syosetu")
    return Client(min_interval=interval, log=lambda msg: print(f"  {msg}", file=sys.stderr, flush=True))


def _export(store, ncode, which, vertical=False):
    if which in ("txt", "both"):
        n, r = export_txt(store, ncode)
        print(f"  txt: {n} chapters, {r} ruby → {store.novel_dir(ncode) / 'plain'}")
    if which in ("epub", "both"):
        print(f"  epub: {build_epub(store, ncode, vertical=vertical)}")


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    store = Store(Path(args.data))
    try:
        if args.cmd == "fetch":
            if bool(args.target) == bool(args.list_file):
                print("error: give either a target or --list", file=sys.stderr)
                return 2
            targets = read_list(args.list_file) if args.list_file else [api.normalize_ncode(args.target)]
            client, failures = _client(args.interval), []
            for i, target in enumerate(targets, 1):
                print(f"== [{i}/{len(targets)}] {target}")
                try:
                    ncode = api.normalize_ncode(target)
                    res = fetch_novel(client, store, ncode, frm=args.frm, to=args.to, refresh=args.refresh)
                    print(f"  {res.title}: {res.fetched} fetched, {res.skipped} already present, {res.total} total")
                    if args.export:
                        _export(store, ncode, args.export)
                except (FetchError, LayoutError, ValueError) as e:
                    failures.append(target)
                    print(f"  FAILED {target}: {e}", file=sys.stderr)
            if failures:
                print(f"{len(failures)} failed: {' '.join(failures)}", file=sys.stderr)
                return 1
            return 0
        if args.cmd == "export":
            ncode = api.normalize_ncode(args.ncode)
            if args.fmt == "txt":
                n, r = export_txt(store, ncode, with_notes=args.with_notes)
                print(f"{n} chapters, {r} ruby records → {store.novel_dir(ncode)}")
            else:
                print(build_epub(store, ncode, out=args.out, vertical=args.vertical, with_notes=args.with_notes))
            return 0
        if args.cmd == "get":
            ncode = api.normalize_ncode(args.target)
            res = fetch_novel(_client(args.interval), store, ncode)
            print(f"{res.title}: {res.fetched} fetched, {res.skipped} already present")
            if args.epub:
                print(build_epub(store, ncode, vertical=args.vertical))
            return 0
        if args.cmd == "list":
            for ncode in store.novels():
                meta = store.load_meta(ncode)
                print(f"{ncode}\t{len(store.chapter_numbers(ncode))}/{meta.get('chapter_count', '?')}\t{meta.get('title', '')}")
            return 0
        if args.cmd == "rank":
            rows = rank(Client(), genres=args.genre, top=args.top, status=args.status, order=args.order)
            write_list(rows, Path(args.out), f"top {args.top} {args.status} per genre by {args.order}, {date.today()}")
            print(f"{len(rows)} novels → {args.out}")
            return 0
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except (FetchError, LayoutError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
