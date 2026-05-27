from __future__ import annotations


class AkshareSymbolNotFoundError(KeyError):
    pass


class AkshareUpstreamError(RuntimeError):
    pass


class AkshareBreakerOpenError(RuntimeError):
    pass
