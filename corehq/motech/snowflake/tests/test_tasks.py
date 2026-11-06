from contextlib import contextmanager

from nose.tools import assert_equal

from corehq.celery import app
from corehq.motech.repeaters.models import Repeater
from corehq.motech.snowflake.tasks import (
    cancel_30day_ingest,
    get_task_ids,
    schedule_30day_ingest,
)

DOMAIN_NAME = 'test-domain'


def test_get_task_ids():

    @app.task(name='corehq.motech.snowflake.tasks.trigger_snowflake_ingest')
    def maybe_later():
        pass

    with get_repeater() as repeater:
        task_ids = get_task_ids(repeater, 'filename')
        assert_equal(len(task_ids), 0)

        maybe_later.apply_async(countdown=1)
        task_ids = get_task_ids(repeater, 'filename')
        assert_equal(len(task_ids), 1)


def test_schedule_cancel_30day_ingest():
    with get_repeater() as repeater:
        task_ids = get_task_ids(repeater, 'filename')
        assert_equal(len(task_ids), 0)

        schedule_30day_ingest(repeater, 'filename')
        task_ids = get_task_ids(repeater, 'filename')
        assert_equal(len(task_ids), 1)

        cancel_30day_ingest(repeater, 'filename')
    task_ids = get_task_ids(repeater, 'filename')
    assert_equal(len(task_ids), 0)


@contextmanager
def get_repeater():
    repeater = Repeater(domain=DOMAIN_NAME)
    try:
        yield repeater
    finally:
        repeater.delete()
