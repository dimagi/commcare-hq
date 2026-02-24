from unittest.mock import patch

from attrs import define, field

from pillowtop.processors import elastic

from .. import case_search as mod


class TestCaseSearchPillowProcessor:

    def test_process_changes_chunk_excludes_irrelevant_changes(self):
        changes = [FakeChange(0), FakeChange(1), FakeChange(2), FakeChange(3)]
        adapter = FakeAdapter()
        proc = mod.CaseSearchPillowProcessor(adapter)

        def needs_search_index(domain_is_fake_change_id):
            return domain_is_fake_change_id < 3

        with (
            patch.object(mod, 'domain_needs_search_index', needs_search_index),
            patch.object(elastic, 'bulk_fetch_changes_docs', lambda chs: ([], [])),
            patch.object(elastic, 'build_bulk_payload', lambda chs, *args: chs),
        ):
            retries, errors = proc.process_changes_chunk(changes)

            # Parts of change_filter_fn tested:
            # excluded: FakeChange(0).metadata.domain is False-ish
            # excluded: domain_needs_search_index(FakeChange(3).metadata.domain) is False
            assert adapter.bulk_calls == [[FakeChange(1), FakeChange(2)]]
            assert not retries, 'excluded changes should not be retried'
            assert not errors


@define
class FakeChange:
    id = field()
    document = True  # processed by doc_filter_fn, which is noop_filter

    @property
    def metadata(self):
        return FakeMetadata(self.id)


@define
class FakeMetadata:
    domain = field()


@define
class FakeAdapter:
    index_name = "fake"
    bulk_calls = field(factory=list)

    def bulk(self, actions, raise_errors):
        self.bulk_calls.append(actions)
        return len(actions), []
