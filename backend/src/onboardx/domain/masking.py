"""Masking of PII-bearing values for display (NFR-03)."""

MASK_CHAR = "*"
VISIBLE_CONTACT_CHARS = 2
VISIBLE_ACCOUNT_CHARS = 4
ACCOUNT_PREFIX_CHARS = 3


def mask_contact(contact: str) -> str:
    """Mask everything but the last 2 characters, preserving length: 9999999921 -> ********21."""
    if len(contact) <= VISIBLE_CONTACT_CHARS:
        return MASK_CHAR * len(contact)
    hidden = len(contact) - VISIBLE_CONTACT_CHARS
    return MASK_CHAR * hidden + contact[-VISIBLE_CONTACT_CHARS:]


def mask_account_number(account_number: str) -> str:
    """Keep the product prefix and last 4 digits: SAV123456789012 -> SAV********9012."""
    keep = ACCOUNT_PREFIX_CHARS + VISIBLE_ACCOUNT_CHARS
    if len(account_number) <= keep:
        return MASK_CHAR * len(account_number)
    hidden = len(account_number) - keep
    return (
        account_number[:ACCOUNT_PREFIX_CHARS]
        + MASK_CHAR * hidden
        + account_number[-VISIBLE_ACCOUNT_CHARS:]
    )
