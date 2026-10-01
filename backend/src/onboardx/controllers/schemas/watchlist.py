"""Watchlist admin schemas (api-contracts 2.7)."""

from dataclasses import asdict

from pydantic import BaseModel, Field

from onboardx.domain.views import WatchlistEntryView, WatchlistPage


class WatchlistEntryIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    aliases: list[str] = Field(default_factory=list, max_length=10)
    list_type: str


class WatchlistEntryOut(BaseModel):
    entry_id: str
    name: str
    aliases: list[str]
    list_type: str
    active: bool
    added_at: str
    deactivated_at: str | None


class WatchlistOut(BaseModel):
    watchlist_version: int
    items: list[WatchlistEntryOut]


def entry_out(view: WatchlistEntryView) -> WatchlistEntryOut:
    return WatchlistEntryOut(**{**asdict(view), "aliases": list(view.aliases)})


def watchlist_out(page: WatchlistPage) -> WatchlistOut:
    return WatchlistOut(
        watchlist_version=page.watchlist_version, items=[entry_out(i) for i in page.items]
    )
