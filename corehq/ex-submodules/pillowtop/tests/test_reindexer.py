import pytest

from ..reindexer.reindexer import (
    PillowChangeProviderReindexer,
    Reindexer,
    ResumableBulkElasticPillowReindexer,
    supports_clean,
)


class NoCleanReindexer(Reindexer):
    def reindex(self):
        pass


class CleanReindexer(NoCleanReindexer):
    def clean(self):
        pass


class NotAReindexer:
    def reindex(self):
        pass


@pytest.mark.parametrize("reindexer_class, expected", [
    (NoCleanReindexer, False),
    (CleanReindexer, True),
    (NotAReindexer, False),
])
def test_supports_clean(reindexer_class, expected):
    assert supports_clean(reindexer_class()) is expected


@pytest.mark.parametrize("reindexer_class, expected", [
    (PillowChangeProviderReindexer, False),
    (ResumableBulkElasticPillowReindexer, True),
])
def test_supports_clean_for_reindexer_classes(reindexer_class, expected):
    reindexer = object.__new__(reindexer_class)
    assert supports_clean(reindexer) is expected
