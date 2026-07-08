from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping, Sequence
from urllib.parse import urlencode

ParamValue = str | int | float | bool | None


def normalize_param(value: ParamValue) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def canonical_query(params: Mapping[str, ParamValue] | Sequence[tuple[str, ParamValue]]) -> str:
    if isinstance(params, Mapping):
        iterable = params.items()
    else:
        iterable = params
    filtered = [(key, normalize_param(value)) for key, value in iterable if value is not None]
    return urlencode(filtered, doseq=False)


def sign_query(query_string: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256).hexdigest()


def signed_query(params: Mapping[str, ParamValue] | Sequence[tuple[str, ParamValue]], secret: str) -> str:
    query = canonical_query(params)
    return f"{query}&signature={sign_query(query, secret)}" if query else f"signature={sign_query('', secret)}"
