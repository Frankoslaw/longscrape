import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import TypeAlias

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
JsonInput: TypeAlias = (
    JsonScalar | list["JsonInput"] | tuple["JsonInput", ...] | Mapping[str, "JsonInput"]
)
FrozenJsonValue: TypeAlias = (
    JsonScalar | tuple["FrozenJsonValue", ...] | Mapping[str, "FrozenJsonValue"]
)
FrozenJsonObject: TypeAlias = Mapping[str, FrozenJsonValue]


def freeze_json(value: JsonInput, *, path: str = "value") -> FrozenJsonValue:
    """Validate and recursively freeze a JSON-compatible value."""
    if isinstance(value, Mapping):
        frozen: dict[str, FrozenJsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} has a non-string object key: {key!r}")
            frozen[key] = freeze_json(item, path=f"{path}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(
            freeze_json(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{path} must not contain a non-finite float")
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise TypeError(f"{path} is not JSON-compatible: {type(value).__name__}")


def freeze_json_object(value: Mapping[str, JsonInput]) -> FrozenJsonObject:
    frozen = freeze_json(dict(value), path="object")
    assert isinstance(frozen, Mapping)
    return frozen


def thaw_json(value: FrozenJsonValue) -> JsonValue:
    if isinstance(value, Mapping):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value


def thaw_json_object(value: FrozenJsonObject) -> JsonObject:
    thawed = thaw_json(value)
    assert isinstance(thawed, dict)
    return thawed
