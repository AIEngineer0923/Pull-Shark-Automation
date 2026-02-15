#!/usr/bin/env python3
"""
Background script to keep free proxies fresh (Windows compatible)
"""

import asyncio
import schedule
import time
import platform
from high_performance.proxy_manager import HighPerformanceProxyManager

# Windows-compatible asyncio settings
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def refresh_proxies():
    """Refresh proxy list"""
    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Refreshing proxies...")
    manager = HighPerformanceProxyManager()
    await manager.initialize()
    print(f"✅ Proxy refresh complete")
    await manager.close()

def run_async_refresh():
    """Run async refresh in sync context"""
    asyncio.run(refresh_proxies())

def main():
    print("🔄 Proxy Refresher Started")
    print("⏰ Will refresh proxies every 30 minutes")
    
    # Initial refresh
    run_async_refresh()
    
    # Schedule regular refreshes
    schedule.every(30).minutes.do(run_async_refresh)
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n🛑 Proxy refresher stopped")

if __name__ == "__main__":
    main()