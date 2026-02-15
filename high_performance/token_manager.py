import json
import asyncio
import aiohttp
import aiofiles
import time
from typing import List, Dict, Optional, Tuple
import random

class HighPerformanceTokenManager:
    """Async token manager for high performance"""
    
    def __init__(self, tokens_file: str = "github_tokens.json"):
        self.tokens_file = tokens_file
        self.tokens: List[Dict] = []
        self.token_status: Dict[str, Dict] = {}
        self.lock = asyncio.Lock()
        self.session = None
        
    async def ensure_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
        
    async def load_tokens_async(self):
        """Load tokens asynchronously"""
        try:
            async with aiofiles.open(self.tokens_file, 'r') as f:
                data = json.loads(await f.read())
                self.tokens = data.get('tokens', [])
                
            for token in self.tokens:
                token_key = token['token'][:8]
                self.token_status[token_key] = {
                    'remaining': 5000,
                    'reset_time': 0,
                    'last_used': 0,
                    'errors': 0,
                    'active': True
                }
            print(f"📋 Loaded {len(self.tokens)} tokens")
        except FileNotFoundError:
            print("⚠ Token file not found")
            
    async def check_token_rate_limit_async(self, token: Dict) -> Tuple[int, int]:
        """Check rate limit asynchronously"""
        try:
            session = await self.ensure_session()
            headers = {'Authorization': f"token {token['token']}"}
            
            async with session.get(
                'https://api.github.com/rate_limit',
                headers=headers,
                timeout=10
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    core = data.get('resources', {}).get('core', {})
                    return core.get('remaining', 0), core.get('reset', 0)
        except:
            pass
        return 0, 0
        
    async def get_best_token_async(self) -> Optional[Dict]:
        """Get best available token"""
        async with self.lock:
            best_token = None
            best_remaining = -1
            
            # Shuffle for fairness
            tokens_copy = self.tokens.copy()
            random.shuffle(tokens_copy)
            
            for token in tokens_copy:
                token_key = token['token'][:8]
                status = self.token_status.get(token_key)
                
                if not status or not status.get('active', True):
                    continue
                    
                # Refresh status if needed
                if time.time() - status.get('last_used', 0) > 300:
                    remaining, reset = await self.check_token_rate_limit_async(token)
                    status['remaining'] = remaining
                    status['reset_time'] = reset
                    
                if status['remaining'] > best_remaining:
                    best_remaining = status['remaining']
                    best_token = token
                    
            if best_token:
                token_key = best_token['token'][:8]
                self.token_status[token_key]['last_used'] = time.time()
                self.token_status[token_key]['remaining'] -= 1
                
            return best_token
            
    async def close(self):
        if self.session:
            await self.session.close()