import asyncio
import git
from pathlib import Path
import aiofiles
from typing import Optional
import os
from concurrent.futures import ThreadPoolExecutor
import platform

class HighPerformanceGitManager:
    """Async Git manager using GitPython (Windows compatible)"""
    
    def __init__(self, repo_path: str, base_branch: str, logger, executor: ThreadPoolExecutor):
        self.repo_path = repo_path
        self.base_branch = base_branch
        self.logger = logger
        self.repo = None
        self.repo_lock = asyncio.Lock()
        self.executor = executor
        self.is_windows = platform.system() == 'Windows'
        
    async def ensure_repo(self):
        """Ensure git repo is initialized"""
        if self.repo is None:
            # Run git operations in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            self.repo = await loop.run_in_executor(
                self.executor,
                lambda: git.Repo(self.repo_path)
            )
        return self.repo
        
    async def run_git_operation(self, func, *args, **kwargs):
        """Run git operation in thread pool"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, func, *args, **kwargs)
        
    async def sync_base(self) -> bool:
        """Fast sync using gitpython"""
        async with self.repo_lock:
            try:
                repo = await self.ensure_repo()
                
                # Fetch with depth=1 for speed
                await self.run_git_operation(repo.remotes.origin.fetch)
                
                # Checkout base branch
                if self.base_branch in repo.heads:
                    await self.run_git_operation(repo.heads[self.base_branch].checkout)
                else:
                    await self.run_git_operation(
                        repo.create_head, 
                        self.base_branch, 
                        f"origin/{self.base_branch}"
                    )
                    await self.run_git_operation(repo.heads[self.base_branch].checkout)
                    
                # Pull latest
                await self.run_git_operation(repo.remotes.origin.pull, self.base_branch)
                return True
            except Exception as e:
                self.logger.error(f"Sync failed: {e}")
                return False
                
    async def create_branch(self, name: str) -> bool:
        """Fast branch creation"""
        async with self.repo_lock:
            try:
                repo = await self.ensure_repo()
                
                if name in repo.heads:
                    await self.run_git_operation(git.refs.head.Head.delete, repo, repo.heads[name])
                    
                new_branch = await self.run_git_operation(repo.create_head, name)
                await self.run_git_operation(new_branch.checkout)
                return True
            except Exception as e:
                self.logger.error(f"Branch creation failed: {e}")
                return False
                
    async def commit(self, file: str, message: str, content: str) -> bool:
        """Fast commit"""
        async with self.repo_lock:
            try:
                file_path = Path(self.repo_path) / file
                async with aiofiles.open(file_path, 'a', encoding='utf-8') as f:
                    await f.write(content)
                    
                repo = await self.ensure_repo()
                await self.run_git_operation(repo.index.add, [file])
                await self.run_git_operation(repo.index.commit, message)
                return True
            except Exception as e:
                self.logger.error(f"Commit failed: {e}")
                return False
                
    async def push(self, branch: str) -> bool:
        """Fast push"""
        async with self.repo_lock:
            try:
                repo = await self.ensure_repo()
                await self.run_git_operation(repo.remotes.origin.push, branch)
                return True
            except Exception as e:
                self.logger.error(f"Push failed: {e}")
                return False