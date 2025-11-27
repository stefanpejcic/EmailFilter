from pathlib import Path as PathLib

BASE_DIR = PathLib(__file__).parent.parent / "lists"

LIST_FILES = {
    "whitelist": BASE_DIR / "whitelisted_domains.txt",
    "blacklist": BASE_DIR / "blacklisted_domains.txt",
    "disposable": BASE_DIR / "disposable_domains.txt",
    "spam_keywords": BASE_DIR / "spam_keywords.txt",
}

_loaded_sets = {}

def load_list(name: str) -> set:
    """Lazy-loads and returns a cached set from a list file."""
    if name not in LIST_FILES:
        raise ValueError(f"List '{name}' not found.")
    if name not in _loaded_sets:
        path = LIST_FILES[name]
        with path.open('r') as f:
            _loaded_sets[name] = set(line.strip() for line in f if line.strip())
    return _loaded_sets[name]

def save_list(name: str):
    """Writes the updated set to its respective file."""
    if name not in LIST_FILES or name not in _loaded_sets:
        raise ValueError(f"List '{name}' not loaded or recognized.")
    path = LIST_FILES[name]
    with path.open('w') as f:
        for item in sorted(_loaded_sets[name]):
            f.write(item + "\n")

def add_to_list(name: str, item: str):
    item = item.strip().lower()
    opposite = "blacklist" if name == "whitelist" else "whitelist"
    opp_list = load_list(opposite)
    if item in opp_list:
        opp_list.remove(item)
        save_list(opposite)
    s = load_list(name)
    s.add(item)
    save_list(name)



def remove_from_list(name: str, item: str):
    s = load_list(name)
    s.discard(item.strip().lower())
    save_list(name)
