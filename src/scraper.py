#!/usr/bin/env python3
"""
Moltbook Agent Scraper - Versione 1.0
Raccoglie agenti dal feed e li salva in SQLite
"""

import sqlite3
import logging
import time
import json
from datetime import datetime
from pathlib import Path
import requests

# ===== CONFIG =====
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
DB_PATH = DATA_DIR / "agents.db"

BASE_URL = "https://www.moltbook.com/api/v1"
CREDENTIALS_PATH = Path(__file__).parent.parent.parent / ".config" / "moltbook" / "credentials.json"


def load_api_key():
    """Carica API key da env o credentials locali"""
    env_key = __import__('os').environ.get("MOLTBOOK_API_KEY")
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

# ===== LOGGING =====
LOGS_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / f"scraper_{datetime.now():%Y%m%d_%H%M}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def init_db():
    """Inizializza database SQLite"""
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            display_name TEXT,
            description TEXT,
            karma INTEGER DEFAULT 0,
            followers INTEGER DEFAULT 0,
            following INTEGER DEFAULT 0,
            is_claimed INTEGER DEFAULT 0,
            is_verified INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            last_active TEXT,
            first_seen TEXT,
            last_updated TEXT,
            tags TEXT,
            posts INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info(f"DB pronto: {DB_PATH}")


def extract_skills(desc):
    """Estrae keywords dalla descrizione"""
    if not desc:
        return "general"
    
    keywords = [
        "code", "python", "javascript", "api", "automation", "trading",
        "finance", "crypto", "ai", "ml", "infrastructure", "devops",
        "security", "booking", "payment", "design", "writing",
        "content", "analysis", "data", "proxy", "server", "hosting"
    ]
    
    found = [kw for kw in keywords if kw in desc.lower()]
    return ", ".join(found) if found else "general"


def fetch_agents():
    """Scarica agenti dal feed Moltbook"""
    headers = {"Authorization": f"Bearer {load_api_key()}"}
    
    try:
        logger.info("Chiamata API Moltbook...")
        resp = requests.get(
            f"{BASE_URL}/posts",
            headers=headers,
            params={"sort": "new", "limit": 50},
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("posts", [])
    except Exception as e:
        logger.error(f"Errore API: {e}")
        return []


def save_agents(posts):
    """Salva agenti nel database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    
    added = updated = 0
    seen = set()
    
    for post in posts:
        author = post.get("author", {})
        if not author:
            continue
        
        name = author.get("name")
        if not name or name in seen:
            continue
        
        seen.add(name)
        
        agent = {
            "id": author.get("id", f"unk_{name}"),
            "name": name,
            "display_name": author.get("display_name") or name,
            "description": (author.get("description") or "")[:500],
            "karma": author.get("karma", 0) or 0,
            "followers": author.get("followerCount", 0) or 0,
            "following": author.get("followingCount", 0) or 0,
            "is_claimed": 1 if author.get("isClaimed") else 0,
            "is_verified": 1 if author.get("isVerified") else 0,
            "is_active": 1 if author.get("isActive", True) else 0,
            "created_at": author.get("createdAt", ""),
            "last_active": author.get("lastActive", ""),
            "tags": extract_skills(author.get("description", "")),
            "posts": author.get("posts_count", 0),
            "comments": author.get("comments_count", 0),
            "first_seen": now,
            "last_updated": now
        }
        
        try:
            c.execute("SELECT name FROM agents WHERE name=?", (name,))
            if c.fetchone():
                c.execute('''
                    UPDATE agents SET
                        karma=?, followers=?, following=?,
                        last_active=?, last_updated=?, description=?,
                        is_active=?, tags=?
                    WHERE name=?
                ''', (
                    agent["karma"], agent["followers"], agent["following"],
                    agent["last_active"], agent["last_updated"], agent["description"],
                    agent["is_active"], agent["tags"], name
                ))
                updated += 1
            else:
                c.execute('''
                    INSERT INTO agents
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''', (
                    agent["id"], agent["name"], agent["display_name"],
                    agent["description"], agent["karma"], agent["followers"],
                    agent["following"], agent["is_claimed"], agent["is_verified"],
                    agent["is_active"], agent["created_at"], agent["last_active"],
                    agent["first_seen"], agent["last_updated"], agent["tags"],
                    agent["posts"], agent["comments"]
                ))
                added += 1
        except Exception as e:
            logger.error(f"Errore salvando {name}: {e}")
    
    conn.commit()
    conn.close()
    
    logger.info(f"Agenti: {added} nuovi, {updated} aggiornati")
    return added, updated


def get_stats():
    """Statistiche database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*), AVG(karma), SUM(followers) FROM agents")
    total, avg_karma, total_followers = c.fetchone()
    
    c.execute("SELECT name, karma FROM agents ORDER BY karma DESC LIMIT 5")
    top = c.fetchall()
    
    conn.close()
    
    return {
        "total": total,
        "avg_karma": round(avg_karma or 0),
        "total_followers": total_followers or 0,
        "top": top
    }


def main():
    """Esecuzione principale"""
    logger.info("=" * 50)
    logger.info("MOLTBOOK AGENT SCRAPER - Start")
    logger.info("=" * 50)
    
    # Init
    init_db()
    
    # Fetch
    posts = fetch_agents()
    if not posts:
        logger.error("Nessun post ricevuto - STOP")
        return False
    
    logger.info(f"Ricevuti {len(posts)} post")
    
    # Save
    added, updated = save_agents(posts)
    
    # Stats
    stats = get_stats()
    logger.info("-" * 50)
    logger.info(f"DATABASE: {stats['total']} agenti totali")
    logger.info(f"Karma medio: {stats['avg_karma']}")
    logger.info(f"Followers totali: {stats['total_followers']}")
    logger.info("Top 5 per karma:")
    for name, karma in stats['top']:
        logger.info(f"  - @{name}: {karma:,}")
    
    logger.info("=" * 50)
    logger.info("Completato con successo")
    
    return True


if __name__ == "__main__":
    main()
