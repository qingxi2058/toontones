"""
Reddit API submitter using PRAW (official Reddit API).
Safe: uses OAuth2, no cookie scraping.

Setup (one-time):
  1. Go to https://www.reddit.com/prefs/apps → "create another app" → script
  2. Name: toontones-backlink-bot
  3. Redirect URI: http://localhost:8080
  4. Copy client_id and client_secret
  5. Create .env file:
       REDDIT_CLIENT_ID=xxx
       REDDIT_CLIENT_SECRET=xxx
       REDDIT_USERNAME=your_username
       REDDIT_PASSWORD=your_password

Usage:
  pip install praw python-dotenv
  python reddit_post.py --subreddit WebGames --dry-run
  python reddit_post.py --subreddit WebGames
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

SITES_FILE = Path(__file__).parent.parent / "sites.json"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

try:
    import praw
    from dotenv import load_dotenv
except ImportError:
    print("Run: pip install praw python-dotenv")
    sys.exit(1)

load_dotenv(Path(__file__).parent.parent / ".env")


def load_sites():
    with open(SITES_FILE) as f:
        return json.load(f)


def mark_submitted(data, target_id):
    for t in data["targets"]:
        if t["id"] == target_id:
            t["status"] = "submitted"
            t["submitted_at"] = str(date.today())
    with open(SITES_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_reddit_targets(data, subreddit=None):
    targets = [t for t in data["targets"] if t["type"] == "reddit_api" and t["status"] == "pending"]
    if subreddit:
        targets = [t for t in targets if t["subreddit"].lower() == subreddit.lower()]
    return targets


def get_post_content(subreddit):
    template_file = TEMPLATES_DIR / f"reddit_{subreddit.lower()}.txt"
    if template_file.exists():
        lines = template_file.read_text().strip().split("\n")
        title = lines[0].replace("Title: ", "").strip()
        body = "\n".join(lines[2:]).replace("Body:\n", "").strip()
        return title, body

    # Generic fallback
    title = "I made a free color memory game with a daily challenge"
    body = (
        "Hey,\n\n"
        "I built ToonTones (https://toontones.net) — a browser-based color memory game "
        "where you recall and match colors with increasing difficulty.\n\n"
        "There's a daily color challenge mode and a color memory test that scores your accuracy. "
        "No signup, instant play.\n\n"
        "Would love feedback!"
    )
    return title, body


def run(subreddit=None, dry_run=False):
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    username = os.getenv("REDDIT_USERNAME")
    password = os.getenv("REDDIT_PASSWORD")

    if not all([client_id, client_secret, username, password]):
        print("Missing Reddit credentials. Create backlink-agent/.env with:")
        print("  REDDIT_CLIENT_ID=xxx")
        print("  REDDIT_CLIENT_SECRET=xxx")
        print("  REDDIT_USERNAME=your_username")
        print("  REDDIT_PASSWORD=your_password")
        sys.exit(1)

    data = load_sites()
    targets = get_reddit_targets(data, subreddit)

    if not targets:
        print("No pending Reddit targets found.")
        return

    for target in targets:
        sr = target["subreddit"]
        title, body = get_post_content(sr)

        print(f"\n📮 Posting to r/{sr}")
        print(f"  Title: {title}")
        print(f"  Body preview: {body[:100]}...")

        if dry_run:
            print("  [DRY RUN] Not posting.")
            continue

        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            user_agent=f"toontones-backlink-bot/1.0 by u/{username}",
        )

        subreddit_obj = reddit.subreddit(sr)
        submission = subreddit_obj.submit(title=title, selftext=body)
        print(f"  ✅ Posted: https://reddit.com{submission.permalink}")
        mark_submitted(data, target["id"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--subreddit", help="Post to a specific subreddit only")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(subreddit=args.subreddit, dry_run=args.dry_run)
