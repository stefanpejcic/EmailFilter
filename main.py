from fastapi import FastAPI
from models import EmailInput, FeedbackInput
from database import *
from utils_async import *
import asyncio

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
  
