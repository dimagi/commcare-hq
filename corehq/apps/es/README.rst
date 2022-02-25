Elasticsearch App
=================

Adapter Design
--------------

The HQ Elastic adapter design came about due to the need for reindexing
Elasticsearch indexes in a way that is transparent to parts of HQ that write to
Elasticsearch (e.g. pillowtop).  Reindexing is necessary for making changes to
index mappings, is a prerequisite to upgrading an Elasticsearch cluster, and is
also needed for changing low-level index configurations (e.g. sharding).

There is an existing procedure draft that documents the steps that were used on
one occasion to reindex the ``case_search`` index.  This procedure leveraged a
custom pillow to "backfill" the cloned index (i.e. initially populated using
Elasticsearch Reindex API). That procedure only works for a subset of HQ
Elasticsearch indexes, and is too risky to be considered as an ongoing Elastic
maintenance strategy. There are several key constraints that an HQ reindexing
procedure should meet which the existing procedure does not:

- simple and robust
- performed with standard maintenance practices
- provides the ability to test and verify the integrity of a new index before it
  is too late to be rejected
- allows HQ Elasticsearch index state to remain decoupled from the
  commcare-cloud codebase
- is not disruptive -- does not prohibit any other kind of standard maintenance
  that might come up while the operation is underway
- is "fire and forget" -- does not require active polling of intermediate state
  in order to progress the overall operation
- is practical for third party HQ hosters to use

One way to accomplish these constraints is to implement an "index multiplexing"
feature in HQ, where Elasticsearch write operations are duplicated across two
indexes. This design facilitates maintaining two up-to-date versions of any
index (a primary read/write index and a secondary write-only index),
allowing HQ to run in a "normal" state (i.e. not a custom "maintenance" state)
while providing the ability to switch back and forth (swapping primary and
secondary) before fully committing to abandoning one of them. Creating a copy of
an index is the unavoidable nature of a reindex operation, and multiplexing
allows safe switching from one to the other without causing disruptions or
outages while keeping both up-to-date.

The least disruptive way to accomplish a multiplexing design is with an adapter
layer that operates between the low-level third party Elasticsearch Python
client library and high-level HQ components which need to read/write data in an
Elasticsearch index. Conveniently, HQ already has the initial framework for this
layer (the ``ElasticsearchInterface`` class), so the adapter layer is not a new
concept. The reason the ``ElasticsearchInterface`` implementation cannot
accommodate multiplexing is because it is not widely adopted for low-level
Elasticsearch operations (e.g. index creation and configuration), and it does
not sufficiently decouple low-level Elasticsearch document manipulation logic
from the high-level HQ code that uses it.

With a multiplexing adapter layer, reindexing an Elasticsearch index can be
as few as four concise steps, none of which are time-critical in respect to each
other:

1. Merge and deploy a PR that configures multiplexing on an index.
2. Execute an idempotent management command that updates the secondary index
   from its primary counterpart.
3. Merge and deploy a PR that disables multiplexing for the index, (now using
   only the new index).
4. Execute a management command to delete the old index.

*Note*: the above steps are not limited to a single index at a time. That is,
the implementation does not prohibit configuring multiplexing and reindexing
multiple indexes at once.

This reindex procedure is inherently safe because:

- At any point in the process, the rollback procedure is a simple code change
  (i.e. revert PR, deploy).
- The operation responsible for populating the secondary index is idempotent
  *and* decoupled from the index configuration, meaning it can undergo change
  iterations without aborting the entire process and losing existing progress.
- Instructions for third party hosters can follow the same process that Dimagi
  uses, which guarantees that any possible problems encountered by a third party
  hoster are not outside the Dimagi main track.


.. TODO: Future adapter documentation
..
.. - adapter patterns
.. - querying with adapters
.. - writing tests (use ``es_test``)

----

.. automodule:: corehq.apps.es.client
   :members:
