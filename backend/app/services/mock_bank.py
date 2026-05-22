"""
Mock bank that simulates a payment processor.

Outcome is deterministic based on amount (last digit):
  amount % 10 == 0  →  SUCCESS   (e.g. 1000, 2000)
  amount % 10 == 1  →  DECLINE   (e.g. 1001, 2001)
  amount % 10 == 2  →  TIMEOUT   (e.g. 1002, 2002)
  anything else     →  SUCCESS

This makes tests 100% predictable without any mocking.
"""
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class BankOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    DECLINE = "DECLINE"
    TIMEOUT = "TIMEOUT"


@dataclass
class BankResult:
    outcome: BankOutcome
    failure_reason: str | None = None


def charge(amount: int) -> BankResult:
    """Call the mock bank. Returns a BankResult synchronously."""
    last_digit = amount % 10

    if last_digit == 1:
        logger.info("MockBank: DECLINE amount=%d", amount)
        return BankResult(outcome=BankOutcome.DECLINE, failure_reason="insufficient_funds")

    if last_digit == 2:
        logger.info("MockBank: TIMEOUT amount=%d", amount)
        return BankResult(outcome=BankOutcome.TIMEOUT, failure_reason="bank_timeout")

    logger.info("MockBank: SUCCESS amount=%d", amount)
    return BankResult(outcome=BankOutcome.SUCCESS)
