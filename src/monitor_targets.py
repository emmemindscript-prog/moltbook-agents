#!/usr/bin/env python3
"""
Strategia A — Monitor passivo target inattivi
Controlla periodicamente se nku-liftrails o alexthegoat postano contenuto
"""

import json
import logging
import os
import requests
from datetime import datetime
from pathlib import Path

BASE_URL = "https://www.moltbook.com/api/v1"
CREDENTIALS_PATH = Path(__file__).parent.parent.parent / ".config" / "moltbook" / "credentials.json"


def load_api_key():
    env_key = os.environ.get("MOLTBOOK_API_KEY")
    if env_key:
        return env_key

    if CREDENTIALS_PATH.exists():
        try:
            data = json.loads(CREDENTIALS_PATH.read_text())
            key = data.get("api_key")
            if key:
                return key
        except Exception:
            pass

    raise RuntimeError("MOLTBOOK_API_KEY non trovata in env o credentials.json")

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ALERT_FILE = DATA_DIR / "target_alerts.json"

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)

MONITORED = {
    "nku-liftrails": {
        "category": "Fleet/Infrastructure",
        "known_for": "4,519 tool calls logged",
        "status": "inactive",
        "priority": "high"
    },
    "alexthegoat": {
        "category": "Trading/Finance",
        "known_for": "autonomous trading system",
        "status": "active",
        "priority": "high"
    },
    # Nuovi target commerciali (expansion)
    "friendly-neighbor": {
        "category": "General/Multi-skill",
        "known_for": "startup-tool builder, identity themes",
        "status": "unknown",
        "priority": "medium"
    },
    "cornelius-trinity": {
        "category": "Code/Infrastructure",
        "known_for": "Layer Skip, x402 revenue transactions",
        "status": "unknown",
        "priority": "high"  # Revenue metrics = hot lead
    },
    "prod_hedgehog": {
        "category": "Infrastructure/DevOps",
        "known_for": "guardian stack, 30+ agent studio",
        "status": "active",  # Già visto nei commenti SparkLab
        "priority": "high"
    },
    "leef_01": {
        "category": "Infrastructure/Monitoring",
        "known_for": "cron-based health checks",
        "status": "unknown",
        "priority": "medium"
    },
    "tudou_web3": {
        "category": "DevOps/Operations",
        "known_for": "operational maturity focus",
        "status": "unknown",
        "priority": "medium"
    }
}


def scan_for_targets(limit=200):
    """Scansione feed per post dei target"""
    try:
        resp = requests.get(
            f"{BASE_URL}/posts",
            headers={"Authorization": f"Bearer {load_api_key()}"},
            params={"sort": "new", "limit": limit},
            timeout=20
        )
        
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}"}
        
        posts = resp.json().get("posts", [])
        found = {}
        
        for post in posts:
            author = post.get("author", {}).get("name", "")
            if author in MONITORED:
                found[author] = {
                    "post_id": post["id"],
                    "content": post.get("content", "")[:200],
                    "date": post.get("createdAt", ""),
                    "karma": post.get("karma", 0),
                    "found_at": datetime.now().isoformat()
                }
        
        return {"found": found, "scanned": len(posts)}
    except Exception as e:
        return {"error": str(e)}


def send_alert(target_data):
    """Prepara alert per notifica umana"""
    target = list(target_data["found"].keys())[0]
    post = target_data["found"][target]
    
    alert = {
        "timestamp": datetime.now().isoformat(),
        "target": target,
        "action": "TARGET_ACTIVE",
        "post_id": post["post_id"],
        "post_preview": post["content"],
        "recommended_action": f"Comment immediately with READY_MESSAGE",
        "url": f"https://www.moltbook.com/posts/{post['post_id']}"
    }
    
    # Salva alert
    DATA_DIR.mkdir(exist_ok=True)
    with open(ALERT_FILE, 'w') as f:
        json.dump(alert, f, indent=2)
    
    return alert


def main():
    logger.info("=" * 40)
    logger.info("MONITOR TARGET — Strategia A")
    logger.info("=" * 40)
    
    result = scan_for_targets()
    
    if "error" in result:
        logger.error(f"❌ Scan failed: {result['error']}")
        return
    
    found = result.get("found", {})
    
    if found:
        logger.info(f"🎯 FOUND {len(found)} target(s) active!")
        for target, data in found.items():
            info = MONITORED.get(target, {})
            logger.info(f"\n   @{target}")
            logger.info(f"   Category: {info.get('category', 'N/A')}")
            logger.info(f"   Known for: {info.get('known_for', 'N/A')}")
            logger.info(f"   Post: \"{data['content']}...\"")
            logger.info(f"   Karma: {data['karma']}")
            logger.info(f"   Date: {data['date']}")
        
        alert = send_alert(result)
        logger.info(f"\n📢 Alert saved: {ALERT_FILE}")
        logger.info(f"🔗 URL: {alert['url']}")
        logger.info("⏰ ACTION REQUIRED: Comment within 15 minutes for visibility")
    else:
        logger.info(f"🔍 Scanned {result['scanned']} posts")
        logger.info(f"❌ No targets found (still inactive)")
        logger.info(f"⏭️  Next check: scheduled run")


if __name__ == "__main__":
    main()
