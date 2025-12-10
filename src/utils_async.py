import re
import aiodns
import asyncio
import aiosmtplib
import dns.resolver
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import whois
from src.constants import *
from async_lru import alru_cache
import time

resolver = aiodns.DNSResolver()
executor = ThreadPoolExecutor()

WHITELISTED_DOMAINS = set(load_list("whitelist"))
BLACKLISTED_DOMAINS = set(load_list("blacklist"))
DISPOSABLE_DOMAINS = set(load_list("disposable"))
SPAM_KEYWORDS = load_list("spam_keywords")
SPAM_PATTERN = re.compile("|".join(map(re.escape, SPAM_KEYWORDS)), re.IGNORECASE)

from src.logger_config import get_logger
logger = get_logger(__name__)

_cached_lists = {}
_MX_CACHE = {}

def get_domain_set(list_name: str) -> set:
    """
    Returns the cached set for a list. Loads from disk if not cached.
    """
    global _cached_lists
    if list_name not in _cached_lists:
        _cached_lists[list_name] = set(load_list(list_name))
    return _cached_lists[list_name]


def check_gibberish(email: str) -> bool:
    local_part = email.split("@")[0]
    logger.debug(f"Checking if '{local_part}' is gibberish")
    if re.search(r"[bcdfghjklmnpqrstvwxyz]{5,}", local_part, re.IGNORECASE):
        logger.warning(f"'{local_part}' detected as gibberish")
        return True
    return False

async def mx_and_smtp_check(email: str):
    domain = email.split('@')[1]
    mx_records = await cached_mx_lookup(domain)
    if not mx_records:
        return False, None, False

    try:
        mx_host = mx_records[0]
        smtp = aiosmtplib.SMTP(hostname=mx_host, timeout=2)

        await smtp.connect()
        await smtp.helo()
        await smtp.mail("noreply@emailfilter.pejcic.rs")

        code, _ = await smtp.rcpt(email)
        await smtp.quit()

        smtp_valid = code == 250
    except Exception:
        smtp_valid = False

    return True, mx_records, smtp_valid



# cache MX
async def cached_mx_lookup(domain: str):
    now = time.time()

    if domain in _MX_CACHE:
        ts, mx_records = _MX_CACHE[domain]
        if mx_records and now - ts < 3600:
            return mx_records

    try:
        answer = await resolver.query(domain, 'MX')
        mx_records = [r.host for r in answer]
        _MX_CACHE[domain] = (now, mx_records)
        return mx_records
    except Exception:
        logger.warning(f"MX lookup failed for {domain}")
        return None


# cache domain
@alru_cache(maxsize=1000)
async def cached_domain_age(domain):
    return await is_new_domain(domain)

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




def check_domain_in_lists(domains: list[str]):
    results = {}
    domain_set = set(domains)

    disposable_set = get_domain_set("disposable")
    blacklist_set = get_domain_set("blacklist")
    whitelist_set = get_domain_set("whitelist")

    disposable_domains = domain_set & disposable_set
    blacklisted_domains = domain_set & blacklist_set
    whitelisted_domains = domain_set & whitelist_set

    for domain in domain_set:
        results[domain] = {
            "disposable": domain in disposable_domains,
            "blacklisted": domain in blacklisted_domains,
            "whitelisted": domain in whitelisted_domains
        }
    return results

def contains_spam_keywords(email: str) -> bool:
    local = email.split("@")[0].lower()
    return bool(SPAM_PATTERN.search(local))
