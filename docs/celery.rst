======
Celery
======

Official Celery documentation: http://docs.celeryproject.org/en/latest/
What is it ==========

Celery is a library we use to perform tasks outside the bounds of an HTTP request.


How to use celery
=================

All celery tasks should go into a tasks.py file or tasks module in a django app.
This ensures that ``autodiscover_tasks`` can find the task and register it with the celery workers.

These tasks should be decorated with one of the following:

1. ``@task`` defines a task that is called manually (with ``task_function_name.delay`` in code)
2. ``@periodic_task`` defines a task that is called at some interval (specified by ``crontab`` in the decorator)
3. ``@serial_task`` defines a task that should only ever have one job running at one time


Best practices
==============

Do not pass objects to celery.
Instead, IDs can be passed and the celery task can retrieve the object from the database using the ID.
This keeps message lengths short and reduces burden on RabbitMQ as well as preventing tasks from operating on stale data.

Do not specify ``serializer='pickle'`` for new tasks.
This is a deprecated message serializer and by default, we now use JSON.

Queues
======
.. csv-table:: Queues
    :header: Queue,I/O Bound?,Target max time-to-start,Target max time-to-start comments,Description of usage,How long does the typical task take to complete?,Best practices / Notes

    send_report_throttled,,hours,"30 minutes: reports should be sent as close to schedule as possible.
    EDIT: this queue only affects mvp-* and ews-ghana",This is used specifically for domains who are abusing Scheduled Reports and overwhelming the background queue.  See settings.THROTTLE_SCHED_REPORTS_PATTERNS,,
    submission_reprocessing_queue,no?,hours,1 hour: not critical if this gets behind as long as it can keep up within a few hours,Reprocess form submissions that errored in ways that can be handled by HQ. Triggered by 'submission_reprocessing_queue' process.,seconds,
    sumologic_logs_queue,yes,hours,1 hour: OK for this to get behind,Forward device logs to sumologic. Triggered by device log submission from mobile.,seconds,Non-essential queue
    analytics_queue,yes,minutes,,Used to run tasks related to external analytics tools like HubSpot. Triggered by user actions on the site.,instantaneous (seconds),
    reminder_case_update_queue,,minutes,,Run reminder tasks related to case changes. Triggered by case change signal.,seconds,
    reminder_queue,yes,minutes,15 minutes: since these are scheduled it can be important for them to get triggered on time,Runs the reminder rule tasks for reminders that are due. Triggered by the 'queue_scheduled_instances' process.,seconds,
    reminder_rule_queue,,minutes,,Run messaging rules after changes to rules. Triggered by changes to rules.,minutes / hours,
    repeat_record_queue,,minutes,ideally minutes but might be ok if it gets behind during peak,Run tasks for repeaters. Triggered by repeater queue process.,seconds,
    sms_queue,yes,minutes,5 minutes?: depends largely on the messaging. Some messages are more time sensitive than others. We don't have a way to tell so ideally they should all go out ASAP.,Used to send SMSs that have been queued. Triggered by 'run_sms_queue' process.,seconds,
    async_restore_queue,no,seconds,,Generate restore response for mobile phones. Gets triggered for sync requests that have async restore flag.,,
    case_import_queue,,seconds,,Run case imports,minutes / hours,
    email_queue,yes,seconds,"generally seconds, since people often blocked on receiving the email (registration workflows for example)",Send emails.,seconds,
    export_download_queue,,seconds,seconds / minutes,Used for manually-triggered exports,minutes,
    icds_dashboard_reports_queue,,seconds,fast,,,
    background_queue,,,,,varies wildly,
    beat,N/A,,,,,
    case_rule_queue,,,,Run case update rules. Triggered by schedule,minutes / hours,
    celery,,,,,,
    celery_periodic,,,,,"Invoice generation: ~2 hours on production.  Runs as a single task, once per month.","I think this is one of the trickiest ones (and most heterogenous) because we run lots of scheduled tasks, that we expect to happen at a certain time, some of which we want at exactly that time and some we are ok with delay in start."
    flower,N/A,,,,,
    icds_aggregation_queue,yes,,initial task is immediate. follow up tasks are constrained by performance of previous tasks. recommend not tracking,Run aggregation tasks for ICDS. Triggered by schedule.,,
    ils_gateway_sms_queue,,,,Custom queue for sending SMS for ILS Gateway project,,
    logistics_background_queue,,,,Custom queue,,
    logistics_reminder_queue,,,,Custom queue,,
    saved_exports_queue,,,,Used only for regularly scheduled exports. Triggered by schedule.,minutes,"This queue is used only for regularly scheduled exports, which are not user-triggered. The time taken to process a saved export depends on the export itself. We now save the time taken to run the saved export as last_build_duration which can be used to monitor or move the task to a different queue that handles big tasks. Since all exports are triggered at the same time (midnight UTC) the queue gets big. Could be useful to spread these out so that the exports are generated at midnight in the TZ of the domain (see callcenter tasks for where this is already done)"
    ucr_indicator_queue,no,,,Used for ICDS very expensive UCRs to aggregate,,
    ucr_queue,no,,,Used to rebuild UCRs,minutes to hours,"This is where UCR data source rebuilds occur. Those have an extremely large variation. May be best to split those tasks like ""Process 1000 forms/cases, then requeue"" so as to not block"



