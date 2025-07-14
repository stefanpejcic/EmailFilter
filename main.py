import json
import sqlite3
from fastapi import FastAPI, HTTPException, Query, Path, Body
from src.models import EmailInput, FeedbackInput
from src.database import *
from src.utils_async import *
import asyncio
from src.constants import load_list, add_to_list, remove_from_list
from src.logger_config import get_logger
from pathlib import Path as PathLib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "reputation.db")

logger = get_logger(__name__)

init_db()
app = FastAPI()

BANNER = r"""
                           _ _  __ _ _ _            
                          (_) |/ _(_) | |           
       ___ _ __ ___   __ _ _| | |_ _| | |_ ___ _ __ 
      / _ \ '_ ` _ \ / _` | | |  _| | | __/ _ \ '__|
     |  __/ | | | | | (_| | | | | | | | ||  __/ |   
      \___|_| |_| |_|\__,_|_|_|_| |_|_|\__\___|_|   
                                                
                Email Filter API started!
---------------------------------------------------------
"""

logger.info("\n" + BANNER)

DEFAULT_SCORES = {
    "base": 50,
    "mx_exists": 20,
    "smtp_valid": 20,
    "whitelisted": 10,
    "new_domain": -10,
    "disposable": -30,
    "blacklisted": -40,
    "spam_keywords": -20,
}

CONFIG_SCORES_PATH = PathLib("config/scores.json")

def load_scores(config_path: PathLib = CONFIG_SCORES_PATH) -> dict:
    if config_path.is_file():
        try:
            with config_path.open("r") as f:
                user_scores = json.load(f)
            merged = DEFAULT_SCORES.copy()
            merged.update(user_scores)
            logger.info(f"Loaded custom scores from {config_path}")
            return merged
        except Exception as e:
            logger.error(f"Failed to load scores config: {e}")
    else:
        logger.info(f"No custom scores config found at {config_path}, using defaults.")
    return DEFAULT_SCORES.copy()

# on startup
SCORES = load_scores()

@app.post("/filter-email")
async def filter_email(data: EmailInput):
    email = data.email
    domain = email.split("@")[1].lower()
    logger.info(f"Received filter request for email: {email}")

    try:
        # Async checks
        mx_task = check_mx(domain)
        smtp_task = smtp_check(email)
        new_domain_task = is_new_domain(domain)

        # Sync checks
        disposable = is_disposable(domain)
        blacklisted = is_blacklisted(domain)
        whitelisted = is_whitelisted(domain)
        spam_keywords = contains_spam_keywords(email)

        # Gather results concurrently
        mx_exists, smtp_valid, new_domain = await asyncio.gather(
            mx_task, smtp_task, new_domain_task
        )

        # Log domain check and reputation penalty
        log_domain_check(domain)
        rep_penalty = get_reputation_penalty(domain)

        # Calculate score
        score = SCORES["base"]
        if mx_exists:
            score += SCORES["mx_exists"]
        if smtp_valid:
            score += SCORES["smtp_valid"]
        if whitelisted:
            score += SCORES["whitelisted"]
        if new_domain:
            score += SCORES["new_domain"]
        if disposable:
            score += SCORES["disposable"]
        if blacklisted:
            score += SCORES["blacklisted"]
        if spam_keywords:
            score += SCORES["spam_keywords"]
        score += rep_penalty
        score = max(0, min(100, score))

        verdict = "accepted" if score >= 60 else "rejected"

        logger.info(f"Filter result for {email} - score: {score}, verdict: {verdict}")

        return {
            "email": email,
            "domain": domain,
            "disposable": disposable,
            "blacklisted": blacklisted,
            "mx_exists": mx_exists,
            "smtp_valid": smtp_valid,
            "new_domain": new_domain,
            "spam_keywords": spam_keywords,
            "reputation_penalty": rep_penalty,
            "score": score,
            "verdict": verdict
        }
    except Exception as e:
        logger.error(f"Error processing filter request for {email}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/feedback/spam")
async def report_spam(data: FeedbackInput):
    domain = data.email.split("@")[1].lower()
    logger.info(f"Marking domain as spam: {domain}")
    mark_domain_as_spam(domain)
    return {"message": f"Domain {domain} marked as spam. Thank you!"}


@app.post("/whitelist")
def add_whitelist(domain: str = Query(...)):
    domain = domain.lower()
    logger.info(f"Adding domain to whitelist: {domain}")
    if domain in load_list("whitelist"):
        logger.warning(f"Domain already whitelisted: {domain}")
        raise HTTPException(status_code=400, detail="Domain already whitelisted.")
    if domain in load_list("blacklist"):
        logger.warning(f"Domain is blacklisted, cannot whitelist without removal: {domain}")
        raise HTTPException(status_code=400, detail="Domain is blacklisted. Remove it before adding to whitelist.")
    add_to_list("whitelist", domain)
    logger.info(f"Domain added to whitelist: {domain}")
    return {"message": f"{domain} added to whitelist."}


@app.delete("/whitelist")
def delete_whitelist(domain: str = Query(...)):
    domain = domain.lower()
    logger.info(f"Removing domain from whitelist: {domain}")
    if domain not in load_list("whitelist"):
        logger.warning(f"Domain not found in whitelist: {domain}")
        raise HTTPException(status_code=404, detail="Domain not in whitelist.")
    remove_from_list("whitelist", domain)
    logger.info(f"Domain removed from whitelist: {domain}")
    return {"message": f"{domain} removed from whitelist."}


