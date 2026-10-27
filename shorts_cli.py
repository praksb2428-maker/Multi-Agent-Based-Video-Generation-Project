"""Command-line entry point for the content-planning milestone."""

import argparse
import json
from pathlib import Path

from src.shorts import approve_plan, create_draft


def _read_json(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def _write_json(path, value):
    target = Path(path)
    if target.exists():
        raise ValueError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="숏츠 콘텐츠 기획 초안 및 승인")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("draft", "approve"):
        command = subcommands.add_parser(name)
        command.add_argument("input", help="입력 JSON 경로")
        command.add_argument("output", help="새로 만들 출력 JSON 경로")
    args = parser.parse_args(argv)
    try:
        data = _read_json(args.input)
        result = create_draft(data) if args.command == "draft" else approve_plan(data)
        _write_json(args.output, result)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(2, f"오류: {error}\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
