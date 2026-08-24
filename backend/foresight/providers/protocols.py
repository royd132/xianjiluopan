from __future__ import annotations

from typing import Protocol, runtime_checkable


class ConnectorDataError(RuntimeError):
    """Raised when a source cache exists but violates its connector contract."""


@runtime_checkable
class DataConnector(Protocol):
    """Minimum lifecycle contract shared by source-specific connectors."""

    key: str

    def available(self) -> bool:
        """Return whether the connector has the local inputs required to read."""
