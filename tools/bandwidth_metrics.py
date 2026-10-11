"""Read disposable destination counters without network privileges."""
from collections import deque
import json
import math
from pathlib import Path
import time

CATEGORIES = ('lan', 'internet', 'other')


class SplitSampler:
    def __init__(self, path='/run/snake-network/counters.json'):
        self.path = Path(path)
        self.history = deque(maxlen=64)
        self.generation = None
        self.latest = {'available': False}

    def read(self, now=None):
        now = time.time() if now is None else now
        try:
            if self.path.stat().st_size > 16384:
                raise ValueError('oversized_counters')
            data = json.loads(self.path.read_text())
            stamp, generation, counters = data['sampledAt'], data['generation'], data['counters']
            if (data['version'] != 1 or not isinstance(generation, str) or not 1 <= len(generation) <= 128
                or not isinstance(stamp, (int, float)) or isinstance(stamp, bool)
                or not math.isfinite(stamp) or not -1 <= now - stamp <= 6
                or set(counters) != set(CATEGORIES)
                or any(type(counters[k]) is not int or not 0 <= counters[k] < 2**64 for k in CATEGORIES)):
                raise ValueError('invalid_counters')
            if self.history:
                previous_time, previous = self.history[-1]
                if generation == self.generation and stamp == previous_time and counters == previous:
                    return dict(self.latest)
                if (generation != self.generation or not 0 < stamp - previous_time <= 10
                    or any(counters[k] < previous[k] for k in CATEGORIES)):
                    self.history.clear()
            self.generation = generation
            result = {'available': False}
            if self.history:
                t, old = self.history[-1]
                result = {'available': True, 'sampleSeconds': stamp-t, 'averageSeconds': 0}
                for k in CATEGORIES:
                    result[k+'Mbps'] = (counters[k]-old[k])*8/(stamp-t)/1000000
                    result[k+'AverageMbps'] = None
            self.history.append((stamp, counters))
            while len(self.history) > 2 and self.history[1][0] <= stamp - 60:
                self.history.popleft()
            coverage = stamp - self.history[0][0]
            if result['available'] and coverage >= 60:
                result['averageSeconds'] = coverage
                for k in CATEGORIES:
                    result[k+'AverageMbps'] = (counters[k]-self.history[0][1][k])*8/coverage/1000000
            self.latest = result
            return dict(result)
        except (OSError, ValueError, TypeError, KeyError, OverflowError):
            self.history.clear()
            self.latest = {'available': False}
            return dict(self.latest)
