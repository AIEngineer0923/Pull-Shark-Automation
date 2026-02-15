import requests
import json
from typing import Optional
from datetime import datetime  # This import was missing

class Notifier:
    def __init__(self, slack_webhook: Optional[str] = None, discord_webhook: Optional[str] = None):
        self.slack_webhook = slack_webhook
        self.discord_webhook = discord_webhook
        
    def send(self, message: str, level: str = "info"):
        """Send notification to configured channels"""
        
        # Discord
        if self.discord_webhook:
            try:
                # Color mapping
                color = {
                    "info": 5814783,      # Blue
                    "success": 3066993,    # Green
                    "warning": 16776960,    # Yellow
                    "error": 15548997       # Red
                }.get(level, 5814783)
                
                # Simple message format (more reliable)
                payload = {
                    "content": f"```{message}```"  # Wrap in code block for better formatting
                }
                
                # Or use embed format (more fancy)
                # payload = {
                #     "embeds": [{
                #         "description": message,
                #         "color": color,
                #         "timestamp": datetime.now().isoformat(),
                #         "title": f"GitHub Automation - {level.upper()}"
                #     }]
                # }
                
                response = requests.post(
                    self.discord_webhook, 
                    json=payload, 
                    timeout=5
                )
                
                if response.status_code == 204:  # Discord returns 204 on success
                    print(f"✅ Discord notification sent")
                else:
                    print(f"⚠ Discord returned status: {response.status_code}")
                    
            except Exception as e:
                print(f"⚠ Discord notification failed: {e}")
                
        # Slack
        if self.slack_webhook:
            try:
                payload = {"text": message}
                response = requests.post(
                    self.slack_webhook, 
                    json=payload, 
                    timeout=5
                )
                if response.status_code == 200:
                    print(f"✅ Slack notification sent")
                    
            except Exception as e:
                print(f"⚠ Slack notification failed: {e}")