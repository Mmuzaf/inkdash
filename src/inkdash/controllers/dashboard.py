"""The only place that knows about both a provider and a layout."""

from __future__ import annotations

from inkdash.config import Config
from inkdash.layouts import Layout, get_layout
from inkdash.model import DashboardModel
from inkdash.providers import DataProvider, HomeAssistantProvider, MockProvider


class DashboardController:
    def __init__(
        self,
        config: Config,
        provider: DataProvider | None = None,
        layout: str | None = None,
    ) -> None:
        self.config = config
        self.provider = provider or build_provider(config, config.dashboard.provider)
        self.layout_name = layout or config.dashboard.layout

    async def load(self) -> DashboardModel:
        return await self.provider.load()

    def layout(self) -> Layout:
        return get_layout(self.layout_name)(self.config)


def build_provider(config: Config, name: str) -> DataProvider:
    if name == "mock":
        return MockProvider(config.dashboard.mock_fixture)
    if name in {"ha", "home_assistant"}:
        return HomeAssistantProvider(config)
    raise ValueError(f"Unknown provider: {name!r}. Available providers: mock, home_assistant")
