import aiodns
import asyncio
import smtplib
import dns.resolver
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import whois
from constants import *

resolver = aiodns.DNSResolver()
executor = ThreadPoolExecutor()

WHITELISTED_DOMAINS = load_list("whitelist")
BLACKLISTED_DOMAINS = load_list("blacklist")
DISPOSABLE_DOMAINS = load_list("disposable")
SPAM_KEYWORDS = load_list("spam_keywords")

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_mx(domain: str) -> bool:
    try:
        await resolver.query(domain, 'MX')
        return True
    except:
        return False

async def smtp_check(email: str) -> bool:
    def inner():
        domain = email.split('@')[1]
        try:
            records = dns.resolver.resolve(domain, 'MX')
            mx = str(records[0].exchange)
            server = smtplib.SMTP(timeout=10)
            server.connect(mx)
            server.helo()
            server.mail("noreply@yourapi.com")
            code, _ = server.rcpt(email)
            server.quit()
            return code == 250
        except:
            return False
    return await asyncio.get_event_loop().run_in_executor(executor, inner)


async def is_new_domain(domain: str, threshold_days=30) -> bool:
    def inner():
        try:
            data = whois.whois(domain)
            logger.info(f"[WHOIS Raw Data] {data}")

            created = data.creation_date
            logger.info(f"[Parsed Creation Date] {created}")

            if not created:
                logger.warning("No creation date found.")
                return True

            if isinstance(created, list):
                created = created[0]
                logger.info(f"[Using First Date from List] {created}")

            if isinstance(created, datetime):
                created_date = created
            else:
                try:
                    created_date = datetime.strptime(str(created), '%Y-%m-%d')
                except Exception as e:
                    logger.error(f"Failed to parse creation date: {created} | Error: {e}")
                    return True

            age_days = (datetime.now() - created_date).days
            logger.info(f"[Domain Age Days] {age_days}")
            return age_days < threshold_days

        except Exception as e:
            logger.error(f"[WHOIS Exception] {e}")
            return True

    return await asyncio.get_event_loop().run_in_executor(executor, inner)

def is_disposable(domain: str) -> bool:
    return domain in DISPOSABLE_DOMAINS

def is_blacklisted(domain: str) -> bool:
    return domain in BLACKLISTED_DOMAINS

def is_whitelisted(domain: str) -> bool:
    return domain in WHITELISTED_DOMAINS

def contains_spam_keywords(email: str) -> bool:
    local = email.split("@")[0].lower()
    return any(word in local for word in SPAM_KEYWORDS)
  
