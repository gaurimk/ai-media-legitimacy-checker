import re

# Catches http(s) links, www. links, and bare domains like bit.ly or example.co.in
_URL = re.compile(
    r"(https?://\S+|www\.\S+|\b[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}\b\S*)"
)
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d\s-]{8,}\d)(?!\d)")

def scrub(text: str) -> str:
    """Hard guarantee: no links or phone numbers reach the image prompt."""
    return _PHONE.sub("a phone number", _URL.sub("a suspicious link", text))