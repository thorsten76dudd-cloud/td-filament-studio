"""Background PC/SC card presence monitor."""

from __future__ import annotations

import threading
from typing import Callable

from smartcard.CardMonitoring import CardMonitor, CardObserver


class NfcCardMonitor:
    """Notifies when a card is inserted or removed."""

    def __init__(
        self,
        on_inserted: Callable[[], None],
        on_removed: Callable[[], None] | None = None,
    ) -> None:
        self._on_inserted = on_inserted
        self._on_removed = on_removed or (lambda: None)
        self._monitor: CardMonitor | None = None
        self._observer: _Observer | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._monitor is not None:
                return
            self._observer = _Observer(self._on_inserted, self._on_removed)
            self._monitor = CardMonitor()
            self._monitor.addObserver(self._observer)

    def stop(self) -> None:
        with self._lock:
            if self._monitor and self._observer:
                try:
                    self._monitor.deleteObserver(self._observer)
                except Exception:
                    pass
            self._monitor = None
            self._observer = None


class _Observer(CardObserver):
    def __init__(
        self,
        on_inserted: Callable[[], None],
        on_removed: Callable[[], None],
    ) -> None:
        self._on_inserted = on_inserted
        self._on_removed = on_removed

    def update(self, observable, actions) -> None:  # noqa: ANN001
        added, removed = actions
        if added:
            self._on_inserted()
        if removed:
            self._on_removed()
