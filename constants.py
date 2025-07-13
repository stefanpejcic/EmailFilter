def load_list_from_file(filename: str) -> set:
    with open(filename, 'r') as f:
        return set(line.strip() for line in f if line.strip())

DISPOSABLE_DOMAINS = load_list_from_file('lists/disposable_domains.txt')
BLACKLISTED_DOMAINS = load_list_from_file('lists/blacklisted_domains.txt')
WHITELISTED_DOMAINS = load_list_from_file('lists/whitelisted_domains.txt')
SPAM_KEYWORDS = load_list_from_file('lists/spam_keywords.txt')
