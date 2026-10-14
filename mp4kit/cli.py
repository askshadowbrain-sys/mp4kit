"""The mp4kit command line: one cmd_* per subcommand."""
import argparse
from typing import Optional


def hexdump(data, start, length):
    """Hex bytes from `start`, 16 per line, lowercase pairs, no offset column."""
    chunk = data[start:start + length]
    return "\n".join(" ".join(f"{b:02x}" for b in chunk[i:i + 16]) for i in range(0, len(chunk), 16))


def cmd_hex(args):
    """`hex FILE [--at N] [--len N]`: print bytes of the file as hex."""
    with open(args.file, "rb") as f:
        print(hexdump(f.read(), args.at, args.len))
    return 0


def main(argv: Optional[list] = None) -> int:
    """Parse the command line and run the chosen subcommand."""
    p = argparse.ArgumentParser(prog="mp4kit")
    sub = p.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("hex", help="print bytes as hex")
    h.add_argument("file")
    h.add_argument("--at", type=int, default=0)
    h.add_argument("--len", type=int, default=64)
    h.set_defaults(func=cmd_hex)
    args = p.parse_args(argv)
    return args.func(args)
