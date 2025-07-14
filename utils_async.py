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

from src.logger_config import get_logger
logger = get_logger(__name__)

async def check_mx(domain: str) -> bool:
    logger.info(f"Checking MX records for domain: {domain}")
    try:
        await resolver.query(domain, 'MX')
        logger.info(f"MX record found for domain: {domain}")
        return True
    except Exception as e:
        logger.warning(f"No MX record found for domain {domain}: {e}")
        return False

async def smtp_check(email: str) -> bool:
    domain = email.split('@')[1]
    logger.info(f"Performing SMTP check for email: {email}")
    def inner():
        try:
            records = dns.resolver.resolve(domain, 'MX')
            mx = str(records[0].exchange)
            logger.info(f"Using MX server {mx} for domain {domain}")
            server = smtplib.SMTP(timeout=10)
            server.connect(mx)
            server.helo()
            server.mail("noreply@yourapi.com")
            code, _ = server.rcpt(email)
            server.quit()
            valid = code == 250
            if valid:
                logger.info(f"SMTP check passed for email {email} (code {code})")
            else:
                logger.warning(f"SMTP check failed for email {email} (code {code})")
            return valid
        except Exception as e:
            logger.error(f"SMTP check exception for {email}: {e}")
            return False
    return await asyncio.get_event_loop().run_in_executor(executor, inner)

async def is_new_domain(domain: str, threshold_days=30) -> bool:
    logger.info(f"Checking if domain is new (threshold {threshold_days} days): {domain}")
    def inner():
        try:
            data = whois.whois(domain)
            logger.debug(f"[WHOIS Raw Data] {data}")

            created = data.creation_date
            logger.debug(f"[Parsed Creation Date] {created}")

            if not created:
                logger.warning(f"No creation date found for domain {domain}")
                return True

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
                    return True

            age_days = (datetime.now() - created_date).days
            logger.info(f"Domain {domain} age: {age_days} days")
            return age_days < threshold_days

        except Exception as e:
            logger.error(f"WHOIS lookup exception for domain {domain}: {e}")
            return True

    return await asyncio.get_event_loop().run_in_executor(executor, inner)

def is_disposable(domain: str) -> bool:
    result = domain in DISPOSABLE_DOMAINS
    logger.info(f"Domain {domain} disposable check: {result}")
    return result

def is_blacklisted(domain: str) -> bool:
    result = domain in BLACKLISTED_DOMAINS
    logger.info(f"Domain {domain} blacklisted check: {result}")
    return result

def is_whitelisted(domain: str) -> bool:
    result = domain in WHITELISTED_DOMAINS
    logger.info(f"Domain {domain} whitelisted check: {result}")
    return result

def contains_spam_keywords(email: str) -> bool:
    local = email.split("@")[0].lower()
    result = any(word in local for word in SPAM_KEYWORDS)
    logger.info(f"Email '{email}' spam keyword check: {result}")
    return result