@app.post("/blacklist")
def add_blacklist(domain: str = Query(...)):
    domain = domain.lower()
    logger.info(f"Adding domain to blacklist: {domain}")
    if domain in load_list("blacklist"):
        logger.warning(f"Domain already blacklisted: {domain}")
        raise HTTPException(status_code=400, detail="Domain already blacklisted.")
    if domain in load_list("whitelist"):
        logger.warning(f"Domain is whitelisted, cannot blacklist without removal: {domain}")
        raise HTTPException(status_code=400, detail="Domain is whitelisted. Remove it before adding to blacklist.")
    add_to_list("blacklist", domain)
    logger.info(f"Domain added to blacklist: {domain}")
    return {"message": f"{domain} added to blacklist."}


@app.delete("/blacklist")
def delete_blacklist(domain: str = Query(...)):
    domain = domain.lower()
    logger.info(f"Removing domain from blacklist: {domain}")
    if domain not in load_list("blacklist"):
        logger.warning(f"Domain not found in blacklist: {domain}")
        raise HTTPException(status_code=404, detail="Domain not in blacklist.")
    remove_from_list("blacklist", domain)
    logger.info(f"Domain removed from blacklist: {domain}")
    return {"message": f"{domain} removed from blacklist."}


@app.get("/lists/{list_name}")
def get_list(list_name: str = Path(..., description="Name of the list to retrieve")):
    list_name = list_name.lower()
    logger.info(f"Fetching list: {list_name}")
    if list_name not in LIST_FILES:
        logger.warning(f"Requested list not found: {list_name}")
        raise HTTPException(status_code=404, detail="List not found.")
    try:
        items = sorted(load_list(list_name))
        logger.info(f"Loaded {len(items)} items from list {list_name}")
        return {
            "list": list_name,
            "items": items
        }
    except Exception as e:
        logger.error(f"Failed to load list {list_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load list: {str(e)}")


@app.get("/lists")
def get_all_lists():
    logger.info("Fetching all lists")
    result = {}
    for name in LIST_FILES:
        try:
            result[name] = sorted(load_list(name))
        except Exception as e:
            logger.warning(f"Failed to load list {name}: {e}")
            continue
    return result


@app.delete("/lists/{list_name}")
def clear_list(list_name: str):
    logger.info(f"Clearing list: {list_name}")
    if list_name not in LIST_FILES:
        logger.warning(f"List not found for clearing: {list_name}")
        raise HTTPException(status_code=404, detail="List not found.")
    _loaded_sets[list_name] = set()
    save_list(list_name)
    logger.info(f"List cleared: {list_name}")
    return {"message": f"{list_name} cleared."}



@app.get("/scores")
def get_scores():
    """
    Get the current scoring weights (defaults + user overrides).
    """
    return {"scores": SCORES, "note": "To update scores POST new values to /scores and restart the application."}


@app.post("/scores")
def update_scores(new_scores: dict = Body(..., example=DEFAULT_SCORES)):
    """
    Update the scoring weights by writing to config/scores.json.
    App restart is required to apply changes.
    """
    try:
        # only allow keys from DEFAULT_SCORES
        for key in new_scores.keys():
            if key not in DEFAULT_SCORES:
                raise HTTPException(status_code=400, detail=f"Invalid score key: {key}")

        CONFIG_SCORES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_SCORES_PATH.open("w") as f:
            json.dump(new_scores, f, indent=4)

        logger.info(f"User updated scores saved to {CONFIG_SCORES_PATH}. App restart required to apply changes.")

        return {
            "message": "Scores updated successfully. Please restart the application to apply changes.",
            "new_scores": new_scores,
        }
    except Exception as e:
        logger.error(f"Failed to update scores: {e}")
        raise HTTPException(status_code=500, detail="Failed to update scores.")

@app.post("/scores/default")
def restore_default_scores():
    """
    Restore the scoring weights to the default values by overwriting config/scores.json.
    Application restart is required to apply changes.
    """
    try:
        CONFIG_SCORES_PATH.parent.mkdir(parents=True, exist_ok=True)  # ensure config dir exists
        with CONFIG_SCORES_PATH.open("w") as f:
            json.dump(DEFAULT_SCORES, f, indent=4)

        logger.info(f"Scores restored to default and saved to {CONFIG_SCORES_PATH}. App restart required to apply changes.")

        return {
            "message": "Scores restored to default. Please restart the application to apply changes.",
            "default_scores": DEFAULT_SCORES,
        }
    except Exception as e:
        logger.error(f"Failed to restore default scores: {e}")
        raise HTTPException(status_code=500, detail="Failed to restore default scores.")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # dict-like rows
    return conn

@app.get("/domains/checked")
def get_checked_domains():
    """
    Return all domains in reputation DB with total checks and user marked spam counts.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT domain, total_checks, user_marked_spam FROM domain_reputation ORDER BY total_checks DESC")
        rows = cursor.fetchall()
        conn.close()
        domains = [dict(row) for row in rows]
        return {"domains": domains, "count": len(domains)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch checked domains: {e}")

@app.get("/domains/penalties")
def get_domains_penalties():
    """
    Return all domains with calculated reputation penalties based on spam ratio.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT domain, total_checks, user_marked_spam FROM domain_reputation ORDER BY domain")
        rows = cursor.fetchall()
        conn.close()
        penalties = []
        for row in rows:
            total = row["total_checks"]
            spam = row["user_marked_spam"]
            if total == 0:
                penalty = 0
            else:
                spam_ratio = spam / total
                penalty = int(-50 * spam_ratio)
            penalties.append({
                "domain": row["domain"],
                "total_checks": total,
                "user_marked_spam": spam,
                "reputation_penalty": penalty
            })
        return {"domains": penalties, "count": len(penalties)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch domain penalties: {e}")

