from types import SimpleNamespace

from mini3di_search.runtime import RssSampler


def test_denied_process_tree_is_reported_as_incomplete():
    class RestrictedProcess:
        def children(self, recursive):
            raise PermissionError("sandbox denies process enumeration")

        def memory_info(self):
            return SimpleNamespace(rss=123456)

    sampler = RssSampler()
    sampler.process = RestrictedProcess()
    sampler.sample()
    assert sampler.peak == 123456
    assert sampler.rss_reads == 1
    assert sampler.tree_complete is False
    assert sampler.incomplete_samples == 1


def test_readable_process_tree_rss_is_summed():
    child = SimpleNamespace(memory_info=lambda: SimpleNamespace(rss=200))
    sampler = RssSampler()
    sampler.process = SimpleNamespace(
        children=lambda recursive: [child], memory_info=lambda: SimpleNamespace(rss=100)
    )
    sampler.sample()
    assert sampler.peak == 300
    assert sampler.tree_complete is True
    assert sampler.incomplete_samples == 0
