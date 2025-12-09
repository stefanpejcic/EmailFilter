import re
import aiodns
import asyncio
import aiosmtplib
import dns.resolver
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import whois
from src.constants import *
from functools import lru_cache

resolver = aiodns.DNSResolver()
executor = ThreadPoolExecutor()

WHITELISTED_DOMAINS = load_list("whitelist")
BLACKLISTED_DOMAINS = load_list("blacklist")
DISPOSABLE_DOMAINS = load_list("disposable")
SPAM_KEYWORDS = load_list("spam_keywords")
SPAM_PATTERN = re.compile("|".join(map(re.escape, SPAM_KEYWORDS)), re.IGNORECASE)

from src.logger_config import get_logger
logger = get_logger(__name__)


async def check_gibberish(email: str) -> bool:
    local_part = email.split("@")[0]
    logger.debug(f"Checking if '{local_part}' is gibberish")
    if re.search(r"[bcdfghjklmnpqrstvwxyz]{5,}", local_part, re.IGNORECASE):
        logger.warning(f"'{local_part}' detected as gibberish")
        return True
    return False

async def check_mx(domain: str) -> bool:
    logger.debug(f"Checking MX records for domain: {domain}")
    try:
        await resolver.query(domain, 'MX')
        logger.debug(f"MX record found for domain: {domain}")
        return True
    except Exception as e:
        logger.warning(f"No MX record found for domain {domain}: {e}")
        return False

async def smtp_check(email: str) -> bool:
    domain = email.split('@')[1]
    try:
        mx_records = await resolver.query(domain, 'MX')
        mx_host = str(mx_records[0].host)
        smtp = aiosmtplib.SMTP(hostname=mx_host, timeout=2)
        await smtp.connect()
        await smtp.helo()
        await smtp.mail("noreply@yourapi.com")
        code, _ = await smtp.rcpt(email)
        await smtp.quit()
        return code == 250
    except Exception:
        return False


# cache domain
@lru_cache(maxsize=1000)
def cached_domain_age(domain):
    return asyncio.run(is_new_domain(domain))

async def is_new_domain(domain: str, threshold_days=30) -> bool:
    logger.debug(f"Checking if domain is new (threshold {threshold_days} days): {domain}")
    def inner():
        try:
            data = whois.whois(domain)
            logger.debug(f"[WHOIS Raw Data] {data}")

            created = data.creation_date
            logger.debug(f"[Parsed Creation Date] {created}")

            if not created:
                logger.warning(f"No creation date found for domain {domain}")
                return True, None  # Age unknown

            if isinstance(created, list):
                created = created[0]
                logger.debug(f"[Using First Date from List] {created}")

            if isinstance(created, datetime):
                created_date = created
            else:
                try:
                    created_date = datetime.strptime(str(created), '%Y-%m-%d')
                except Exception as e:
                    logger.error(f"Failed to parse creation date {created} for domain {domain}: {e}")
                    return True, None

            age_days = (datetime.now(timezone.utc) - created_date).days #timezone-aware
            logger.debug(f"Domain {domain} age: {age_days} days")
            return age_days < threshold_days, age_days

        except Exception as e:
            logger.error(f"WHOIS lookup exception for domain {domain}: {e}")
            return True, None

    return await asyncio.get_event_loop().run_in_executor(executor, inner)

def is_disposable(domain: str) -> bool:
    result = domain in DISPOSABLE_DOMAINS
    logger.debug(f"Domain {domain} disposable check: {result}")
    return result

def is_blacklisted(domain: str) -> bool:
    result = domain in BLACKLISTED_DOMAINS
    logger.debug(f"Domain {domain} blacklisted check: {result}")
    return result

def is_whitelisted(domain: str) -> bool:
    result = domain in WHITELISTED_DOMAINS
    logger.debug(f"Domain {domain} whitelisted check: {result}")
    return result

def contains_spam_keywords(email: str) -> bool:
    local = email.split("@")[0].lower()
    return bool(SPAM_PATTERN.search(local))
