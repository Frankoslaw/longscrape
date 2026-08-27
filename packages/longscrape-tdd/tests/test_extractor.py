import pytest


@pytest.mark.asyncio
async def test_trivial():
    assert 2 + 2 == 4