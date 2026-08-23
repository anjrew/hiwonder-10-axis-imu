"""Command line entry points: list ports, print live data, dump raw bytes."""

from __future__ import annotations

import argparse
import sys

from .reader import DEFAULT_BAUDRATE, ImuReader, find_ports


def _fmt(label: str, values, unit: str) -> str:
    if values is None:
        return f"{label}: --"
    return f"{label}: " + " ".join(f"{v:8.3f}" for v in values) + f" {unit}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hiwonder-imu", description=__doc__)
    parser.add_argument("-p", "--port", help="serial device (default: first USB serial port found)")
    parser.add_argument("-b", "--baudrate", type=int, default=DEFAULT_BAUDRATE)
    parser.add_argument("-n", "--count", type=int, default=0, help="stop after N samples (0 = forever)")
    parser.add_argument("--list-ports", action="store_true", help="show serial ports and exit")
    parser.add_argument("--raw", action="store_true", help="print decoded frames instead of grouped samples")
    parser.add_argument("--view", action="store_true", help="open a live 3D view in the browser")
    parser.add_argument("--demo", action="store_true", help="with --view, use fake motion instead of hardware")
    parser.add_argument("--http-port", type=int, default=8420, help="port for --view (default: 8420)")
    parser.add_argument("--no-browser", action="store_true", help="with --view, do not open a browser tab")
    args = parser.parse_args(argv)

    if args.list_ports:
        ports = find_ports()
        print("\n".join(ports) if ports else "no USB serial devices found")
        return 0

    if args.view or args.demo:
        from .viz import serve

        try:
            serve(
                port=args.port,
                baudrate=args.baudrate,
                http_port=args.http_port,
                demo=args.demo,
                open_browser=not args.no_browser,
            )
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        return 0

    try:
        with ImuReader(args.port, args.baudrate) as imu:
            print(f"reading {imu.port} at {imu.baudrate} baud - ctrl-c to stop", file=sys.stderr)
            source = imu.frames() if args.raw else imu.samples()
            for i, item in enumerate(source, start=1):
                if args.raw:
                    print(f"{item.name:<12} " + " ".join(f"{v:9.4f}" for v in item.values))
                else:
                    print(
                        "  ".join(
                            [
                                _fmt("acc", item.accel, "m/s2"),
                                _fmt("gyro", item.gyro, "deg/s"),
                                _fmt("rpy", item.angle, "deg"),
                            ]
                        )
                    )
                if args.count and i >= args.count:
                    break
    except KeyboardInterrupt:
        return 0
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
