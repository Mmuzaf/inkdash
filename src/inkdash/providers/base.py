"""Provider contract. A provider knows nothing about Textual or layouts."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from inkdash.model import DashboardModel


@runtime_checkable
class DataProvider(Protocol):
    """Loads a fully normalized dashboard model from some data source."""

    name: str

    async def load(self) -> DashboardModel: ...
