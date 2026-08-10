import pytest
from longscrape_core.errors import InvalidSerializedValue
from longscrape_core.serialization import (
    canonical_json,
    fingerprint,
    load_json_object,
)


def test_canonical_json_sorts_object_keys() -> None:
    assert canonical_json({"b": 2, "a": 1}) == '{"a":1,"b":2}'


def test_fingerprint_is_stable() -> None:
    assert fingerprint({"b": 2, "a": 1}) == fingerprint({"a": 1, "b": 2})


def test_load_json_object_rejects_array() -> None:
    with pytest.raises(InvalidSerializedValue, match="object"):
        load_json_object("[]")


def test_canonical_json_rejects_non_serializable_value() -> None:
    with pytest.raises(InvalidSerializedValue):
        canonical_json({"invalid": {1, 2, 3}})
