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
            created = data.creation_date
            
            if not created:
                return True

            if isinstance(created, list):
                created = created[0]

            if isinstance(created, datetime):
                created_date = created
            else:
                try:
                    created_date = datetime.strptime(str(created), '%Y-%m-%d')
                except Exception:
                    return True

            age_days = (datetime.now() - created_date).days
            return age_days < threshold_days
        except Exception as e:
            print(f"Exception in whois lookup: {e}")
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
  
