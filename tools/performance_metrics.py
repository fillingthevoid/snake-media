"""Small in-memory CPU and physical-network sampler; no privileged operations."""
from collections import deque
import math
from pathlib import Path
import re
import threading
import time


def cpu_counters(text):
    row = text.splitlines()[0].split()
    if len(row) < 9 or row[0] != 'cpu':
        raise ValueError('invalid_cpu_counters')
    values = tuple(int(value) for value in row[1:9])
    if any(value < 0 for value in values):
        raise ValueError('invalid_cpu_counters')
    # Guest/guest_nice are included in user/nice already.
    return values


def cpu_usage(before, after):
    delta = [b - a for a, b in zip(before, after)]
    total = sum(delta)
    if len(delta) != 8 or any(value < 0 for value in delta) or total <= 0:
        raise ValueError('reset_cpu_counters')
    return 100 * (total - delta[3] - delta[4]) / total


class PerformanceSampler:
    def __init__(self, stat='/proc/stat', net='/sys/class/net'):
        self.stat = Path(stat)
        self.net = Path(net)
        self.lock = threading.Lock()
        self.previous_cpu = None
        self.history = deque(maxlen=64)
        self.latest_cpu = {'available': False}
        self.latest_network = {'available': False}
        self.when = None
        self.stop_event = threading.Event()

    def network_counters(self):
        interfaces = sorted(p.name for p in self.net.iterdir()
            if (p / 'device').exists() and (p / 'operstate').read_text().strip() == 'up')
        if not interfaces or any(not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}', name) for name in interfaces):
            raise ValueError('network_unavailable')
        counters = {name: int((self.net / name / 'statistics/tx_bytes').read_text()) for name in interfaces}
        if any(value < 0 for value in counters.values()):
            raise ValueError('invalid_network_counters')
        return counters

    def tick(self, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            elapsed = None if self.when is None else now - self.when
            if not math.isfinite(now) or elapsed is not None and not 0 < elapsed <= 10:
                self.previous_cpu = None
                self.history.clear()
            self.latest_cpu = {'available': False}
            try:
                current = cpu_counters(self.stat.read_text())
                if self.previous_cpu is not None:
                    try:
                        usage = cpu_usage(self.previous_cpu, current)
                        self.latest_cpu = {'available': True, 'usagePercent': usage, 'sampleSeconds': elapsed}
                    except ValueError:
                        pass
                self.previous_cpu = current
            except Exception:
                self.previous_cpu = None
            self.latest_network = {'available': False}
            try:
                counters = self.network_counters()
                if self.history and (counters.keys() != self.history[-1][1].keys()
                    or any(counters[n] < self.history[-1][1][n] for n in counters)):
                    self.history.clear()
                if self.history:
                    previous_time, previous = self.history[-1]
                    seconds = now - previous_time
                    rate = sum(counters[n] - previous[n] for n in counters) * 8 / seconds / 1000000
                    self.latest_network = {'available': True, 'interface': ', '.join(counters),
                        'uploadMbps': rate, 'sampleSeconds': seconds, 'uploadAverageMbps': None, 'averageSeconds': 0}
                self.history.append((now, counters))
                while len(self.history) > 2 and self.history[1][0] <= now - 60:
                    self.history.popleft()
                oldest_time, oldest = self.history[0]
                coverage = now - oldest_time
                if self.latest_network['available'] and coverage >= 60:
                    self.latest_network.update(uploadAverageMbps=sum(counters[n] - oldest[n] for n in counters) * 8 / coverage / 1000000,
                        averageSeconds=coverage)
            except Exception:
                self.history.clear()
            self.when = now

    def snapshot(self, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            if self.when is None or not 0 <= now - self.when <= 6:
                return {'cpu': {'available': False}, 'network': {'available': False}}
            return {'cpu': dict(self.latest_cpu), 'network': dict(self.latest_network)}

    def start(self):
        def run():
            while not self.stop_event.is_set():
                self.tick()
                self.stop_event.wait(2)
        threading.Thread(target=run, name='performance-sampler', daemon=True).start()
