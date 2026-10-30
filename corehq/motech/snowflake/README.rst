Data forwarding to Snowflake
============================

CommCare forwards data to Snowflake in a two-step process to optimize
for cost.


Costing in Snowflake
--------------------

Snowflake charges for processing and "staging". In Snowflake vocabulary,
"staging" means storing data before it is "ingested". It is more cost
effective to use "external staging", where data is stored in Amazon S3,
than "internal staging", where data is stored in Snowflake, before it is
ingested.

Processing can be done one record at a time, but ingesting data in
chunks is also more cost effective. Chunk size has a Goldilocks zone of
between 10MB and 100MB. Snowflake will inspect the data, and allocate it
a number of processors, which will process it in parallel.

The staged files that have been ingested will be recognized for 64 days
as having been processed. After that they will be considered new, and
will be ingested again.


Repeater workflow
-----------------

The Repeater sends forms as CSV rows to an S3 bucket. S3 does not offer
the ability to append to a file. (It is possible to use a Kinesis
Firehose delivery stream to send the rows to an AWS S3 bucket. It's
intended for log files. But adding another service to the design does
not seem ideal for our target user.)

A scheduled task, ``trigger_snowflake_ingest()``, runs every month:

1. It creates a new directory for the next month's forms.
2. It triggers Snowflake to ingest the forms in the directory for the
   current month.
3. It deletes the last month's directory.


Other work to do
----------------

This workflow will need a new ``AuthManager`` subclass for Snowflake key
pair authentication, and probably another one for S3 authentication.

Still to be determined: How to add a ``snowflake_connection_settings``
property to the ``SQLSnowflakeS3Repeater`` model. This will depend on
how inheritance works for the ``SQLRepeater`` class; its Couch to SQL
migration is being developed at the time of writing.

We will need clear documentation for administrators to set up S3 and
Snowflake for data forwarding from hQ.

Partners are very likely to want previous form data in Snowflake too.
USH has used Talend to transform data from the Data Export Tool into a
similar CSV format. We could reuse that, or we could write a management
command to do this using data forwarding, which could be useful for
other types of Repeaters too.


Room for improvement
--------------------

The Repeater could manage Snowflake better. Instead of using a scheduled
task for triggering ingestion, the Repeater could check S3 whenever a
form is forwarded, and if the total size crosses a threshold, ingestion
could be triggered.

We could still use a task to ensure that data is ingested after a
maximum of 30 days, if that threshold is not reached. And cancel and
reschedule the task if it is reached.

There are two ways to achieve that.

* The more readable way is to use `django-celery-beat`_ to manage
  scheduled tasks.
* Alternatively, we could use the ``eta`` parameter of
  ``task.apply_async()`` to schedule the task., and to cancel scheduled
  tasks we could do something like this:

  .. code-block:: python

      from corehq.celery import app

      scheduled = app.control.inspect().scheduled().itervalues()
      task_ids = [s["request"]["id"] for s in chain.from_iterable(scheduled)]
      app.control.revoke(task_ids)

  Credit: `StackOverflow`_



.. _django-celery-beat: https://pypi.org/project/django-celery-beat/
.. _StackOverflow: https://stackoverflow.com/a/32383135
