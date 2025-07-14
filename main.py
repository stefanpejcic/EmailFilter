from fastapi import FastAPI, HTTPException, Query, Path
from models import EmailInput, FeedbackInput
from database import *
from utils_async import *
import asyncio

from constants import load_list, add_to_list, remove_from_list

init_db()
app = FastAPI()

@app.post("/filter-email")
async def filter_email(data: EmailInput):
    email = data.email
    domain = email.split("@")[1].lower()

    # Async checks
    mx_task = check_mx(domain)
    smtp_task = smtp_check(email)
    new_domain_task = is_new_domain(domain)

    # Sync checks
    disposable = is_disposable(domain)
    blacklisted = is_blacklisted(domain)
    whitelisted = is_whitelisted(domain)
    spam_keywords = contains_spam_keywords(email)

    # Gather results
    mx_exists, smtp_valid, new_domain = await asyncio.gather(
        mx_task, smtp_task, new_domain_task
    )

    # Log + reputation
    log_domain_check(domain)
    rep_penalty = get_reputation_penalty(domain)

    # Scoring
    score = 50
    if mx_exists: score += 20
    if smtp_valid: score += 20
    if whitelisted: score += 10
    if new_domain: score -= 10
    if disposable: score -= 30
    if blacklisted: score -= 40
    if spam_keywords: score -= 20
    score += rep_penalty
    score = max(0, min(100, score))

    verdict = "accepted" if score >= 60 else "rejected"

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

@app.post("/feedback/spam")
async def report_spam(data: FeedbackInput):
    domain = data.email.split("@")[1].lower()
    mark_domain_as_spam(domain)
    return {"message": f"Domain {domain} marked as spam. Thank you!"}

@app.post("/whitelist")
def add_whitelist(domain: str = Query(...)):
    domain = domain.lower()
    if domain in load_list("whitelist"):
        raise HTTPException(status_code=400, detail="Domain already whitelisted.")
    if domain in load_list("blacklist"):
        raise HTTPException(status_code=400, detail="Domain is blacklisted. Remove it before adding to whitelist.")
    add_to_list("whitelist", domain)
    return {"message": f"{domain} added to whitelist."}

@app.delete("/whitelist")
def delete_whitelist(domain: str = Query(...)):
    domain = domain.lower()
    if domain not in load_list("whitelist"):
        raise HTTPException(status_code=404, detail="Domain not in whitelist.")
    remove_from_list("whitelist", domain)
    return {"message": f"{domain} removed from whitelist."}

@app.post("/blacklist")
def add_blacklist(domain: str = Query(...)):
    domain = domain.lower()
    if domain in load_list("blacklist"):
        raise HTTPException(status_code=400, detail="Domain already blacklisted.")
    if domain in load_list("whitelist"):
        raise HTTPException(status_code=400, detail="Domain is whitelisted. Remove it before adding to blacklist.")
    add_to_list("blacklist", domain)
    return {"message": f"{domain} added to blacklist."}

@app.delete("/blacklist")
def delete_blacklist(domain: str = Query(...)):
    domain = domain.lower()
    if domain not in load_list("blacklist"):
        raise HTTPException(status_code=404, detail="Domain not in blacklist.")
    remove_from_list("blacklist", domain)
    return {"message": f"{domain} removed from blacklist."}

@app.get("/lists/{list_name}")
def get_list(list_name: str = Path(..., description="Name of the list to retrieve")):
    list_name = list_name.lower()
    if list_name not in LIST_FILES:
        raise HTTPException(status_code=404, detail="List not found.")
    
    try:
        return {
            "list": list_name,
            "items": sorted(load_list(list_name))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load list: {str(e)}")

# SLOW
@app.get("/lists")
def get_all_lists():
    result = {}
    for name in LIST_FILES:
        try:
            result[name] = sorted(load_list(name))
        except Exception:
            continue  # skip silently
    return result

@app.delete("/lists/{list_name}")
def clear_list(list_name: str):
    if list_name not in LIST_FILES:
        raise HTTPException(status_code=404, detail="List not found.")
    _loaded_sets[list_name] = set()
    save_list(list_name)
    return {"message": f"{list_name} cleared."}
