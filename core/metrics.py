"""
Lightweight Prometheus-compatible metrics — no external dependency.

Exposes counters, histograms, and gauges via /metrics in text exposition format.
Thread-safe using threading.Lock.
"""
import threading
import time
from collections import defaultdict


class Metrics:
    def __init__(self):
        self._lock = threading.Lock()
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = defaultdict(float)
        self._histograms: dict[str, list[float]] = defaultdict(list)

    def inc_counter(self, name: str, value: float = 1, labels: dict | None = None):
        key = self._labeled_key(name, labels)
        with self._lock:
            self._counters[key] += value

    def set_gauge(self, name: str, value: float, labels: dict | None = None):
        key = self._labeled_key(name, labels)
        with self._lock:
            self._gauges[key] = value

    def observe_histogram(self, name: str, value: float, labels: dict | None = None):
        key = self._labeled_key(name, labels)
        with self._lock:
            self._histograms[key].append(value)

    def time_histogram(self, name: str, labels: dict | None = None):
        """Context manager / decorator to time a block and record in histogram."""
        return _Timer(self, name, labels)

    def expose(self) -> str:
        with self._lock:
            lines = []
            for key, val in sorted(self._counters.items()):
                base = key.split("{")[0]
                lines.append(f"# TYPE {base} counter")
                lines.append(f"{key} {val}")
            for key, val in sorted(self._gauges.items()):
                base = key.split("{")[0]
                lines.append(f"# TYPE {base} gauge")
                lines.append(f"{key} {val}")
            for key, values in sorted(self._histograms.items()):
                base = key.split("{")[0]
                lines.append(f"# TYPE {base} summary")
                if values:
                    sorted_v = sorted(values)
                    count = len(sorted_v)
                    total = sum(sorted_v)
                    lines.append(f'{key}_sum {total}')
                    lines.append(f'{key}_count {count}')
                    for q in (0.5, 0.9, 0.95, 0.99):
                        idx = min(int(count * q), count - 1)
                        lines.append(f'{key}{{quantile="{q}"}} {sorted_v[idx]}')
            return "\n".join(lines) + "\n"

    def _labeled_key(self, name: str, labels: dict | None = None) -> str:
        if labels:
            pairs = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
            return f'{name}{{{pairs}}}'
        return name


class _Timer:
    def __init__(self, metrics: Metrics, name: str, labels: dict | None = None):
        self._m = metrics
        self._name = name
        self._labels = labels
        self._start = 0.0

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, *args):
        elapsed = (time.monotonic() - self._start) * 1000
        self._m.observe_histogram(self._name, elapsed, self._labels)


metrics = Metrics()
