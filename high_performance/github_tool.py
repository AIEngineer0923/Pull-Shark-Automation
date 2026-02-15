import asyncio
import aiohttp
import json
import time
import os
from typing import Optional, List, Dict, Tuple
import re

class HighPerformanceGitHubTool:
    """Async GitHub tool for high performance"""
    
    def __init__(self, base_branch: str, max_retries: int, logger, token_manager, proxy_manager=None):
        self.base_branch = base_branch
        self.max_retries = max_retries
        self.logger = logger
        self.token_manager = token_manager
        self.proxy_manager = proxy_manager
        self.session = None
        self.semaphore = asyncio.Semaphore(50)
        self.retry_delay = 5
        
    async def ensure_session(self):
        if self.session is None:
            connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
            self.session = aiohttp.ClientSession(connector=connector)
        return self.session
        
    async def run_gh_command(self, command: List[str], use_proxy: bool = True) -> Tuple[bool, str]:
        """Run GitHub CLI command asynchronously"""
        async with self.semaphore:
            token = await self.token_manager.get_best_token_async()
            if not token:
                return False, "No valid token available"
                
            proxy = None
            if use_proxy and self.proxy_manager:
                proxy = await self.proxy_manager.get_proxy_async()
                
            env = os.environ.copy()
            env['GITHUB_TOKEN'] = token['token']
            env['GH_TOKEN'] = token['token']
            
            if proxy:
                env['HTTP_PROXY'] = proxy['url']
                env['HTTPS_PROXY'] = proxy['url'].replace('http://', 'https://')
                
            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env
                )
                
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=30
                )
                
                if process.returncode == 0:
                    return True, stdout.decode()
                else:
                    error = stderr.decode()
                    if 'rate limit' in error.lower():
                        await self.token_manager.mark_rate_limited(token)
                    return False, error
                    
            except asyncio.TimeoutError:
                return False, "Command timeout"
            except Exception as e:
                return False, str(e)
                
    async def create_pr(self, title: str, body: str, head: str) -> Optional[int]:
        """Create PR asynchronously"""
        for attempt in range(self.max_retries):
            success, output = await self.run_gh_command([
                "gh", "pr", "create",
                "--title", title,
                "--body", body,
                "--base", self.base_branch,
                "--head", head
            ])
            
            if success:
                match = re.search(r'/(\d+)$', output.strip())
                if match:
                    pr_number = int(match.group(1))
                    self.logger.info(f"Created PR #{pr_number}")
                    return pr_number
                    
            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (2 ** attempt))
                
        return None
        
    async def merge_pr(self, branch: str) -> bool:
        """Merge PR asynchronously"""
        for attempt in range(self.max_retries):
            success, _ = await self.run_gh_command([
                "gh", "pr", "merge", branch, "--merge", "--auto"
            ])
            
            if success:
                self.logger.info(f"Merged PR {branch}")
                return True
                
            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (2 ** attempt))
                
        return False
        
    async def close(self):
        if self.session:
            await self.session.close()