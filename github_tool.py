import subprocess
import json
import time
import socket
from typing import Optional, List, Dict
import re

class GitHubTool:
    def __init__(self, base_branch: str, max_retries: int, logger):
        self.base_branch = base_branch
        self.max_retries = max_retries
        self.logger = logger
        self.retry_delay = 5

    def wait_for_internet(self) -> bool:
        """Wait for internet connection"""
        try:
            socket.create_connection(("api.github.com", 443), timeout=5)
            return True
        except OSError:
            return False

    def run(self, command: List[str]) -> subprocess.CompletedProcess:
        """Run GitHub CLI command with retries"""
        for attempt in range(self.max_retries):
            if not self.wait_for_internet():
                time.sleep(5)
                continue

            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0:
                    return result

                self.logger.warning(
                    f"Attempt {attempt+1}/{self.max_retries} failed: {' '.join(command)}"
                )

                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))

            except subprocess.TimeoutExpired:
                self.logger.warning(f"Command timed out on attempt {attempt+1}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))

        raise Exception(f"Command failed after {self.max_retries} attempts: {' '.join(command)}")

    def check_rate_limit(self) -> Dict:
        """Check GitHub API rate limit"""
        try:
            result = self.run(["gh", "api", "rate_limit"])
            data = json.loads(result.stdout)
            core = data.get("resources", {}).get("core", {})
            
            remaining = core.get("remaining", 5000)
            reset_time = core.get("reset", 0)
            
            print(f"🔎 GitHub API Remaining: {remaining}")
            
            return {
                "remaining": remaining,
                "reset_time": reset_time
            }
        except Exception as e:
            print(f"⚠ Rate limit check failed: {e}")
            return {"remaining": 5000, "reset_time": 0}

    def create_pr(self, title: str, body: str, head: str) -> Optional[str]:
        """Create a pull request"""
        try:
            result = self.run([
                "gh", "pr", "create",
                "--title", title,
                "--body", body,
                "--base", self.base_branch,
                "--head", head
            ])
            
            match = re.search(r'/(\d+)$', result.stdout.strip())
            if match:
                pr_number = match.group(1)
                self.logger.info(f"Created PR #{pr_number}")
                return pr_number
                
            return None
        except Exception as e:
            self.logger.error(f"Failed to create PR: {e}")
            raise

    def merge_pr(self, branch: str) -> bool:
        """Merge a pull request"""
        try:
            self.run(["gh", "pr", "merge", branch, "--merge", "--auto"])
            self.logger.info(f"Merged PR {branch}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to merge PR {branch}: {e}")
            return False