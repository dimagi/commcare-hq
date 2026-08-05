from datetime import date, datetime

import pytest
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db import connections, router

from corehq.util.metrics.tests.utils import capture_metrics

from ..tasks import (
    MODELS_TO_PRUNE,
    _get_partitions_to_drop,
    prune_auditcare_tables,
)
from .testutils import AuditcareTest

BASE_TABLE = 'auditcare_accessaudit'


def test_no_partitions_means_nothing_to_drop():
    partitions_to_drop = _get_partitions_to_drop([], BASE_TABLE, date(2030, 1, 1))
    assert partitions_to_drop == []


@pytest.mark.parametrize(
    'table_name',
    [
        BASE_TABLE,  # the parent table itself
        'auditcare_navigationeventaudit_y2020m01',  # the other model's partition
        'phone_synclogsql_y2020w01',  # an unrelated partitioned table
        f'{BASE_TABLE}_y2020m1',  # month not zero padded
        f'{BASE_TABLE}_y20m01',  # two digit year
        f'{BASE_TABLE}_y2020m01_backup',  # a manual copy of a partition
        f'{BASE_TABLE}_y2020w01',  # weekly rather than monthly
        f'{BASE_TABLE}_null',  # architect's partition for null event_date
    ],
)
def test_ignores_tables_that_are_not_monthly_partitions(table_name):
    partitions_to_drop = _get_partitions_to_drop([table_name], BASE_TABLE, date(2030, 1, 1))
    assert partitions_to_drop == []


def test_partition_containing_the_cutoff_is_kept():
    existing = [f'{BASE_TABLE}_y2020m06']
    partitions_to_drop = _get_partitions_to_drop(existing, BASE_TABLE, date(2020, 6, 15))
    assert partitions_to_drop == []


def test_partition_containing_the_cutoff_is_kept_when_cutoff_is_first_of_month():
    existing = [f'{BASE_TABLE}_y2020m06']
    partitions_to_drop = _get_partitions_to_drop(existing, BASE_TABLE, date(2020, 6, 1))
    assert partitions_to_drop == []


def test_partition_one_month_before_the_cutoff_is_dropped():
    existing = [f'{BASE_TABLE}_y2020m05']
    partitions_to_drop = _get_partitions_to_drop(existing, BASE_TABLE, date(2020, 6, 15))
    assert partitions_to_drop == [f'{BASE_TABLE}_y2020m05']


def test_partition_one_month_after_the_cutoff_is_kept():
    existing = [f'{BASE_TABLE}_y2020m07']
    partitions_to_drop = _get_partitions_to_drop(existing, BASE_TABLE, date(2020, 6, 15))
    assert partitions_to_drop == []


def test_cutoff_in_january_drops_the_previous_december():
    existing = [
        f'{BASE_TABLE}_y2019m12',
        f'{BASE_TABLE}_y2020m01',
    ]
    partitions_to_drop = _get_partitions_to_drop(existing, BASE_TABLE, date(2020, 1, 10))
    assert partitions_to_drop == [f'{BASE_TABLE}_y2019m12']


def test_drops_every_month_older_than_the_cutoff():
    existing = [
        f'{BASE_TABLE}_y2018m11',
        f'{BASE_TABLE}_y2018m12',
        f'{BASE_TABLE}_y2019m01',
        f'{BASE_TABLE}_y2019m06',
        f'{BASE_TABLE}_y2019m07',  # the cutoff month
        f'{BASE_TABLE}_y2019m08',
        f'{BASE_TABLE}_y2020m01',
    ]
    partitions_to_drop = _get_partitions_to_drop(existing, BASE_TABLE, date(2019, 7, 20))
    assert partitions_to_drop == [
        f'{BASE_TABLE}_y2018m11',
        f'{BASE_TABLE}_y2018m12',
        f'{BASE_TABLE}_y2019m01',
        f'{BASE_TABLE}_y2019m06',
    ]


def test_matches_partitions_of_the_model_it_was_given():
    existing = [
        'auditcare_navigationeventaudit_y2018m01',
        f'{BASE_TABLE}_y2018m01',
    ]
    base_table = 'auditcare_navigationeventaudit'
    partitions_to_drop = _get_partitions_to_drop(existing, base_table, date(2026, 1, 1))
    assert partitions_to_drop == ['auditcare_navigationeventaudit_y2018m01']


class TestPruneAuditcarePartitions(AuditcareTest):
    def test_drops_only_partitions_older_than_the_retention_period(self):
        cutoff = date.today() - relativedelta(
            years=settings.AUDITCARE_RETENTION_YEARS
        )
        # two expired dates, so the task has to drop more than one partition
        expired_dates = [
            datetime(cutoff.year - 3, 1, 15),
            datetime(cutoff.year - 1, 7, 15),
        ]
        retained_date = datetime.utcnow()
        for model in MODELS_TO_PRUNE:
            model.objects.bulk_create(
                [
                    model(user='melvin@test.com', event_date=event_date)
                    for event_date in expired_dates + [retained_date]
                ]
            )
        tables_before = {
            model: self.get_partition_tables(model)
            for model in MODELS_TO_PRUNE
        }

        with capture_metrics() as metrics:
            prune_auditcare_tables()

        for model in MODELS_TO_PRUNE:
            remaining = self.get_partition_tables(model)
            dropped = tables_before[model] - remaining
            assert self.partitions_for(model, expired_dates) == dropped
            assert self.partitions_for(model, [retained_date]) == remaining
            assert model.objects.filter(event_date=retained_date).exists()
            assert not model.objects.filter(
                event_date__in=expired_dates
            ).exists()
            assert metrics.sum(
                'commcare.auditcare.partitions_dropped', model=model.__name__
            ) == len(dropped)

    def get_partition_tables(self, model):
        db = router.db_for_write(model)
        with connections[db].cursor() as cursor:
            cursor.execute(
                'SELECT tablename FROM pg_tables WHERE tablename LIKE %s',
                [f'{model._meta.db_table}_%'],
            )
            return {row[0] for row in cursor.fetchall()}

    def partitions_for(self, model, event_dates):
        return {
            f'{model._meta.db_table}_y{d.year}m{d.month:02d}'
            for d in event_dates
        }
