def is_authorized(user_id: str, allowed_user_ids: frozenset[str]) -> bool:
    """Only an immutable Discord user ID grants access."""
    return user_id in allowed_user_ids
