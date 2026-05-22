"""
Webhook delivery worker — transactional outbox consumer.

Polls the webhook_events table for PENDING events and delivers them
to each merchant's webhook_url via HTTP POST.

Retry schedule with ±20% jitter (attempt_count is 0-indexed at time of failure):
  After attempt 1 failure → wait ~10s   (next_attempt_at = now + 10s ± 2s)
  After attempt 2 failure → wait ~30s
  After attempt 3 failure → wait ~120s  (2 min)
  After attempt 4 failure → wait ~600s  (10 min)
  After attempt 5 failure → mark FAILED permanently

Run this as a separate process:
  python -m app.worker.webhook_worker
"""
import json
import logging
import random
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

import requests

from app.core.config import settings
from app.core.database import get_conn, init_pool
from app.services.webhook_service import sign_payload

logger = logging.getLogger(__name__)

# Backoff delays in seconds for each attempt index (0-based)
_BACKOFF_SECONDS = [10, 30, 120, 600]
_JITTER_FACTOR = 0.2  # ±20%


def _backoff_with_jitter(attempt_count: int) -> float:
    """Return seconds to wait before the next attempt, with ±20% jitter."""
    base = _BACKOFF_SECONDS[min(attempt_count, len(_BACKOFF_SECONDS) - 1)]
    jitter = base * _JITTER_FACTOR * (2 * random.random() - 1)
    return max(1.0, base + jitter)


def fetch_pending_events(conn) -> list[dict]:
    """Fetch events that are due for delivery, oldest first."""
    now = datetime.now(tz=timezone.utc)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                we.id, we.payment_intent_id, we.merchant_id,
                we.event_type, we.payload, we.status,
                we.attempt_count, we.next_attempt_at,
                m.webhook_url
            FROM webhook_events we
            JOIN merchants m ON m.id = we.merchant_id
            WHERE we.status = 'PENDING'
              AND we.next_attempt_at <= %s
              AND m.webhook_url IS NOT NULL
            ORDER BY we.next_attempt_at ASC
            LIMIT 50
            """,
            (now,),
        )
        return cur.fetchall()


def deliver_event(conn, event: dict) -> None:
    """
    Attempt to deliver one webhook event.
    Updates the event row based on outcome — success or retry/fail.
    """
    event_id = event["id"]
    merchant_id = event["merchant_id"]
    webhook_url = event["webhook_url"]
    attempt_count = event["attempt_count"]

    payload = event["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    payload_json = json.dumps(payload, sort_keys=True)

    signature = sign_payload(UUID(str(merchant_id)), payload_json)
    headers = {
        "Content-Type": "application/json",
        "X-LedgerPay-Signature": signature,
        "X-LedgerPay-Event": event["event_type"],
    }

    try:
        resp = requests.post(webhook_url, data=payload_json, headers=headers, timeout=10)
        resp.raise_for_status()
        _mark_delivered(conn, event_id)
        logger.info("Webhook delivered event_id=%s attempt=%d", event_id, attempt_count + 1)

    except Exception as exc:
        new_attempt_count = attempt_count + 1
        if new_attempt_count >= settings.webhook_max_attempts:
            _mark_failed(conn, event_id, new_attempt_count)
            logger.warning(
                "Webhook permanently failed event_id=%s after %d attempts: %s",
                event_id, new_attempt_count, exc,
            )
        else:
            delay = _backoff_with_jitter(new_attempt_count)
            next_attempt = datetime.now(tz=timezone.utc) + timedelta(seconds=delay)
            _schedule_retry(conn, event_id, new_attempt_count, next_attempt)
            logger.warning(
                "Webhook delivery failed event_id=%s attempt=%d retry_in=%.1fs: %s",
                event_id, new_attempt_count, delay, exc,
            )


def _mark_delivered(conn, event_id) -> None:
    now = datetime.now(tz=timezone.utc)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE webhook_events
            SET status = 'DELIVERED', delivered_at = %s
            WHERE id = %s
            """,
            (now, str(event_id)),
        )


def _mark_failed(conn, event_id, attempt_count: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE webhook_events
            SET status = 'FAILED', attempt_count = %s
            WHERE id = %s
            """,
            (attempt_count, str(event_id)),
        )


def _schedule_retry(conn, event_id, attempt_count: int, next_attempt_at: datetime) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE webhook_events
            SET attempt_count = %s, next_attempt_at = %s
            WHERE id = %s
            """,
            (attempt_count, next_attempt_at, str(event_id)),
        )


def run_once(conn) -> int:
    """Process one batch of pending events. Returns the number processed."""
    events = fetch_pending_events(conn)
    for event in events:
        deliver_event(conn, event)
        conn.commit()
    return len(events)


def run_forever() -> None:
    """Main worker loop. Polls every WEBHOOK_WORKER_POLL_INTERVAL seconds."""
    init_pool()
    logger.info(
        "Webhook worker started — poll_interval=%ds max_attempts=%d",
        settings.webhook_worker_poll_interval,
        settings.webhook_max_attempts,
    )
    while True:
        try:
            with get_conn() as conn:
                processed = run_once(conn)
            if processed:
                logger.info("Worker processed %d webhook event(s)", processed)
        except Exception as exc:
            logger.exception("Worker loop error: %s", exc)
        time.sleep(settings.webhook_worker_poll_interval)


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    run_forever()
