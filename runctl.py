#!/usr/bin/env python3
"""
DeepClaw Nova - runctl (governor CLI)
"""

import argparse
import time
from pathlib import Path
from core.job_store import JobStore
from core.workspace import get_approved_roots, is_path_in_approved_workspace


def format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "00:00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def handle_status(args):
    store = JobStore()
    active = store.get_active_jobs()
    last = store.get_last_failure()
    print("====================================================================")
    print(" DEEPCLAW NOVA GOVERNOR / JOB STORE")
    print("====================================================================")
    print(f"Active jobs: {len(active)}")
    for j in active:
        dur = time.time() - j["created_at"]
        print(f"  - {j['job_id']} [{j['status']}] {j['resource_class']} prio={j['priority']} {format_duration(dur)}")
        print(f"    {j['command'][:80]}")
    if last:
        print(f"Last failure: {last['job_id']} {last.get('last_failure_class')}")
    else:
        print("Last failure: none")
    print("Approved roots:")
    for r in get_approved_roots():
        print(f"  - {r}")


def handle_jobs(args):
    store = JobStore()
    jobs = store.list_jobs(limit=args.limit, status=args.status)
    if not jobs:
        print("No jobs found.")
        return
    print(f"{'JOB ID':<18} {'STATUS':<16} {'CLASS':<12} {'OWNER':<10} {'RETRIES':<8}")
    print("-" * 70)
    for j in jobs:
        print(f"{j['job_id']:<18} {j['status']:<16} {j['resource_class']:<12} {j['owner']:<10} {j['retry_count']:<8}")


def handle_check(args):
    p = Path(args.path)
    print("approved" if is_path_in_approved_workspace(p) else "DENIED")


def main():
    parser = argparse.ArgumentParser(description="DeepClaw Nova runctl")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("status", help="Show governor/job status")
    jp = sub.add_parser("jobs", help="List jobs")
    jp.add_argument("--limit", type=int, default=50)
    jp.add_argument("--status", type=str, default=None)
    cp = sub.add_parser("check", help="Check if path is in approved workspace")
    cp.add_argument("path", type=str)
    args = parser.parse_args()
    if args.command == "jobs":
        handle_jobs(args)
    elif args.command == "check":
        handle_check(args)
    else:
        handle_status(args)


if __name__ == "__main__":
    main()
