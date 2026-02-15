import json
import uuid
import time
import os
import argparse
from datetime import datetime
from pathlib import Path

from git_manager import GitManager
from github_tool import GitHubTool
from token_manager import TokenManager
from proxy_manager import ProxyManager
from notifier import Notifier
from logger import setup_logger

def load_config():
    """Load configuration"""
    with open("config.json") as f:
        return json.load(f)

def load_state():
    """Load state"""
    try:
        with open("state.json") as f:
            return json.load(f)
    except:
        return {"last_completed_pr": 0}

def save_state(state):
    """Save state"""
    with open("state.json", "w") as f:
        json.dump(state, f, indent=2)

def generate_content(index):
    """Generate README content"""
    return f"""
---

## Automated Contribution #{index}
Timestamp: {datetime.now().isoformat()}
UUID: {uuid.uuid4()}
---

"""

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="GitHub Automation Tool")
    parser.add_argument("--count", type=int, help="Override PR count")
    parser.add_argument("--delay", type=int, help="Override delay seconds")
    parser.add_argument("--dry-run", action="store_true", help="Enable dry run mode")
    parser.add_argument("--no-merge", action="store_true", help="Disable auto merge")
    parser.add_argument("--reset", action="store_true", help="Reset state")
    parser.add_argument("--use-proxies", action="store_true", help="Use proxies")
    return parser.parse_args()

def main():
    """Main function"""
    args = parse_args()
    config = load_config()
    state = load_state()
    logger = setup_logger()

    if args.reset:
        state["last_completed_pr"] = 0
        save_state(state)
        print("🔄 State reset.")
        return

    # Apply overrides
    if args.count:
        config["pr_count"] = args.count
    if args.delay:
        config["delay_seconds"] = args.delay
    if args.dry_run:
        config["dry_run"] = True
    if args.no_merge:
        config["auto_merge"] = False

    # Change to repo directory
    os.chdir(config["repo_path"])

    # Initialize managers
    git = GitManager(config["base_branch"], config["max_retries"], logger)
    gh = GitHubTool(config["base_branch"], config["max_retries"], logger)
    token_manager = TokenManager()
    proxy_manager = ProxyManager() if args.use_proxies else None
    notifier = Notifier(config.get("slack_webhook"), config.get("discord_webhook"))

    start = state["last_completed_pr"] + 1
    end = config["pr_count"]

    print(f"🚀 Starting from PR #{start}")
    print(f"⏱️  Delay: {config['delay_seconds']} seconds")

    consecutive_failures = 0
    
    for i in range(start, end + 1):
        try:
            print(f"\n🔹 Processing PR #{i}")
            
            branch = f"automation-{i}-{uuid.uuid4().hex[:8]}"
            
            # Git operations
            if not git.sync_base():
                raise Exception("Failed to sync base branch")
                
            if not git.create_branch(branch):
                raise Exception(f"Failed to create branch {branch}")
                
            # Update README
            with open(config["readme_file"], "a", encoding="utf-8") as f:
                f.write(generate_content(i))
                
            if not git.commit(config["readme_file"], f"Automated update #{i}"):
                print("⚠ No changes to commit")
                continue
                
            if not config["dry_run"]:
                # Get token
                token, _ = token_manager.get_best_token()
                if not token:
                    raise Exception("No valid tokens available")
                    
                # Push and create PR
                if not git.push(branch):
                    raise Exception("Failed to push branch")
                    
                pr_number = gh.create_pr(
                    f"Automated PR #{i}",
                    "Automated system update via GitHub Automation Tool.",
                    branch
                )
                
                if pr_number:
                    print(f"✅ PR #{i} created successfully (PR #{pr_number})")
                    
                    # Send creation notification
                    notifier.send(
                        f"✅ PR #{i} created successfully\n"
                        f"Branch: {branch}\n"
                        f"PR Number: #{pr_number}",
                        "success"
                    )
                    
                    # Auto-merge if enabled
                    if config["auto_merge"]:
                        merge_success = gh.merge_pr(branch)
                        
                        if merge_success:
                            print(f"✅ PR #{pr_number} merged successfully")
                            notifier.send(
                                f"✅ PR #{i} merged successfully\n"
                                f"PR Number: #{pr_number}",
                                "success"
                            )
                        else:
                            print(f"⚠️  Failed to merge PR #{pr_number}")
                            notifier.send(
                                f"⚠️  PR #{i} created but merge failed\n"
                                f"PR Number: #{pr_number}",
                                "warning"
                            )
                else:
                    print(f"✅ PR #{i} created successfully")
                
            # Update state
            state["last_completed_pr"] = i
            save_state(state)
            
            # Reset failure counter
            consecutive_failures = 0
            
            # Send notification every 10 PRs
            if i % 10 == 0:
                notifier.send(f"✅ Progress: {i}/{end} PRs completed")
                
            # Delay
            if i < end:
                print(f"⏱️  Waiting {config['delay_seconds']} seconds...")
                time.sleep(config["delay_seconds"])
                
        except Exception as e:
            consecutive_failures += 1
            logger.error(f"PR #{i} failed: {str(e)}")
            notifier.send(f"❌ Failed at PR #{i}: {str(e)[:100]}")
            
            if consecutive_failures >= 5:
                print("❌ Too many consecutive failures. Stopping.")
                break
                
            time.sleep(30)

    print("\n🎉 Automation completed!")

if __name__ == "__main__":
    main()