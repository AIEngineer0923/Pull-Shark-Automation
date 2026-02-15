import subprocess
import time
import socket
from typing import List, Optional
import os

class GitManager:
    def __init__(self, base_branch: str, max_retries: int, logger):
        self.base_branch = base_branch
        self.max_retries = max_retries
        self.logger = logger
        self.retry_delay = 5

    def wait_for_internet(self, timeout: int = 10) -> bool:
        """Wait for internet connection"""
        start_time = time.time()
        while time.time() - start_time < 60:
            try:
                socket.create_connection(("github.com", 443), timeout=timeout)
                return True
            except OSError:
                time.sleep(2)
        return False

    def run(self, command: List[str], check_internet: bool = True) -> subprocess.CompletedProcess:
        """Run git command with retries"""
        for attempt in range(self.max_retries):
            if check_internet and not self.wait_for_internet():
                raise Exception("No internet connection")

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

    def sync_base(self) -> bool:
        """Safely sync base branch"""
        try:
            self.run(["git", "fetch", "--all"])
            self.run(["git", "checkout", self.base_branch])
            self.run(["git", "pull", "origin", self.base_branch])
            return True
        except Exception as e:
            self.logger.error(f"Failed to sync base branch: {e}")
            return False

    def create_branch(self, name: str) -> bool:
        """Create new branch"""
        try:
            self.run(["git", "checkout", "-b", name])
            return True
        except Exception as e:
            self.logger.error(f"Failed to create branch {name}: {e}")
            return False

    def commit(self, file: str, message: str) -> bool:
        """Commit changes"""
        try:
            self.run(["git", "add", file])
            self.run(["git", "commit", "-m", message])
            return True
        except Exception as e:
            self.logger.error(f"Failed to commit: {e}")
            return False

    def push(self, branch: str) -> bool:
        """Push branch to remote"""
        try:
            self.run(["git", "push", "-u", "origin", branch])
            return True
        except Exception as e:
            self.logger.error(f"Failed to push {branch}: {e}")
            return False