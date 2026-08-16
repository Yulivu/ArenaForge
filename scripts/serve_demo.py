"""Serve the built ArenaForge site with explicit UTF-8 content types."""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class UTF8RequestHandler(SimpleHTTPRequestHandler):
    """Add an explicit charset for text assets in local previews."""

    def guess_type(self, path: str) -> str:
        suffix = Path(path).suffix.lower()
        types = {
            ".css": "text/css; charset=utf-8",
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml; charset=utf-8",
        }
        return types.get(suffix, super().guess_type(path))


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the built ArenaForge site.")
    parser.add_argument("--directory", type=Path, default=Path("web/dist"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8773)
    args = parser.parse_args()

    directory = args.directory.resolve()
    handler = partial(UTF8RequestHandler, directory=str(directory))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving {directory} at http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
