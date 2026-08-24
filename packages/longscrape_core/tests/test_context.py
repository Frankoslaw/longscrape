import pytest
from longscrape_core import Context, ContextKey


def test_context_keys_are_identity_based_and_typed() -> None:
    first = ContextKey[int]("value")
    second = ContextKey[int]("value")
    context = Context()
    context.set(first, 3)
    assert context.get(first) == 3
    assert context.get(second) is None
    context.discard(first)
    with pytest.raises(LookupError, match="value"):
        context.require(first)
