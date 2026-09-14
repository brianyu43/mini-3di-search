"""Resource bounds and sampled process-tree memory for local search."""

import signal
import threading
from contextlib import contextmanager
from time import perf_counter

import psutil


class RssSampler:
    """Sample current process + descendants; this is not Python-heap-only memory."""

    def __init__(self, interval: float = 0.01) -> None:
        self.interval = interval
        self.peak = 0
        self.samples = 0
        self.incomplete_samples = 0
        self.tree_complete = True
        self.rss_reads = 0
        self.stop = threading.Event()
        self.process = psutil.Process()
        self.worker = threading.Thread(target=self._run, daemon=True)

    def sample(self) -> None:
        try:
            processes = [self.process, *self.process.children(recursive=True)]
        except (psutil.Error, OSError):
            processes = [self.process]
            self.incomplete_samples += 1
            self.tree_complete = False
        rss = 0
        for process in processes:
            try:
                rss += process.memory_info().rss
                self.rss_reads += 1
            except (psutil.Error, OSError):
                self.incomplete_samples += 1
                self.tree_complete = False
        self.peak = max(self.peak, rss)
        self.samples += 1

    def _run(self) -> None:
        while not self.stop.wait(self.interval):
            self.sample()

    def __enter__(self):
        self.sample()
        self.worker.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.worker.join()
        self.sample()


@contextmanager
def bounded():
    began = perf_counter()
    with RssSampler(0.05) as memory:

        def guard(signum, frame):
            if perf_counter() - began > 900 or memory.peak > 8 * 1024**3:
                raise RuntimeError("search exceeded 900s or 8GiB process-tree RSS budget")

        old = signal.signal(signal.SIGALRM, guard)
        signal.setitimer(signal.ITIMER_REAL, 1, 1)
        try:
            yield memory
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)


def memory_report(memory):
    return {
        "sampled_peak_rss_bytes": memory.peak,
        "process_tree_complete": memory.tree_complete,
        "samples": memory.samples,
        "sample_interval_seconds": memory.interval,
        "scope": "current process and descendants; sample maximum can miss peaks",
        "sampler_threads": 1,
        "compute_threads": 1,
    }
