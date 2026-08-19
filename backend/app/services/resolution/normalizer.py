"""Deterministic normalization for entity fields.

Canonicalizes names, emails, phones, addresses, currencies, and dates
so that fuzzy matching can compare like-to-like. Every function is
pure — no database calls, no LLM involvement.
"""

from __future__ import annotations

import re
import unicodedata


def canonicalize_name(name: str) -> str:
    """Canonicalize an entity name for matching.

    Steps:
    1. Unicode normalize (NFKD)
    2. Lowercase
    3. Strip leading/trailing whitespace
    4. Collapse multiple spaces
    5. Remove common suffixes (Inc, LLC, Ltd, Corp, etc.)
    6. Remove punctuation
    7. Strip articles (the, a, an)

    "Acme Inc." → "acme"
    "ACME INC" → "acme"
    "Acme Incorporated" → "acme"
    "The ACME Corporation" → "acme"
    """
    s = unicodedata.normalize("NFKD", name)
    s = s.lower().strip()
    # Remove common business suffixes
    suffixes = [
        r"\binc\.?\b", r"\bllc\.?\b", r"\bltd\.?\b", r"\bcorp\.?\b",
        r"\bcorporation\b", r"\bincorporated\b", r"\bcompany\b", r"\bco\.?\b",
        r"\bgroup\b", r"\binternational\b", r"\bglobal\b", r"\bsolutions\b",
        r"\benterprises\b", r"\bholdings\b",
    ]
    for suffix in suffixes:
        s = re.sub(suffix, "", s)
    # Remove articles
    s = re.sub(r"\b(the|a|an)\b", "", s)
    # Remove punctuation
    s = re.sub(r"[^a-z0-9\s]", "", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def canonicalize_email(email: str) -> str:
    """Canonicalize an email for matching.

    - Lowercase
    - Strip whitespace
    - Remove dots in Gmail-style addresses (j.smith@gmail.com → jsmith@gmail.com)
    """
    s = email.lower().strip()
    if not s:
        return s
    # Gmail dot-stripping
    local, _, domain = s.partition("@")
    if domain in ("gmail.com", "googlemail.com"):
        local = local.replace(".", "")
    return f"{local}@{domain}"


def canonicalize_phone(phone: str) -> str:
    """Canonicalize a phone number for matching.

    Strips everything except digits, removes leading country code if 11 digits.
    """
    digits = re.sub(r"[^0-9]", "", phone)
    if not digits:
        return ""
    # Remove leading 1 for US numbers (11 digits starting with 1)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def canonicalize_address(address: str) -> str:
    """Canonicalize an address for matching.

    - Lowercase
    - Expand common abbreviations
    - Remove punctuation
    - Collapse whitespace
    """
    s = address.lower().strip()
    # Expand abbreviations
    abbrevs = {
        r"\bst\b": "street", r"\bave\b": "avenue", r"\bblvd\b": "boulevard",
        r"\brd\b": "road", r"\bdr\b": "drive", r"\bln\b": "lane",
        r"\bct\b": "court", r"\bpl\b": "place", r"\bwy\b": "way",
        r"\bste\b": "suite", r"\bfl\b": "floor", r"\brm\b": "room",
        r"\bn\b": "north", r"\bs\b": "south", r"\be\b": "east", r"\bw\b": "west",
    }
    for pattern, replacement in abbrevs.items():
        s = re.sub(pattern, replacement, s)
    # Remove punctuation
    s = re.sub(r"[^a-z0-9\s]", "", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def get_canonical_fields(entity_type: str, data: dict) -> dict:
    """Return canonical field values for an entity based on its type."""
    canonical = {}
    if entity_type == "customer":
        if data.get("name"):
            canonical["name"] = canonicalize_name(data["name"])
        if data.get("email"):
            canonical["email"] = canonicalize_email(data["email"])
        if data.get("phone"):
            canonical["phone"] = canonicalize_phone(data["phone"])
        if data.get("address"):
            canonical["address"] = canonicalize_address(data["address"])
    elif entity_type == "contract":
        if data.get("name"):
            canonical["name"] = canonicalize_name(data["name"])
    elif entity_type == "invoice":
        if data.get("invoice_number"):
            canonical["invoice_number"] = data["invoice_number"].strip().upper()
    elif entity_type == "payment":
        if data.get("reference"):
            canonical["reference"] = data["reference"].strip().upper()
    return canonical
