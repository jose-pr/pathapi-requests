"""uripath-http-requests benchmark runner.

Times the built-in transport of `uripath` and this one on the same requests
against an in-process loopback server. Run `python benchmarks/bench.py --help`
for the options. `--save` writes the run as JSON into `benchmarks/results/`;
the schema is in `benchmarks/README.md`.
"""

from __future__ import annotations

import argparse
import datetime
import http.server
import json
import os
import platform
import statistics
import subprocess
import sys
import sysconfig
import threading
import timeit
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

SCHEMA = "uripath-http-requests.bench/1"
BODY = b"x" * 1024
LARGE = b"y" * (1 << 20)


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        data = LARGE if self.path.startswith("/large") else BODY
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_PUT(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()


def _cases(url, samples):
    from uripath import transports
    from uripath.schemes import HTTPURIPath

    results = {}
    for name in ("builtin", "requests"):
        transport = transports.get(name)()
        try:
            root = HTTPURIPath(url).with_transport(transport)
            small, large = root / "small.bin", root / "large.bin"
            small.read_bytes()
            cases = {
                "50 GETs of a 1 KiB file": (
                    lambda: [small.read_bytes() for _ in range(50)],
                    50,
                ),
                "1 GET of a 1 MiB file": (large.read_bytes, 1),
                "20 PUTs of 1 KiB": (
                    lambda: [small.write_bytes(BODY) for _ in range(20)],
                    20,
                ),
            }
            for label, (run, calls) in cases.items():
                taken = timeit.repeat(run, number=1, repeat=samples)
                per_call = sorted(t / calls * 1000.0 for t in taken)
                results[f"{label}, {name} transport"] = {
                    "min_ms": round(per_call[0], 6),
                    "median_ms": round(statistics.median(per_call), 6),
                    "max_ms": round(per_call[-1], 6),
                    "samples": len(per_call),
                    "calls_per_sample": calls,
                }
        finally:
            transport.close()
    return results


def _git():
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return {"commit": commit, "dirty": dirty}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--save", action="store_true", help="write the run as JSON")
    parser.add_argument("--name", help="file name without .json")
    parser.add_argument(
        "--results-dir", type=Path, default=REPO_ROOT / "benchmarks" / "results"
    )
    parser.add_argument(
        "--samples", type=int, default=5, help="samples per case (1-100)"
    )
    parser.add_argument("--note", help="free text stored in the JSON")
    args = parser.parse_args(argv)
    if not 1 <= args.samples <= 100:
        parser.error("--samples is between 1 and 100")

    import requests
    import uripath
    import uripath_http_requests

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        metrics = _cases(f"http://127.0.0.1:{server.server_port}", args.samples)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    for label, values in metrics.items():
        print(f"{label}: median {values['median_ms']:.3f} ms per call")
    if args.save:
        version = uripath_http_requests.__version__
        python = f"py{sys.version_info.major}.{sys.version_info.minor}"
        system = f"{platform.system().lower()}-{platform.machine().lower()}"
        name = args.name or f"{version}-{python}-{system}"
        document = {
            "schema": SCHEMA,
            "name": name,
            "source": "ci" if "GITHUB_ACTIONS" in os.environ else "local",
            "note": args.note,
            "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(
                timespec="seconds"
            ),
            "package": {"name": "uripath-http-requests", "version": version},
            "dependencies": {
                "uripath": uripath.__version__,
                "requests": requests.__version__,
            },
            "git": _git(),
            "python": platform.python_version(),
            "interpreter": platform.python_implementation(),
            "platform": sysconfig.get_platform(),
            "processor": platform.processor() or platform.machine(),
            "metrics": metrics,
        }
        args.results_dir.mkdir(parents=True, exist_ok=True)
        target = args.results_dir / f"{name}.json"
        target.write_text(
            json.dumps(document, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print("wrote", target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
