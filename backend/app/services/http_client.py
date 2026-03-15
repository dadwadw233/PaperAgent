import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx


RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


@dataclass
class ExternalServiceError(RuntimeError):
    category: str
    message: str
    status_code: Optional[int] = None
    snapshot: Optional[str] = None
    retryable: bool = False

    def __str__(self) -> str:
        status = f" status={self.status_code}" if self.status_code is not None else ""
        snippet = f" snapshot={self.snapshot}" if self.snapshot else ""
        return f"{self.category}:{status} {self.message}{snippet}".strip()


def post_json_with_retry(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout: float,
    retries: int = 2,
    backoff_seconds: float = 0.8,
) -> Dict[str, Any]:
    last_error: Optional[ExternalServiceError] = None
    for attempt in range(retries + 1):
        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=timeout)
            if not resp.is_success:
                snapshot = (resp.text or "")[:500]
                retryable = resp.status_code in RETRYABLE_STATUS_CODES
                err = ExternalServiceError(
                    category="http_status",
                    message=f"Upstream returned {resp.status_code}",
                    status_code=resp.status_code,
                    snapshot=snapshot,
                    retryable=retryable,
                )
                if retryable and attempt < retries:
                    time.sleep(backoff_seconds * (attempt + 1))
                    continue
                raise err
            try:
                return resp.json()
            except Exception as exc:
                raise ExternalServiceError(
                    category="invalid_json",
                    message=f"Response is not valid JSON: {exc}",
                    snapshot=(resp.text or "")[:500],
                    retryable=False,
                ) from exc
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout) as exc:
            last_error = ExternalServiceError(
                category="timeout",
                message=str(exc),
                retryable=True,
            )
            if attempt < retries:
                time.sleep(backoff_seconds * (attempt + 1))
                continue
            break
        except httpx.RequestError as exc:
            last_error = ExternalServiceError(
                category="network_error",
                message=str(exc),
                retryable=True,
            )
            if attempt < retries:
                time.sleep(backoff_seconds * (attempt + 1))
                continue
            break
        except ExternalServiceError as exc:
            last_error = exc
            if exc.retryable and attempt < retries:
                time.sleep(backoff_seconds * (attempt + 1))
                continue
            break

    if last_error:
        raise last_error
    raise ExternalServiceError(category="unknown_error", message="Request failed for unknown reason")
