import unicodedata


def normalize_catalog_text(value: str) -> str:
    """Return the canonical exact-match key used at write and query time."""
    compatible = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(
        "".join(character if character.isalnum() else " " for character in compatible).split()
    )
