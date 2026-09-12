from __future__ import annotations

import argparse
import sys

from src.pipeline import run

DEFAULT_DOMAINS = ["postman.com", "supabase.com", "vapi.ai"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autonomous Lead Enrichment Agent")
    parser.add_argument(
        "--domains", nargs="+", default=None,
        help="Space-separated list of company domains, e.g. --domains postman.com supabase.com",
    )
    parser.add_argument(
        "--domains-file", type=str, default=None,
        help="Path to a text file with one domain per line",
    )
    return parser.parse_args()


def resolve_domains(args: argparse.Namespace) -> list[str]:
    if args.domains:
        return args.domains
    if args.domains_file:
        with open(args.domains_file, encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return DEFAULT_DOMAINS


def main() -> int:
    args = parse_args()
    domains = resolve_domains(args)
    print(f"Running lead enrichment on {len(domains)} domain(s): {domains}")
    results = run(domains)
    failed = [r for r in results if r.status == "failed"]
    if failed:
        print(f"\n{len(failed)} domain(s) failed: {[r.domain for r in failed]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())