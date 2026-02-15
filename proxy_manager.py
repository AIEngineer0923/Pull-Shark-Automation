import random
import requests
import time
from typing import List, Dict, Optional
from datetime import datetime
import threading
import queue

class ProxyManager:
    """Sequential proxy manager for main.py"""
    
    def __init__(self, proxy_file: str = "proxies.txt"):
        self.proxy_file = proxy_file
        self.working_proxies: queue.Queue = queue.Queue()
        self.failed_proxies: Dict[str, datetime] = {}
        self.lock = threading.Lock()
        self.load_proxies()

    def load_proxies(self):
        """Load proxies from file"""
        try:
            with open(self.proxy_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        proxy = self.parse_proxy(line)
                        if proxy:
                            self.working_proxies.put(proxy)
            print(f"📋 Loaded {self.working_proxies.qsize()} proxies")
        except FileNotFoundError:
            print(f"⚠ No proxy file found. Create {self.proxy_file}")

    def parse_proxy(self, proxy_str: str) -> Optional[Dict]:
        """Parse proxy string"""
        try:
            if '@' in proxy_str:
                proto_rest, auth_host = proxy_str.split('://', 1) if '://' in proxy_str else ('http', proxy_str)
                auth, host = auth_host.split('@')
                user, password = auth.split(':')
                ip, port = host.split(':')
                
                return {
                    'protocol': proto_rest,
                    'user': user,
                    'password': password,
                    'ip': ip,
                    'port': port,
                    'url': proxy_str
                }
            else:
                if '://' in proxy_str:
                    proto, rest = proxy_str.split('://')
                    ip, port = rest.split(':')
                else:
                    proto = 'http'
                    ip, port = proxy_str.split(':')
                    
                return {
                    'protocol': proto,
                    'ip': ip,
                    'port': port,
                    'url': f"{proto}://{ip}:{port}"
                }
        except Exception:
            return None

    def get_proxy(self) -> Optional[Dict]:
        """Get a working proxy"""
        try:
            proxy = self.working_proxies.get_nowait()
            self.working_proxies.put(proxy)
            return proxy
        except queue.Empty:
            return None