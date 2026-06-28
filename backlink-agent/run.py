"""
Backlink agent runner for toontones.net.
Enforces rate limiting: max 3 submissions per run, status tracked in sites.json.

Usage:
  python run.py --status          # Show submission progress
  python run.py --next            # Submit next 1-3 pending form targets
  python run.py --reddit          # Post to next pending Reddit target
  python run.py --dry-run         # Preview without submitting
"""

import argparse
import json
from pathlib import Path

SITES_FILE = Path(__file__).parent / "sites.json"


def load_sites():
    with open(SITES_FILE) as f:
        return json.load(f)


def print_status():
    data = load_sites()
    targets = data["targets"]
    total = len(targets)
    submitted = [t for t in targets if t["status"] == "submitted"]
    pending = [t for t in targets if t["status"] == "pending"]

    print(f"\n📊 Backlink Status — {data['site']['url']}")
    print(f"   Total targets : {total}")
    print(f"   Submitted     : {len(submitted)}")
    print(f"   Pending       : {len(pending)}")

    if submitted:
        print("\n✅ Submitted:")
        for t in submitted:
            print(f"   [{t['submitted_at']}] {t['name']} (DA {t['da']})")

    if pending:
        print("\n⏳ Pending (by type):")
        for typ in ["form", "reddit_api", "manual", "web2"]:
            group = [t for t in pending if t["type"] == typ]
            if group:
                print(f"   {typ}:")
                for t in group:
                    print(f"     - {t['name']} (DA {t['da']}) {t['notes'][:60] if t['notes'] else ''}")


def run_next(dry_run=False, limit=3):
    from submitters.form_submit import run as form_run
    data = load_sites()
    pending_forms = [t for t in data["targets"] if t["type"] == "form" and t["status"] == "pending"]
    batch = pending_forms[:limit]

    if not batch:
        print("No pending form targets. Try --reddit or --manual.")
        return

    print(f"Submitting {len(batch)} form target(s) (limit {limit}/run)...")
    for t in batch:
        form_run(site_id=t["id"], dry_run=dry_run)


def run_reddit(dry_run=False):
    from submitters.reddit_post import run as reddit_run
    data = load_sites()
    pending = [t for t in data["targets"] if t["type"] == "reddit_api" and t["status"] == "pending"]
    if not pending:
        print("No pending Reddit targets.")
        return
    # Post to only 1 subreddit per run to avoid spam signals
    reddit_run(subreddit=pending[0]["subreddit"], dry_run=dry_run)


def print_manual_queue():
    data = load_sites()
    manual = [t for t in data["targets"] if t["type"] in ("manual", "web2") and t["status"] == "pending"]
    if not manual:
        print("No manual targets pending.")
        return
    print("\n📋 Manual submission queue:")
    for t in manual:
        print(f"\n  {t['name']} (DA {t['da']})")
        print(f"  URL: {t['submit_url']}")
        if t["notes"]:
            print(f"  Note: {t['notes']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ToonTones backlink agent")
    parser.add_argument("--status", action="store_true", help="Show submission progress")
    parser.add_argument("--next", action="store_true", help="Submit next batch of form targets (max 3)")
    parser.add_argument("--reddit", action="store_true", help="Post to next Reddit target")
    parser.add_argument("--manual", action="store_true", help="Show manual submission queue")
    parser.add_argument("--dry-run", action="store_true", help="Preview without submitting")
    args = parser.parse_args()

    if args.status:
        print_status()
    elif args.next:
        run_next(dry_run=args.dry_run)
    elif args.reddit:
        run_reddit(dry_run=args.dry_run)
    elif args.manual:
        print_manual_queue()
    else:
        parser.print_help()
