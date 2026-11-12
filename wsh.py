#!/usr/bin/python3
"""Run shell commands on a Tizen watch over sdb.

Usage:
    ./wsh.py --host <watch-ip> "id" "cat /proc/cmdline"
    WATCH_HOST=<watch-ip> ./wsh.py "id"

Options:
    --host IP    watch address (or set WATCH_HOST)
    --root       attempt the `root:on` sdb service first (will be refused on
                 retail firmware)

The host key is the one used by watchsdb.py (default ~/.tizen-sdb-key.pem).
"""
import argparse
import importlib.util
import os
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("watchsdb", _here / "watchsdb.py")
ws = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ws)


def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--host", default=os.environ.get("WATCH_HOST"))
    parser.add_argument("--root", action="store_true")
    parser.add_argument("commands", nargs="*")
    args = parser.parse_args()

    if not args.host:
        parser.error("watch address required: use --host <ip> or WATCH_HOST")
    if not args.commands:
        parser.error("no command given")

    ws.ensure_key()
    s = ws.Sdb(args.host)

    if args.root:
        try:
            local = s.next_id
            s.next_id += 1
            s._send(ws.OPEN, local - 1, 0, b"root:on\0")
            s.sock.settimeout(20)
            cmd, a0, a1, data = ws.read_packet(s.sock)
            print("[root] reply cmd=%08x data=%r" % (cmd, data[:120]))
        except Exception as e:
            print("[root] failed:", e)

    for c in args.commands:
        print("$ " + c)
        try:
            out = s.shell(c)
        except Exception as e:
            out = "ERR: %s" % e
        sys.stdout.write(out)
        if not out.endswith("\n"):
            sys.stdout.write("\n")

    s.close()


if __name__ == "__main__":
    main()
