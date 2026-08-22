"""Process-local capabilities shared by any stage composition."""

from dataclasses import dataclass, field
from typing import Generic, TypeVar, cast

T = TypeVar("T")
_MISSING = object()


@dataclass(frozen=True, eq=False)
class ContextKey(Generic[T]):
    """Identity-based key for a process-local pipeline capability."""

    name: str


@dataclass
class PipelineContext:
    """A mutable, non-serializable bag of capabilities for stage calls."""

    _values: dict[ContextKey[object], object] = field(default_factory=dict)

    def set(self, key: ContextKey[T], value: T) -> None:
        self._values[cast(ContextKey[object], key)] = value

    def get(self, key: ContextKey[T]) -> T | None:
        return cast(T | None, self._values.get(cast(ContextKey[object], key)))

    def require(self, key: ContextKey[T]) -> T:
        value = self._values.get(cast(ContextKey[object], key), _MISSING)
        if value is _MISSING:
            raise LookupError(f"Pipeline context value is missing: {key.name}")
        return cast(T, value)

    def discard(self, key: ContextKey[T]) -> None:
        self._values.pop(cast(ContextKey[object], key), None)
