=======
Pillows
=======

Overview
========

What are pillows
----------------
Pillows are a component of the publisher/subscriber design pattern that
is used for asynchronous communication. A pillow subscribes to a change feed,
and when changes are received, performs specific operations related to that change.

Why do we need pillows
----------------------
In CommCare HQ, pillows are primarily used to update secondary databases like
Elasticsearch and User Configurable Reports (UCRs). Some other use cases
are invalidating cache or checking if alerts need to be sent.

How do pillows receive changes
------------------------------
We use Kafka as the message queue. Producers send changes to Kafka, and
consumers (i.e. pillows) listen to those changes and process them. Kafka uses
*topics* to organize related changes, and pillows listen for changes to
one or more topics.

Why the name
------------
Pillows were initially created to process changes specifically from CouchDB. The
idea was that "pillows" sit on top of the "couch". Our usage of pillows has since
expanded beyond Couch, making this name a historical artifact.

Deconstructing a Pillow
=======================

All pillows inherit from the `ConstructedPillow` class. A pillow consists of a
few parts:

1. Change Feed
2. Checkpoint
3. Processor(s)
4. Change Event Handler

Change Feed
-----------
An instance of a `ChangeFeed` class is created and configured to only contain
changes the pillow cares about when setting up a pillow.

For more information about change feeds, see :ref:`Change Feeds`.

Checkpoint
----------

The checkpoint is a JSON field that tells the processor where to start reading
from the change feed.

Processors
----------

A processor operates on the incoming change. For example, the case pillow
has multiple processors, one to send case changes to elasticsearch, another
to update UCR datasources, etc.

Historically, we had one processor per pillow, however we now favor multiple
processors per pillow. This is due to the large memory consumption of
a pillow process, and wanting to minimize how many pillow processes we need to run.

Change Event Handler
--------------------

This fires after each change has been processed. The main use case is to save
checkpoints to the database.

Error Handling
==============

Errors
------
Pillows can fail to process a change for a number of reasons. The most common
causes of pillow errors are a code bug, or a failure in a dependent service
(e.g., attempting to save a change to Elasticsearch but it is unreachable). If
errors are encountered in processors, a `PillowError` is created.

Retries
--------
The `run_pillow_retry_queue` command is configured to run continuously on a
pillow machine, and looks for new `PillowError` objects to retry. A pillow has the
option to disable retrying errors via the `retry_errors` property.

Monitoring
==========

There are several datadog metrics with the prefix `commcare.change_feed` that
can be helpful for monitoring pillows. Generally these metrics will have tags
for pillow name, topic, and partition to filter on.

.. list-table::
   :header-rows: 1

   * - Metric (not including commcare.change_feed)
     - Description
   * - change_lag
     - The current time - when the last change processed was put into the queue
   * - changes.count
     - Number of changes processed
   * - changes.success
     - Number of changes processed successfully
   * - changes.exceptions
     - Number of changes processed with an exception
   * - processor.timing
     - Time spent in processing a document.
       Different tags for extract/transform/load steps.
   * - processed_offsets
     - Latest offset that has been processed by the pillow
   * - current_offsets
     - The current offsets of each partition in kafka (useful for math in dashboards)
   * - need_processing
     - current_offsets - processed_offsets

Generally when planning for pillows, you should:
    - Minimize change_lag
        - ensures changes are processed in a reasonable time (e.g., up to date reports for users)
    - Minimize changes.exceptions
        - ensures consistency across application (e.g., secondary databases contain accurate data)
        - more exceptions mean more load since they will be reprocessed at a later time
    - Minimize number of pillows running
        - minimizes server resources required

The ideal setup would have 1 pillow with no exceptions and 0 second lag.


Troubleshooting
===============

A pillow is falling behind
--------------------------

Otherwise known as "pillow lag", a pillow can fall behind for a few reasons:

1. The processor is too slow for the number of changes that are coming in.
2. There was an issue with the change feed that caused the checkpoint to be
   "rewound".
3. A processor continues to fail so changes are re-queued and processed again
   later.

Lag is inherent to asynchronous change processing, so the question is what
amount of lag is acceptable for users.

Optimizing a processor
~~~~~~~~~~~~~~~~~~~~~~
To solve #1 you should use any monitors that have been set up to attempt to
pinpoint the issue.
`commcare.change_feed.processor.timing` can help determine what
processors/pillows are the root cause of slow processing.

If this is a UCR pillow use the `profile_data_source` management command to
profile the expensive data sources.

Parallel Processors
~~~~~~~~~~~~~~~~~~~

To scale pillows horizontally do the following:

1. Look for what pillows are behind. This can be found in the change feed
   dashboard or the hq admin system info page.
2. Ensure you have enough resources on the pillow server to scale the pillows.
   This can be found through datadog.
3. Decide what topics need to have added partitions in kafka. There is no way
   to scale a couch pillow horizontally. Removing partitions isn't
   straightforward, so you should attempt scaling in small increments. Also
   make sure pillows are able to split partitions easily by using powers of 2.
4. Run `./manage.py add_kafka_partition <topic> <number partitions to have>`
5. In the commcare-cloud repo environments/<env>/app-processes.yml file
   change num_processes to the pillows you want to scale.
6. On the next deploy multiple processes will be used when starting pillows

Note that pillows will automatically divide up partitions based on the number of partitions
and the number of processes for the pillow. It doesn't have to be one to one, and you don't
have to specify the mapping manually. That means you can create more partitions than you need
without changing the number of pillow processes and just restart pillows
for the change to take effect. Later you can just change the number of processes without touching
the number of partitions, and and just update the supervisor conf and restarting pillows
for the change to take effect.

The UCR pillows also have options to split the pillow into multiple. They
include `ucr_divsion`, `include_ucrs` and `exclude_ucrs`. Look to the pillow
code for more information on these.

Rewound Checkpoint
~~~~~~~~~~~~~~~~~~

Occasionally checkpoints will be "rewound" to a previous state causing pillows
to process changes that have already been processed. This usually happens when
a couch node fails over to another. If this occurs, stop the pillow, wait for
confirmation that the couch nodes are up, and fix the checkpoint using:
`./manage.py fix_checkpoint_after_rewind <pillow_name>`

Many pillow exceptions
~~~~~~~~~~~~~~~~~~~~~~

`commcare.change_feed.changes.exceptions` has tag `exception_type` that reports the name and path of the exception encountered.
These exceptions could be from coding errors or from infrastructure issues.
If they are from infrastructure issues (e.g. ES timeouts) some solutions could be:

- Scale ES cluster (more nodes, shards, etc)
- Reduce number of pillow processes that are writing to ES
- Reduce other usages of ES if possible (e.g. if some custom code relies on ES, could it use UCRs, https://github.com/dimagi/commcare-hq/pull/26241)


Problem with checkpoint for pillow name: First available topic offset for topic is num1 but needed num2
--------------------------------------------------------------------------------------------------------

This happens when the earliest checkpoint that kafka knows about for a topic is
after the checkpoint the pillow wants to start at. This often happens if a
pillow has been stopped for a month and has not been removed from the settings.

To fix this you should verify that the pillow is no longer needed in the
environment. If it isn't, you can delete the checkpoint and re-deploy. This
should eventually be followed up by removing the pillow from the settings.

If the pillow is needed and should be running you're in a bit of a pickle. This
means that the pillow is not able to get the required document ids from kafka.
It also won't be clear what documents the pillows has and has not processed. To
fix this the safest thing will be to force the pillow to go through all relevant
docs. Once this process is started you can move the checkpoint for that pillow
to the most recent offset for its topic.
