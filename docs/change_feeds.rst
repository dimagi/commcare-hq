.. _Change Feeds:

============
Change Feeds
============

The following describes our approach to change feeds on HQ.
For related content see `this presentation on the topic <https://docs.google.com/presentation/d/1YPWUJbic87UYz3bqocJCsnYrnaEZkn8nCM2VZOXQRmg/edit>`_
though be advised the presentation was last updated in 2015 and is somewhat out of date.

What they are
=============

A change feed is modeled after the CouchDB ``_changes`` feed.
It can be thought of as a real-time log of "changes" to our database.
Anything that creates such a log is called a "(change) publisher".

Other processes can listen to a change feed and then do something with the results.
Processes that listen to changes are called "subscribers".
In the HQ codebase "subscribers" are referred to as "pillows" and most of the change feed functionality is provided via the pillowtop module.
This document refers to pillows and subscribers interchangeably.

Common use cases for change subscribers:

* ETL (our main use case)
    - Saving docs to ElasticSearch
    - Custom report tables
    - UCR data sources
* Cache invalidation

Architecture
============

We use `kafka <http://kafka.apache.org/>`_ as our primary back-end to facilitate change feeds.
This allows us to decouple our subscribers from the underlying source of changes so that they can be database-agnostic.
For legacy reasons there are still change feeds that run off of CouchDB's ``_changes`` feed however these are in the process of being phased out.

Topics
~~~~~~

Topics are a kafka concept that are used to create logical groups (or "topics") of data.
In the HQ codebase we use topics primarily as a 1:N mapping to HQ document classes (or ``doc_type`` s).
Forms and cases currently have their own topics, while everything else is lumped in to a "meta" topic.
This allows certain pillows to subscribe to the exact category of change/data they are interested in
(e.g. a pillow that sends cases to elasticsearch would only subscribe to the "cases" topic).

Document Stores
~~~~~~~~~~~~~~~

Published changes are just "stubs" but do not contain the full data that was affected.
Each change should be associated with a "document store" which is an abstraction that represents a way to retrieve the document from its original database.
This allows the subscribers to retrieve the full document while not needing to have the underlying source hard-coded (so that it can be changed).
To add a new document store, you can use one of the existing subclasses of ``DocumentStore`` or roll your own.

Publishing changes
==================

Publishing changes is the act of putting them into kafka from somewhere else.

From Couch
~~~~~~~~~~

Publishing changes from couch is easy since couch already has a great change feed implementation with the ``_changes`` API.
For any database that you want to publish changes from the steps are very simple.
Just create a ``ConstructedPillow`` with a ``CouchChangeFeed`` feed pointed at the database you wish to publish from and a ``KafkaProcessor`` to publish the changes.
There is a utility function (``get_change_feed_pillow_for_db``) which creates this pillow object for you.


From SQL
~~~~~~~~

Currently SQL-based change feeds are published from the app layer.
Basically, you can just call a function that publishes the change in a ``.save()`` function (or a ``post_save`` signal).
See the functions in `form_processors.change_publishers <https://github.com/dimagi/commcare-hq/blob/master/corehq/form_processor/change_publishers.py>`_ and their usages for an example of how that's done.

It is planned (though unclear on what timeline) to find an option to publish changes directly from SQL to kafka to avoid race conditions and other issues with doing it at the app layer.
However, this change can be rolled out independently at any time in the future with (hopefully) zero impact to change subscribers.

From anywhere else
~~~~~~~~~~~~~~~~~~

There is not yet a need/precedent for publishing changes from anywhere else, but it can always be done at the app layer.

Subscribing to changes
======================

It is recommended that all new change subscribers be instances (or subclasses) of ``ConstructedPillow``.
You can use the ``KafkaChangeFeed`` object as the change provider for that pillow, and configure it to subscribe to one or more topics.
Look at usages of the ``ConstructedPillow`` class for examples on how this is done.



Porting a new pillow
====================

Porting a new pillow to kafka will typically involve the following steps.
Depending on the data being published, some of these may be able to be skipped (e.g. if there is already a publisher for the source data, then that can be skipped).

1. Setup a publisher, following the instructions above.
2. Setup a subscriber, following the instructions above.
3. For non-couch-based data sources, you must setup a ``DocumentStore`` class for the pillow, and include it in the published feed.
4. For any pillows that require additional bootstrap logic (e.g. setting up UCR data tables or bootstrapping elasticsearch indexes) this must be hooked up manually.

Mapping the above to CommCare-specific details
==============================================

Topics
~~~~~~

The list of topics used by CommCare can be found in `corehq.apps.change_feed.topics.py <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/change_feed/topics.py#L9>`_.
For most data models there is a 1:1 relationship between the data model and the model in CommCare HQ, with the exceptions
of forms and cases, which each have two topics - one for the legacy CouchDB-based forms/cases, and one for the SQL-based
models (suffixed by ``-sql``).

Contents of the feed
~~~~~~~~~~~~~~~~~~~~

Generally the contents of each change in the feed will documents that mirror the ``ChangeMeta`` class in
`pillowtop.feed.interface <https://github.com/dimagi/commcare-hq/blob/master/corehq/ex-submodules/pillowtop/feed/interface.py#L9>`_,
in the form of a serialized JSON dictionary. An example once deserialized might look something like this:

.. code-block:: json

    {
      "document_id": "95dece4cd7c945ec83c6d2dd04d38673",
      "data_source_type": "sql",
      "data_source_name": "form-sql",
      "document_type": "XFormInstance",
      "document_subtype": "http://commcarehq.org/case",
      "domain": "dimagi",
      "is_deletion": false,
      "document_rev": null,
      "publish_timestamp": "2019-09-18T14:31:01.930921Z",
      "attempts": 0
    }

Details on how to interpret these can be found in the comments of the linked class.

The `document_id`, along with the `document_type` and `data_source_type` should be sufficient to retrieve the
underlying raw document out from the feed from the Document Store (see above).