Soil
====

Soil is a Dimagi utility to provide downloads that are backed by celery.

To use soil:

.. code-block:: python

    from soil import DownloadBase
    from soil.progress import update_task_state
    from soil.util import expose_cached_download

    @task
    def my_cool_task():
        DownloadBase.set_progress(my_cool_task, 0, 100)

        # do some stuff

        DownloadBase.set_progress(my_cool_task, 50, 100)

        # do some more stuff

        DownloadBase.set_progress(my_cool_task, 100, 100)

        expose_cached_download(payload, expiry, file_extension)

For error handling update the task state to failure and provide errors, HQ currently supports two options:

Option 1
--------

This option raises a celery exception which tells celery to ignore future state updates.
The resulting task result will not be marked as "successful" so ``task.successful()`` will return ``False``
If calling with ``CELERY_ALWAYS_EAGER = True`` (i.e. a dev environment), and with ``.delay()``,
the exception will be caught by celery and ``task.result`` will return the exception.

.. code-block:: python

    from celery.exceptions import Ignore
    from soil import DownloadBase
    from soil.progress import update_task_state
    from soil.util import expose_cached_download

    @task
    def my_cool_task():
        try:
            # do some stuff
        except SomeError as err:
            errors = [err]
            update_task_state(my_cool_task, states.FAILURE, {'errors': errors})
            raise Ignore()

Option 2
--------

This option raises an exception which celery does not catch.
Soil will catch this and set the error to the error message in the exception.
The resulting task will be marked as a failure meaning ``task.failed()`` will return ``True``
If calling with ``CELERY_ALWAYS_EAGER = True`` (i.e. a dev environment), the exception will "bubble up" to the calling code.

.. code-block:: python

    from soil import DownloadBase
    from soil.progress import update_task_state
    from soil.util import expose_cached_download

    @task
    def my_cool_task():
        # do some stuff
        raise SomeError("my uncool error")

Testing
=======

As noted in the [celery docs](http://docs.celeryproject.org/en/v4.2.1/userguide/testing.html) testing tasks in celery is not the same as in production.
In order to test effectively, mocking is required.

An example of mocking with Option 1 from the soil documentation:

.. code-block:: python

    @patch('my_cool_test.update_state')
    def my_cool_test(update_state):
        res = my_cool_task.delay()
        self.assertIsInstance(res.result, Ignore)
        update_state.assert_called_with(
            state=states.FAILURE,
            meta={'errors': ['my uncool errors']}
        )

Other references
================
https://docs.google.com/presentation/d/1iiiVZDiOGXoLeTvEIgM_rGgw6Me5_wM_Cyc64bl7zns/edit#slide=id.g1d621cb6fc_0_372

https://docs.google.com/spreadsheets/d/10uv0YBVTGi88d6mz6xzwXRLY5OZLW1FJ0iarHI6Orck/edit?ouid=112475836275787837666&usp=sheets_home&ths=true
