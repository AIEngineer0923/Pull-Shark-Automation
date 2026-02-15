import json
import time
from typing import List, Dict, Optional, Tuple
import threading
import subprocess
import os

class TokenManager:
    def __init__(self, tokens_file: str = "github_tokens.json"):
        self.tokens_file = tokens_file
        self.tokens: List[Dict] = []
        self.token_status: Dict[str, Dict] = {}
        self.lock = threading.Lock()
        self.load_tokens()

    def load_tokens(self):
        """Load tokens from file"""
        try:
            with open(self.tokens_file, 'r') as f:
                data = json.load(f)
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
            print(f"📋 Loaded {len(self.tokens)} GitHub tokens")
        except FileNotFoundError:
            print("⚠ No token file found. Create github_tokens.json")
            self.tokens = []

    def add_token(self, token: str, name: str = None):
        """Add a new token"""
        new_token = {
            'token': token,
            'name': name or f"token-{len(self.tokens)+1}"
        }
        self.tokens.append(new_token)
        
        token_key = token[:8]
        self.token_status[token_key] = {
            'remaining': 5000,
            'reset_time': 0,
            'last_used': 0,
            'errors': 0,
            'active': True
        }
        self.save_tokens()

    def save_tokens(self):
        """Save tokens to file"""
        with open(self.tokens_file, 'w') as f:
            json.dump({'tokens': self.tokens}, f, indent=2)

    def get_best_token(self) -> Optional[Tuple[str, Dict]]:
        """Get the token with most remaining requests"""
        with self.lock:
            best_token = None
            best_status = None
            best_remaining = -1
            
            for token in self.tokens:
                token_key = token['token'][:8]
                status = self.token_status.get(token_key, {})
                
                if not status.get('active', True):
                    continue
                    
                remaining = status.get('remaining', 0)
                if remaining > best_remaining:
                    best_remaining = remaining
                    best_token = token
                    best_status = status
                    
            if best_token:
                token_key = best_token['token'][:8]
                self.token_status[token_key]['last_used'] = time.time()
                self.token_status[token_key]['remaining'] -= 1
                return best_token['token'], best_status
                
            return None, None

    def get_token_stats(self) -> str:
        """Get token statistics"""
        stats = []
        for token in self.tokens:
            token_key = token['token'][:8]
            status = self.token_status.get(token_key, {})
            stats.append(
                f"  {token.get('name', token_key)}: "
                f"{status.get('remaining', 0)} remaining, "
                f"errors: {status.get('errors', 0)}"
            )
        return "\n".join(stats)