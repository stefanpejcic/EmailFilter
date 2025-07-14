from fastapi import FastAPI, HTTPException, Query, Path
from models import EmailInput, FeedbackInput
from database import *
from utils_async import *
import asyncio
from constants import load_list, add_to_list, remove_from_list
from logger_config import get_logger

logger = get_logger(__name__)

init_db()
app = FastAPI()

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
        score = 50
        if mx_exists:
            score += 20
        if smtp_valid:
            score += 20
        if whitelisted:
            score += 10
        if new_domain:
            score -= 10
        if disposable:
            score -= 30
        if blacklisted:
            score -= 40
        if spam_keywords:
            score -= 20
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
