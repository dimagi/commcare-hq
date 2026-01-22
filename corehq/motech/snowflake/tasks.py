from datetime import datetime, timedelta
from itertools import chain

from celery.schedules import crontab

from corehq.celery import app  # celery.task.task is deprecated


@app.on_after_configure.connect  # celery.task.periodic_task is deprecated
def setup_periodic_tasks(sender, **kwargs):
    # Trigger ingest at 03:03 on 3rd of the month
    sender.add_periodic_task(
        crontab(hour=3, minute=3, day_of_month=3),
        trigger_snowflake_ingest.s(),
    )


@app.task
def trigger_snowflake_ingest():
    # https://docs.snowflake.com/en/user-guide/python-connector-example.html#copying-data-from-an-external-location
    # con.cursor().execute("""
    # COPY INTO testtable FROM s3://<s3_bucket>/data/
    #     STORAGE_INTEGRATION = myint
    #     FILE_FORMAT=(field_delimiter=',')
    # """.format(
    #     aws_access_key_id=AWS_ACCESS_KEY_ID,
    #     aws_secret_access_key=AWS_SECRET_ACCESS_KEY))
    ...


def schedule_30day_ingest(repeater, filename):
    """
    A zip file of forms on S3 should be ingested by Snowflake no more
    than 30 days after the first form was submitted to CommCare.
    """
    thirty_days = datetime.utcnow() + timedelta(days=30)
    trigger_snowflake_ingest.apply_async(
        (repeater.domain, get_repeater_id(repeater), filename),
        eta=thirty_days,
    )

    # Alternatively, using django_celery_beat
    # from django_celery_beat.models import ClockedSchedule, PeriodicTask
    #
    # schedule, __ = ClockedSchedule.objects.get_or_create(
    #     clocked_time=thirty_days,
    # )
    # args = [repeater.domain, get_repeater_id(repeater), filename]
    # PeriodicTask.objects.create(
    #     clocked=schedule,
    #     name=str(uuid.uuid4()),
    #     task='corehq.motech.snowflake.tasks.trigger_snowflake_ingest',
    #     args=json.dumps(args),
    #     one_off=True,
    # )


def cancel_30day_ingest(repeater, filename):
    """
    A zip file of forms has been ingested because it reached a threshold
    file size. Cancel the scheduled 30-day ingest.
    """
    task_ids = get_task_ids(repeater, filename)
    app.control.revoke(task_ids)


def get_task_ids(repeater, filename):
    # Thank you StackOverflow: https://stackoverflow.com/a/32383135
    scheduled = app.control.inspect().scheduled().itervalues()
    task_ids = [s["request"]["id"] for s in chain.from_iterable(scheduled)]
    # TODO: We only want the ones for this task, this domain, this repeater,
    #       this filename
    return []


# TODO: Remove after Repeaters are migrated to SQL
def get_repeater_id(repeater):
    try:
        return repeater.repeater_id
    except AttributeError:
        return repeater.get_id
