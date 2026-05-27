import pytest
from django.test import RequestFactory, TestCase

from corehq.apps.fixtures.models import (
    Field,
    LookupTable,
    LookupTableRow,
    TypeField,
)
from corehq.apps.integration.payments.filters import (
    LOOKUP_TABLE_TAG_PREFIX,
    ActivityFilter,
    BaseLookupTableFilter,
    BatchNumberFilter,
    CampaignFilter,
    FunderFilter,
    get_lookup_table_values,
)


def _create_table(domain, tag, values, *, column=None, addCleanup=None):
    column = column or tag
    table = LookupTable(
        domain=domain,
        tag=tag,
        fields=[TypeField(column)],
    )
    table.save()
    if addCleanup is not None:
        addCleanup(table.delete)
    for sort_key, value in enumerate(values):
        LookupTableRow(
            domain=domain,
            table=table,
            fields={column: [Field(value=value)]},
            sort_key=sort_key,
        ).save()
    return table


class TestGetLookupTableValues(TestCase):

    domain = 'payments-lookup-values-test'

    def test_returns_empty_when_table_missing(self):
        assert get_lookup_table_values(self.domain, 'payments_batch_number', 'batch_number') == []

    def test_returns_values_in_row_order_with_duplicates(self):
        _create_table(
            self.domain, 'payments_campaign',
            ['Gamma', 'Alpha', 'Beta', 'Alpha'],
            column='campaign', addCleanup=self.addCleanup,
        )
        assert get_lookup_table_values(self.domain, 'payments_campaign', 'campaign') == [
            'Gamma', 'Alpha', 'Beta', 'Alpha',
        ]

    def test_ignores_rows_missing_the_column(self):
        table = _create_table(
            self.domain, 'payments_funder', ['ACME'],
            column='funder', addCleanup=self.addCleanup,
        )
        LookupTableRow(
            domain=self.domain,
            table=table,
            fields={'other_column': [Field(value='ignored')]},
            sort_key=99,
        ).save()
        assert get_lookup_table_values(self.domain, 'payments_funder', 'funder') == ['ACME']


class TestLookupTableFilters(TestCase):

    domain = 'payments-filters-test'

    def _seed(self, case_property, values):
        tag = f'{LOOKUP_TABLE_TAG_PREFIX}{case_property}'
        _create_table(
            self.domain, tag, values,
            column=case_property, addCleanup=self.addCleanup,
        )

    def _build(self, filter_cls):
        request = RequestFactory().get('/')
        return filter_cls(request=request, domain=self.domain, timezone=None)

    def test_batch_number_options_from_lookup_table(self):
        self._seed('batch_number', ['B-2', 'B-1'])
        assert self._build(BatchNumberFilter).options == [('B-1', 'B-1'), ('B-2', 'B-2')]

    def test_campaign_options_from_lookup_table(self):
        self._seed('campaign', ['Vaccination', 'Outreach'])
        assert self._build(CampaignFilter).options == [
            ('Outreach', 'Outreach'),
            ('Vaccination', 'Vaccination'),
        ]

    def test_activity_options_from_lookup_table(self):
        self._seed('activity', ['Door-to-door'])
        assert self._build(ActivityFilter).options == [('Door-to-door', 'Door-to-door')]

    def test_funder_options_from_lookup_table(self):
        self._seed('funder', ['ACME'])
        assert self._build(FunderFilter).options == [('ACME', 'ACME')]

    def test_options_dedupe_and_sort_at_filter(self):
        self._seed('campaign', ['Gamma', 'Alpha', 'Beta', 'Alpha'])
        assert self._build(CampaignFilter).options == [
            ('Alpha', 'Alpha'),
            ('Beta', 'Beta'),
            ('Gamma', 'Gamma'),
        ]

    def test_options_drops_empty_string_values(self):
        self._seed('campaign', ['Alpha', '', 'Beta'])
        assert self._build(CampaignFilter).options == [
            ('Alpha', 'Alpha'),
            ('Beta', 'Beta'),
        ]

    def test_options_empty_when_table_missing(self):
        assert self._build(BatchNumberFilter).options == []
        assert self._build(CampaignFilter).options == []
        assert self._build(ActivityFilter).options == []
        assert self._build(FunderFilter).options == []

    def test_options_empty_when_unprefixed_table_exists(self):
        # A pre-existing 'campaign' table (no payments_ prefix) must not be
        # picked up by CampaignFilter.
        unprefixed = LookupTable(
            domain=self.domain,
            tag='campaign',
            fields=[TypeField('campaign')],
        )
        unprefixed.save()
        self.addCleanup(unprefixed.delete)
        LookupTableRow(
            domain=self.domain,
            table=unprefixed,
            fields={'campaign': [Field(value='Should-Not-Appear')]},
            sort_key=0,
        ).save()
        assert self._build(CampaignFilter).options == []

    def test_subclass_without_slug_raises(self):
        class _MisconfiguredFilter(BaseLookupTableFilter):
            label = 'Misconfigured'

        with pytest.raises(NotImplementedError):
            self._build(_MisconfiguredFilter)
