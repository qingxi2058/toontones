"""
Form-based directory submitter for toontones.net.
Uses Playwright to fill and submit forms on AI/game directories that don't require login.

Usage:
  pip install playwright
  playwright install chromium
  python form_submit.py --site futurepedia
  python form_submit.py --all --dry-run
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Run: pip install playwright && playwright install chromium")
    sys.exit(1)

SITES_FILE = Path(__file__).parent.parent / "sites.json"


def load_sites():
    with open(SITES_FILE) as f:
        data = json.load(f)
    return data


def mark_submitted(sites_data, site_id):
    for target in sites_data["targets"]:
        if target["id"] == site_id:
            target["status"] = "submitted"
            target["submitted_at"] = str(date.today())
    with open(SITES_FILE, "w") as f:
        json.dump(sites_data, f, indent=2, ensure_ascii=False)


def get_form_targets(sites_data):
    return [t for t in sites_data["targets"] if t["type"] == "form" and t["status"] == "pending"]


def submit_generic(page, target, site_info, templates):
    """Generic form filler — opens the URL and waits for manual review."""
    print(f"  Opening: {target['submit_url']}")
    page.goto(target["submit_url"], wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)

    # Try common field patterns
    fill_attempts = [
        (["input[name*='url']", "input[placeholder*='URL']", "input[placeholder*='url']", "input[placeholder*='website']"], site_info["url"]),
        (["input[name*='name']", "input[name*='title']", "input[placeholder*='name']", "input[placeholder*='tool']"], site_info["name"]),
        (["textarea[name*='desc']", "textarea[placeholder*='desc']", "textarea[name*='about']"], templates["short"]),
    ]

    for selectors, value in fill_attempts:
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if el.count() > 0:
                    el.fill(value)
                    print(f"    Filled {sel}")
                    break
            except Exception:
                pass

    print(f"  [MANUAL] Review and submit: {target['submit_url']}")
    print(f"  Press Enter when done (or type 'skip' to skip)...")
    response = input().strip()
    return response != "skip"


def run(site_id=None, dry_run=False):
    data = load_sites()
    site_info = data["site"]

    templates = {
        "short": open(Path(__file__).parent.parent / "templates/short.txt").read().strip(),
        "long": open(Path(__file__).parent.parent / "templates/long.txt").read().strip(),
    }

    targets = get_form_targets(data)
    if site_id:
        targets = [t for t in targets if t["id"] == site_id]

    if not targets:
        print("No pending form targets found.")
        return

    print(f"Found {len(targets)} pending form target(s).")

    if dry_run:
        for t in targets:
            print(f"  [DRY RUN] Would submit to: {t['name']} ({t['submit_url']})")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        for i, target in enumerate(targets):
            print(f"\n[{i+1}/{len(targets)}] {target['name']} (DA {target['da']})")
            if target.get("notes"):
                print(f"  Note: {target['notes']}")

            success = submit_generic(page, target, site_info, templates)
            if success:
                mark_submitted(data, target["id"])
                print(f"  ✅ Marked as submitted")
            else:
                print(f"  ⏭  Skipped")

            if i < len(targets) - 1:
                print("  Waiting 5s before next submission...")
                page.wait_for_timeout(5000)

        browser.close()

    print(f"\nDone. Submitted to {sum(1 for t in targets if t['status'] == 'submitted')} site(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", help="Submit to a specific site ID only")
    parser.add_argument("--all", action="store_true", help="Submit to all pending form targets")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done without submitting")
    args = parser.parse_args()

    if not args.site and not args.all:
        parser.print_help()
        sys.exit(1)

    run(site_id=args.site, dry_run=args.dry_run)
