import asyncio
import aiohttp
import time
from typing import List, Dict, Optional
from bs4 import BeautifulSoup


class HighPerformanceProxyManager:
    """Async high-performance rotating proxy manager"""

    def __init__(self):
        self.working_proxies: asyncio.Queue = asyncio.Queue()
        self.failed_proxies: Dict[str, float] = {}
        self.lock = asyncio.Lock()
        self.session: Optional[aiohttp.ClientSession] = None
        self.cooldown_seconds = 300  # 5 min cooldown for failed proxies
        self.test_url = "https://api.github.com/rate_limit"

    # --------------------------------------------------
    # SESSION MANAGEMENT
    # --------------------------------------------------

    async def ensure_session(self):
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=15)
            connector = aiohttp.TCPConnector(limit=100, ssl=False)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={"User-Agent": "Mozilla/5.0"}
            )
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    # --------------------------------------------------
    # FETCH PROXIES
    # --------------------------------------------------

    async def fetch_proxies(self) -> List[Dict]:
        """Fetch proxies from multiple reliable sources"""
        proxies = []
        seen = set()
        session = await self.ensure_session()

        sources = [
            # HTML sources
            ('https://free-proxy-list.net/', 'free-proxy-list'),
            ('https://www.sslproxies.org/', 'sslproxies'),

            # API / Raw sources (more reliable)
            ('https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all', 'proxyscrape'),
            ('https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt', 'github-speedx'),
            ('https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt', 'github-clarketm'),
        ]

        for url, source in sources:
            try:
                print(f"  🔎 Fetching from {source}...")
                async with session.get(url) as response:
                    if response.status != 200:
                        continue

                    # HTML TABLE SOURCES
                    if source in ['free-proxy-list', 'sslproxies']:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')

                        table = (
                            soup.find('table', {'id': 'proxylisttable'})
                            or soup.find('table', {'class': 'table'})
                        )

                        if table and table.tbody:
                            for row in table.tbody.find_all('tr')[:75]:
                                cols = row.find_all('td')
                                if len(cols) >= 7:
                                    ip = cols[0].text.strip()
                                    port = cols[1].text.strip()
                                    https = cols[6].text.strip().lower() == 'yes'

                                    if https:
                                        key = f"{ip}:{port}"
                                        if key not in seen:
                                            seen.add(key)
                                            proxies.append({
                                                'ip': ip,
                                                'port': port,
                                                'url': f'http://{ip}:{port}',
                                                'source': source
                                            })

                    # RAW TEXT / API SOURCES
                    else:
                        text = await response.text()
                        lines = text.strip().splitlines()

                        for line in lines[:150]:
                            line = line.strip()
                            if ':' in line:
                                parts = line.split(':')
                                if len(parts) == 2:
                                    ip, port = parts
                                    key = f"{ip}:{port}"

                                    if key not in seen:
                                        seen.add(key)
                                        proxies.append({
                                            'ip': ip,
                                            'port': port,
                                            'url': f'http://{ip}:{port}',
                                            'source': source
                                        })

            except Exception as e:
                print(f"  ⚠ Error from {source}: {e}")
                continue

        print(f"  📦 Total unique proxies collected: {len(proxies)}")
        return proxies

    # --------------------------------------------------
    # TEST PROXIES
    # --------------------------------------------------

    async def test_proxy(self, proxy: Dict) -> bool:
        """Test if proxy works"""
        try:
            session = await self.ensure_session()
            start = time.time()

            async with session.get(
                self.test_url,
                proxy=proxy['url'],
                timeout=8
            ) as response:
                if response.status == 200:
                    latency = time.time() - start
                    proxy['latency'] = latency
                    return True

        except Exception:
            pass

        return False

    # --------------------------------------------------
    # INITIALIZATION
    # --------------------------------------------------

    async def initialize(self):
        """Fetch and validate proxies"""
        print("🔍 Fetching proxies...")
        proxies = await self.fetch_proxies()

        if not proxies:
            print("❌ No proxies fetched.")
            return

        print(f"📦 Testing {len(proxies)} proxies...")

        semaphore = asyncio.Semaphore(50)

        async def limited_test(proxy):
            async with semaphore:
                return await self.test_proxy(proxy)

        test_tasks = [limited_test(p) for p in proxies]
        results = await asyncio.gather(*test_tasks)

        working = []
        for proxy, ok in zip(proxies, results):
            if ok:
                working.append(proxy)

        # Sort by latency (fastest first)
        working.sort(key=lambda x: x.get("latency", 999))

        for proxy in working:
            await self.working_proxies.put(proxy)

        print(f"✅ Working proxies: {len(working)}")

    # --------------------------------------------------
    # GET PROXY (ROTATING)
    # --------------------------------------------------

    async def get_proxy_async(self) -> Optional[Dict]:
        """Get rotating working proxy"""
        try:
            proxy = await asyncio.wait_for(self.working_proxies.get(), timeout=2)

            # Skip failed proxies still in cooldown
            key = f"{proxy['ip']}:{proxy['port']}"
            if key in self.failed_proxies:
                if time.time() - self.failed_proxies[key] < self.cooldown_seconds:
                    return None
                else:
                    del self.failed_proxies[key]

            await self.working_proxies.put(proxy)
            return proxy

        except asyncio.TimeoutError:
            return None

    # --------------------------------------------------
    # MARK FAILED
    # --------------------------------------------------

    async def mark_failed(self, proxy: Dict):
        """Mark proxy as temporarily failed"""
        key = f"{proxy['ip']}:{proxy['port']}"
        self.failed_proxies[key] = time.time()
