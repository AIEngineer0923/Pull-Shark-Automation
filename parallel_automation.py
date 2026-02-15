import json
import uuid
import time
import os
import argparse
import asyncio
import aiofiles
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import signal
import sys
import platform
from concurrent.futures import ThreadPoolExecutor
import colorama
from colorama import Fore, Style

colorama.init()

from high_performance.token_manager import HighPerformanceTokenManager
from high_performance.proxy_manager import HighPerformanceProxyManager
from high_performance.git_manager import HighPerformanceGitManager
from high_performance.github_tool import HighPerformanceGitHubTool
from notifier import Notifier
from logger import setup_logger


class PRStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PRTask:
    index: int
    branch: str = ""
    status: PRStatus = PRStatus.PENDING
    pr_number: Optional[int] = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    @property
    def duration(self) -> float:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0


class ParallelAutomation:
    def __init__(self, config: Dict, max_concurrent: int = 10):
        self.config = config
        self.max_concurrent = max_concurrent
        self.logger = setup_logger()

        self.token_manager = None
        self.proxy_manager = None
        self.github_tool = None
        self.git_manager = None

        self.tasks: List[PRTask] = []
        self.stats = {
            'completed': 0,
            'failed': 0,
            'total_time': 0
        }

        self.start_time = None
        self.shutdown_flag = False
        self.executor = ThreadPoolExecutor(max_workers=10)

        # 🔔 Initialize notifier
        self.notifier = Notifier(
            config.get("slack_webhook"),
            config.get("discord_webhook")
        )

        try:
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
        except:
            pass

    def signal_handler(self, signum=None, frame=None):
        print(f"\n{Fore.YELLOW}🛑 Shutdown signal received...{Style.RESET_ALL}")
        self.shutdown_flag = True

    async def setup(self):
        print(f"{Fore.CYAN}🚀 Initializing parallel automation...{Style.RESET_ALL}")

        self.token_manager = HighPerformanceTokenManager()
        await self.token_manager.load_tokens_async()

        if self.config.get('use_free_proxies', True):
            self.proxy_manager = HighPerformanceProxyManager()
            await self.proxy_manager.initialize()

        self.github_tool = HighPerformanceGitHubTool(
            self.config['base_branch'],
            self.config['max_retries'],
            self.logger,
            self.token_manager,
            self.proxy_manager
        )

        self.git_manager = HighPerformanceGitManager(
            self.config['repo_path'],
            self.config['base_branch'],
            self.logger,
            self.executor
        )

    def generate_content(self, index: int) -> str:
        return f"""
---

## Automated Contribution #{index}
Timestamp: {datetime.now().isoformat()}
UUID: {uuid.uuid4()}
Platform: {platform.system()}
---
"""

    async def process_pr(self, task: PRTask) -> PRTask:
        task.status = PRStatus.PROCESSING
        task.start_time = time.time()

        try:
            task.branch = f"automation-{task.index}-{uuid.uuid4().hex[:8]}"

            if not await self.git_manager.sync_base():
                raise Exception("Failed to sync base branch")

            if not await self.git_manager.create_branch(task.branch):
                raise Exception(f"Failed to create branch {task.branch}")

            content = self.generate_content(task.index)

            if not await self.git_manager.commit(
                self.config['readme_file'],
                f"Automated update #{task.index}",
                content
            ):
                raise Exception("Failed to commit changes")

            if not self.config.get('dry_run', False):

                if not await self.git_manager.push(task.branch):
                    raise Exception("Failed to push branch")

                pr_number = await self.github_tool.create_pr(
                    f"Automated PR #{task.index}",
                    "Automated system update via parallel automation",
                    task.branch
                )

                if pr_number:
                    task.pr_number = pr_number
                    self.logger.info(f"✅ Created PR #{pr_number}")

                    # 🔔 Success notification
                    self.notifier.send(
                        f"✅ PR #{task.index} created successfully\n"
                        f"Branch: {task.branch}\n"
                        f"PR Number: #{pr_number}",
                        "success"
                    )

                    if self.config.get('auto_merge', True):
                        merge_success = await self.github_tool.merge_pr(task.branch)

                        if merge_success:
                            self.logger.info(f"✅ Merged PR #{pr_number}")
                            self.notifier.send(
                                f"✅ PR #{task.index} merged successfully",
                                "success"
                            )
                        else:
                            self.logger.warning(f"⚠ Failed to merge PR #{pr_number}")
                            self.notifier.send(
                                f"⚠ PR #{task.index} created but merge failed",
                                "warning"
                            )

            task.status = PRStatus.COMPLETED
            self.stats['completed'] += 1

        except Exception as e:
            task.status = PRStatus.FAILED
            task.error = str(e)
            self.stats['failed'] += 1
            self.logger.error(f"PR #{task.index} failed: {e}")

            # 🔔 Failure notification
            self.notifier.send(
                f"❌ PR #{task.index} failed\n"
                f"Error: {str(e)[:200]}",
                "error"
            )

        finally:
            task.end_time = time.time()

        return task

    async def run(self, start: int, end: int):
        self.start_time = time.time()
        self.tasks = [PRTask(index=i) for i in range(start, end + 1)]

        print(f"\n{Fore.GREEN}🚀 Starting parallel automation{Style.RESET_ALL}")

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def process_with_semaphore(task):
            async with semaphore:
                if self.shutdown_flag:
                    return task
                return await self.process_pr(task)

        tasks = [process_with_semaphore(task) for task in self.tasks]

        completed = 0

        for future in asyncio.as_completed(tasks):
            if self.shutdown_flag:
                break

            result = await future
            completed += 1

            elapsed = time.time() - self.start_time
            rate = completed / (elapsed / 60) if elapsed > 0 else 0

            print(f"\r📈 {completed}/{len(self.tasks)} "
                  f"✓ {self.stats['completed']} "
                  f"✗ {self.stats['failed']} "
                  f"⚡ {rate:.1f} PRs/min", end="")

            # 🔔 Progress update every 10 PRs
            if completed % 10 == 0:
                await self.save_state()

                self.notifier.send(
                    f"📊 Progress Update:\n"
                    f"Completed: {self.stats['completed']}/{len(self.tasks)}\n"
                    f"Failed: {self.stats['failed']}\n"
                    f"Speed: {rate:.1f} PRs/min",
                    "info"
                )

        await self.show_final_stats()

        await self.github_tool.close()
        if self.proxy_manager:
            await self.proxy_manager.close()
        await self.token_manager.close()
        self.executor.shutdown()

    async def save_state(self):
        state = {
            'last_completed_pr': max(
                [t.index for t in self.tasks if t.status == PRStatus.COMPLETED] or [0]
            ),
            'timestamp': datetime.now().isoformat(),
            'stats': self.stats
        }

        async with aiofiles.open('parallel_state.json', 'w') as f:
            await f.write(json.dumps(state, indent=2))

    async def show_final_stats(self):
        elapsed = time.time() - self.start_time
        minutes = elapsed / 60
        rate = self.stats['completed'] / minutes if minutes > 0 else 0

        print("\n🎉 Automation Complete!")

        # 🔔 Final completion notification
        self.notifier.send(
            f"🎉 Automation Complete!\n"
            f"Total: {len(self.tasks)} PRs\n"
            f"✅ Success: {self.stats['completed']}\n"
            f"❌ Failed: {self.stats['failed']}\n"
            f"⚡ Speed: {rate:.1f} PRs/min\n"
            f"⏱️ Time: {minutes:.1f} minutes",
            "success"
        )


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--concurrent", type=int, default=10)
    parser.add_argument("--start", type=int)
    parser.add_argument("--no-proxy", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open('config.json') as f:
        config = json.load(f)

    config['use_free_proxies'] = not args.no_proxy
    config['dry_run'] = args.dry_run

    start = args.start or 1
    end = args.count

    automation = ParallelAutomation(config, max_concurrent=args.concurrent)

    await automation.setup()
    await automation.run(start, end)


if __name__ == "__main__":
    asyncio.run(main())
