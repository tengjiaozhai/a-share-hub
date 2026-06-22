"""FX (foreign exchange) service placeholder.

Phase 1: no-op implementation. Both methods return ``None`` so callers can
detect "FX rate unavailable" without forcing a hard conversion. This is
intentional per the Alpha Holdings UX overhaul plan: A 股 CNY and 美股 USD are
displayed in their native currency without merging into a single total.

Future phases may wire a real rate provider here (e.g. Yahoo Finance,
exchangerate.host). Until then, callers must treat ``None`` as "do not
convert".
"""
from __future__ import annotations


class FxService:
    """Resolve FX rates between CNY and USD.

    Both lookups are currently placeholders that return ``None``. The shape of
    the API is fixed so call sites can be written ahead of the real provider.
    """

    def get_cny_per_usd(self) -> float | None:
        """Return the CNY value of one USD.

        Returns ``None`` while the real provider is not wired up. Callers must
        not fall back to a hard-coded rate — they should surface "rate
        unavailable" instead.
        """
        return None

    def get_usd_per_cny(self) -> float | None:
        """Return the USD value of one CNY.

        Returns ``None`` while the real provider is not wired up.
        """
        return None
