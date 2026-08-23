"""A shared token bucket, because thread-pool width alone does not bound the
request rate.

Measured on a real 49-pilot local: 8 worker threads produced 20 req/s to
zKillboard, because most pilots answer in well under a second and the pool
simply cycles faster. The verified-safe sustained figure is ~8-10 req/s, and
the penalty for exceeding it is an IP ban of up to an hour, so the rate is
capped explicitly rather than left as an emergent property of the pool size.
"""
from __future__ import annotations

import threading
import time


class TokenBucket:
    def __init__(self, rate: float, burst: float | None = None):
        self.rate = float(rate)
        self.capacity = float(burst if burst is not None else rate)
        self._tokens = self.capacity
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def take(self, tokens: float = 1.0) -> float:
        """Block until `tokens` are available. Returns seconds waited."""
        waited = 0.0
        while True:
            with self._lock:
                now = time.monotonic()
                self._tokens = min(self.capacity,
                                   self._tokens + (now - self._last) * self.rate)
                self._last = now
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return waited
                deficit = tokens - self._tokens
                sleep_for = deficit / self.rate
            time.sleep(sleep_for)
            waited += sleep_for


# 8 req/s sustained is what was verified across hundreds of requests without a
# single 429. The burst allowance lets a small local finish snappily.
zkb_bucket = TokenBucket(rate=8.0, burst=12.0)

# CCP's public image CDN. A separate bucket on purpose: sharing zkb's would let
# an icon prefetch eat the killboard's budget, and the price there is an
# hour-long IP ban (invariant 3). Icons are a one-time cost -- 76 files on a
# fresh install -- so this rate is about being polite, not about throughput.
images_bucket = TokenBucket(rate=8.0, burst=12.0)
