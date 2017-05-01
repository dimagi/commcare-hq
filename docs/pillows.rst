=======
Pillows
=======

What they are
=============

A pillow is a subscriber to a change feed. When a
change is published the pillow receives the document, performs some calculation
or transform, and publishes it to another database.

Creating a pillow
=================

All pillows inherit from `ConstructedPillow` class. A pillow consists of a few parts:

1. Change Feed
2. Checkpoint
3. Processor(s)
4. Change Event Handler

Change Feed
-----------

Change feeds are documented `here <Change Feeds>`_.

The 10,000 foot view is a change feed publishes changes which you can subscribe to.

Checkpoint
----------

The checkpoint is a json field that tells processor where to start the change
feed.

Processor(s)
------------

A processor is what handles the transformation or calculation and publishes it
to a database. Most pillows only have one processor, but sometimes it will make
sense to combine processors into one pillow when you are only iterating over a
small number of documents (such as custom reports).

When creating a processor you should be aware of how much time it will take to
process the record. A useful baseline is:

86400 seconds per day / # of expected changes per day = how long your processor should take

Note that it should be faster than this as most changes will come in at once
instead of evenly distributed throughout the day.

Change Event Handler
--------------------

This fires after each change has been processed. The main use case is to save
the checkpoint to the database.

Error Handling
==============

Pillow errors are handled by saving to model `PillowError`. A celery queue
reads from this model and retries any errors on the pillow.

Monitoring
==========

There are several datadog metrics with the prefix `commcare.change_feed` that
can be helpful for monitoring pillows.

For UCR pillows the pillow log will contain any data sources and docs that
have exceeded a threshold and can be used to find expensive data sources.

Troubleshooting
===============

A pillow is falling behind
--------------------------

A pillow can fall behind for two reasons:

1. The processor is too slow for the number of changes that are coming in.
2. There has been an issue with the change feed that has caused the checkpoint
   to be "rewound"

Optimizing a processor
~~~~~~~~~~~~~~~~~~~~~~
To solve #1 you should use any monitors that have been set up to attempt to
pinpoint the issue.

If this is a UCR pillow use the `profile_data_source` management command to
profile the expensive data sources.

Parallel Processors
~~~~~~~~~~~~~~~~~~~

The UCR pillows currently have options to split the pillow into multiple. They
include `ucr_divsion`, `include_ucrs` and `exclude_ucrs`. Look to the pillow
code for more information on these.

Soon it will be possible to add partitions to kafka topics, which will be the
preferred way to horizontally scale pillows.

Rewound Checkpoint
~~~~~~~~~~~~~~~~~~

Occasionally checkpoints will be "rewound" to a previous state causing pillows
to process changes that have already been processed. This usually happens when
a couch node fails over to another. If this occurs, stop the pillow, wait for
confirmation that the couch nodes are up, and fix the checkpoint using:
`./manage.py fix_checkpoint_after_rewind <pillow_name>`

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
