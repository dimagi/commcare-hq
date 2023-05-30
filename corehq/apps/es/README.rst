Elasticsearch App
=================


Elasticsearch Index Management
------------------------------

CommCare HQ data in Elasticsearch is integral to core application functionality.
The level that the application relies on Elasticsearch data varies from index to
index. Currently, Elasticsearch contains both authoritative data (for example
``@indexed_on`` case property and ``UnknownUser`` user records) and data used
for real-time application logic (the ``users`` index, for example).

In order to guarantee stability (or "manageability", if you will) of this core
data, it is important that Elasticsearch indexes are maintained in a consistent
state across all environments as a concrete design feature of CommCare HQ. This
design constraint is accomplished by managing Elasticsearch index modifications
(for example: creating indexes, updating index mappings, etc) exclusively
through Django's migration framework. This ensures that all Elasticsearch index
modifications will be part of standard CommCare HQ code deployment procedures,
thereby preventing Elasticsearch index state drift between maintained CommCare
HQ deployments.

One or more migrations are required any time the following Elasticsearch state
configurations are changed in code:

- index names
- index aliases
- analyzers
- mappings
- tuning parameters

Elasticsearch allows changing an index's ``number_of_replicas`` tuning parameter
on a live index. In the future, the configuration settings (i.e. "live state")
of that value should be removed from the CommCare HQ codebase entirely in order
to decouple it from application logic.


.. _creating-elasticsearch-index-migrations:

Creating Elasticsearch Index Migrations
'''''''''''''''''''''''''''''''''''''''

Like Django Model migrations, Elasticsearch index migrations can be quite
verbose. To aid in creating these migrations, there is a Django manage command
that can generate migration files for Elasticsearch index operations. Since
the Elasticsearch index state is not a Django model, Django's model migration
framework cannot automatically determine what operations need to be included in
a migration, or even when a new migration is required. This is why creating
these migrations is a separate command and not integrated into the default
``makemigrations`` command.

To create a new Elasticsearch index migration, use the
``make_elastic_migration`` management command and provide details for the
required migration operations via any combination of the ``-c/--create``,
``-u/--update`` and/or ``-d/--delete`` command line options.

Similar to Django model migrations, this management command uses the index
metadata (mappings, analysis, etc) from the existing Elasticsearch code, so it
is important that this command is executed *after* making changes to index
metadata. To provide an example, consider a hypothetical scenario where the
following index changes are needed:

- create a new ``users`` index
- update the mapping on the existing ``groups`` index to add a new property
  named ``pending_users``
- delete the existing index named ``groups-sandbox``

After the new property has been added to the ``groups`` index mapping in code,
the following management command would create a migration file (e.g.
``corehq/apps/es/migrations/0003_groups_pending_users.py``) for the necessary
operations:

.. code-block:: shell

    ./manage.py make_elastic_migration --name groups_pending_users -c users -u groups:pending_users -d groups-sandbox


.. _updating-elastic-index-mappings:

Updating Elastic Index Mappings
'''''''''''''''''''''''''''''''

Prior to the ``UpdateIndexMapping`` migration operation implementation, Elastic
mappings were always applied "in full" any time a mapping change was needed.
That is: the entire mapping (from code) was applied to the existing index via
the `Put Mapping`_ API. This technique had some pros and cons:

- **Pro**: the mapping update logic in code was simple because it did not have
  to worry about which *existing* mapping properties are persistent (persist on
  the index even if omitted in a PUT request payload) and which ones are
  volatile (effectively "unset" if omitted in a PUT request payload).
- **Con**: it requires that *all* mapping properties are explicitly set on every
  mapping update, making mapping updates impossible if the existing index
  mapping in Elasticsearch has diverged from the mapping in code.

Because CommCare HQ Elastic mappings have been able to drift between
environments, it is no longer possible to update some index mappings using the
historical technique. On some indexes, the live index mappings have sufficiently
diverged that there is no common, "full mapping definition" that can be applied
on all environments. This means that in order to push mapping changes to all
environments, new mapping update logic is needed which is capable of updating
individual properties on an Elastic index mapping while leaving other (existing)
properties unchanged.

The ``UpdateIndexMapping`` migration operation adds this capability. Due to the
complex behavior of the Elasticsearch "Put Mapping" API, this implementation is
limited to only support changing the mapping ``_meta`` and ``properties`` items.
Changing other mapping properties (e.g. ``date_detection``, ``dynamic``, etc) is
not yet implemented. However, the current implementation does ensure that the
existing values are retained (unchanged). Historically, these values are rarely
changed, so this limitation does not hinder any kind of routine maintenance
operations. Implementing the ability to change the other properties will be a
simple task when there is a clear definition of how that functionality needs to
work, for example: when a future feature/change requires changing these
properties for a specific reason.

.. _Put Mapping: https://www.elastic.co/guide/en/elasticsearch/reference/2.4/indices-put-mapping.html


Comparing Mappings In Code Against Live Indexes
"""""""""""""""""""""""""""""""""""""""""""""""

When modifying mappings for an existing index, it can be useful to compare the
new mapping (as defined in code) to the live index mappings in Elasticsearch on
a CommCare HQ deployment. This is possible by dumping the mappings of interest
into local files and comparing them with a diff utility. The
``print_elastic_mappings`` Django manage command makes this process relatively
easy. Minimally, this can be accomplished in as few as three steps:

1. Export the local code mapping into a new file.
2. Export the mappings from a deployed environment into a local file.
3. Compare the two files.

In practice, this might look like the following example:

.. code-block:: shell

   ./manage.py print_elastic_mappings sms --no-names > ./sms-in-code.py
   cchq <env> django-manage print_elastic_mappings smslogs_2020-01-28:sms --no-names > ./sms-live.py
   diff -u ./sms-live.py ./sms-in-code.py


Elastic Index Tuning Configurations
'''''''''''''''''''''''''''''''''''

CommCare HQ provides a mechanism for individual deployments (environments) to
tune the performance characteristics of their Elasticsearch indexes via Django
settings. This mechanism can be used by defining an ``ES_SETTINGS`` dictionary
in ``localsettings.py`` (or by configuring the requisite Elasticsearch
parameters in a `CommCare Cloud environment`_). Tuning parameters can be
specified in one of two ways:

1. **"default"**: configures the tuning settings for *all* indexes in the
   environment.
2. **index identifier**: configures the tuning settings for *a specific* index
   in the environment -- these settings take precedence over "default" settings.

For example, if an environment wishes to explicitly configure the "case_search"
index with six shards, and all others with only three, the configuration could
be specified in ``localsettings.py`` as:

.. code-block:: python

   ES_SETTINGS = {
       "default": {"number_of_shards": 3},
       "case_search": {"number_of_shards": 6},
   }

Configuring a tuning setting with the special value ``None`` will result in that
configuration item being reset to the Elasticsearch cluster default (unless
superseded by another setting with higher precedence). Refer to
`corehq/app/es/index/settings.py`_ file for the full details regarding what
items (index and tunning settings values) are configurable, as well as what
default tuning settings will be used when not customized by the environment.

**Important note**: These Elasticsearch index tuning settings are not "live".
That is: changing their values on a deployed environment will not have any
immediate affect on live indexes in Elasticsearch. Instead, these values are
only ever used when an index is created (for example, during a fresh CommCare HQ
installation or when an existing index is reindexed into a new one). This means
that making new values become "live" involves an index migration and reindex,
which requires changes in the CommCare HQ codebase.

.. _CommCare Cloud environment: https://commcare-cloud.readthedocs.io/en/latest/reference/1-commcare-cloud/2-configuration.html
.. _corehq/app/es/index/settings.py: https://github.com/dimagi/commcare-hq/blob/master/corehq/app/es/index/settings.py


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
Elasticsearch index. HQ already has the initial framework for this layer (the
``ElasticsearchInterface`` class), so the adapter layer is not a new concept.
The reason that the ``ElasticsearchInterface`` implementation cannot be modified
in-place to accommodate multiplexing is because it is the wrong level of
abstraction. The ``ElasticsearchInterface`` abstraction layer was designed as an
Elasticsearch **version** abstraction. It provides a common set of functions and
methods so that the high-level HQ "consumer" that uses it can interact with
Elasticsearch documents without knowing which Elasticsearch *version* is on the
backend. It is below "index-level" logic, and does not implement index-specific
functionality needed in order for some indexes to be handled differently than
others (e.g. some indexes are indexed individually while others are
multiplexed). The document adapter implementation is a **document** abstraction
layer. It provides a common set of functions and methods to allow high-level HQ
code to perform Elasticsearch operations at the document level, allowing unique
adapters to handle their document operations differently from index to index.

With a multiplexing adapter layer, reindexing an Elasticsearch index can be
as few as four concise steps, none of which are time-critical in respect to each
other:

1. Merge and deploy a PR that configures multiplexing on an index.
2. Execute an idempotent management command that updates the secondary index
   from its primary counterpart.
3. Merge and deploy a PR that disables multiplexing for the index, (now using
   only the new index).
4. Execute a management command to delete the old index.

**Note**: the above steps are not limited to a single index at a time. That is,
the implementation does not prohibit configuring multiplexing and reindexing
multiple indexes at once.

This reindex procedure is inherently safe because:

- At any point in the process, the rollback procedure is a simple code change
  (i.e. revert PR, deploy).
- The operation responsible for populating the secondary index is idempotent
  *and* decoupled from the index configuration, allowing it to undergo change
  iterations without aborting the entire process (thereby losing reindex
  progress).
- Instructions for third party hosters can follow the same process that Dimagi
  uses, which guarantees that any possible problems encountered by a third party
  hoster are not outside the Dimagi main track.


Design Details
''''''''''''''

Reindex Procedure Details
'''''''''''''''''''''''''

1. Configure multiplexing on an index by passing in ``secondary`` index name to
   ``create_document_adapter``.

   - Ensure that there is a migration in place for creating the index (see
     `Creating Elasticsearch Index Migrations <creating-elasticsearch-index-migrations_>`__
     above).
   - *(Optional)* If the reindex involves other meta-index changes (shards,
     mappings, etc), also update those configurations at this time.

     **Note** Currently the Adapter will not support reindexing on specific
     environments but it would be compatible to accommodate it in future. This
     support will be added once we get to V5 of ES.

   - Configure ``create_document_adapter`` to return an instance of
     ``ElasticMultiplexAdapter`` by passing in ``secondary`` index name.

     .. code-block:: python

         case_adapter = create_document_adapter(
             ElasticCase,
             "hqcases_2016-03-04",
             "case",
             secondary="hqcase_2022-10-20"
         )

   - Add a migration which performs all cluster-level operations required for
     the new (secondary) index. For example:

     - creates the new index
     - configures shards, replicas, etc for the index
     - sets the index mapping

   - Review, merge and deploy this change.  At Django startup, the new
     (secondary) index will automatically and immediately begin receiving
     document writes. Document reads will always come from the primary index.

2. Execute a management command to sync and verify the secondary index from the
   primary.

   **Note**: This command is not yet implemented.

   This management command is idempotent and performs four operations in serial.
   If any of the operations complete with unexpected results, the command will
   abort with an error.

   1. Executes a Elastic ``reindex`` request with parameters to populate the
      secondary index from the primary, configured to not overwrite existing
      documents in the target (secondary) index.
   2. Polls the reindex task progress, blocking until complete.

      **Note**: the reindex API also supports a "blocking" mode which may be
      advantageous due to limitations in Elasticsearch 2.4's Task API. As such,
      this step **2.** might be removed in favor of a blocking reindex during
      the 2.4 --> 5.x upgrade.

   3. Performs a cleanup operation on the secondary index to remove tombstone
      documents.
   4. Performs a verification pass to check integrity of the secondary index.

      **Note**: An exact verification algorithm has not been designed, and
      complex verification operations may be left out of the first
      implementation. The reason it is outlined *in* this design is to identify
      that verification is supported and would happen *at this point* in the
      process. The initial implementation will at least implement
      feature-equivalency with the previous process (i.e. ensure document counts
      are equal between the two indexes), and tentatively an "equivalency check"
      of document ``_id``'s (tentative because checking equality while the
      multiplexer is running is a race condition).

   Example command (not yet implemented):

   .. code-block:: bash

       ./manage.py elastic_sync_multiplexed ElasticBook

3. Perform a primary/secondary "swap" operation one or more times as desired to
   run a "live test" on the new (secondary) index while keeping the old
   (primary) index up-to-date.

   - Reconfigure the adapter by swapping the "primary" and "secondary" index
     names.
   - Add a migration that cleans up tombstone documents on the "new primary"
     index prior to startup.

   **Note**: In theory, this step can be optional (e.g. if the sync procedure
   becomes sufficiently trusted in the future, or for "goldilox" indexes where
   rebuilding from source is feasible but advantageous to avoid, etc).

4. Disable multiplexing for the index.

   - Reconfigure the document adapter for the index by changing the "primary
     index name" to the value of the "secondary index name" and remove the
     secondary configuration (thus reverting the adapter back to a single-index
     adapter).
   - Add a migration that cleans up tombstone documents on the index.
   - Review, merge and deploy this change.

5. Execute a management command to delete the old index. Example:

   .. code-block:: bash

       ./manage.py prune_elastic_index ElasticBook


.. TODO: Future adapter documentation
..
.. - adapter patterns
.. - querying with adapters
.. - writing tests (use ``es_test``)

----

Elastic Client Adapters
-----------------------

The ``corehq.apps.es.client`` module encapsulates the CommCare HQ Elasticsearch
client adapters. It implements a high-level Elasticsearch client protocol
necessary to accomplish all interactions with the backend Elasticsearch cluster.
Client adapters are split into two usage patterns, the "Management Adapter" and
"Document Adapters".  Client adapters are instantiated at import time in order
to perform index verification when Django starts.  Downstream code needing an
adapter import and use the adapter instance.


Management Adapter
''''''''''''''''''

There is only one management adapter, ``corehq.apps.es.client.manager``. This
adapter is used for performing all cluster management tasks such as creating and
updating indices and their mappings, changing index settings, changing cluster
settings, etc.  This functionality is split into a separate class for a few
reasons:

1. The management adapter is responsible for low-level Elastic operations which
   document adapters should never be performing because the scope of a document
   adapter does not extend beyond a single index.
2. Elasticsearch 5+ implements security features which limit the kinds of
   operations a connection can be used for. The separation in these client
   adapter classes is designed to fit into that model.

.. code-block:: python

    from corehq.apps.es.client import manager

    manager.index_create("books")
    mapping = {"properties": {
        "author": {"type": "text"},
        "title": {"type": "text"},
        "published": {"type": "date"},
    }}
    manager.index_put_mapping("books", "book", mapping)
    manager.index_refresh("books")
    manager.index_delete("books")


Document Adapters
'''''''''''''''''

Document adapter classes are defined on a per-index basis and include specific
properties and functionality necessary for maintaining a single type of "model"
document in a single index.  Each index in Elasticsearch needs to have a
cooresponding ``ElasticDocumentAdapter`` subclass which defines how the Python
model is applied to that specific index.  At the very least, a document adapter
subclass must define the following:

- A ``mapping`` which defines the structure and properties for documents managed
  by the adapter.
- A ``from_python()`` classmethod which can convert a Python model object into
  the JSON-serializable format for writing into the adapter's index.

The combination of ``(index_name, type)`` constrains the document adapter to
a specific HQ document mapping.  Comparing an Elastic cluster to a Postgres
database (for the sake of analogy), the Elastic **index** is analogous to a
Postgres **schema** object (e.g. ``public``), and the ``_type`` property is
analogous to a Postgres **table** object. The combination of both index name
*and* ``_type`` fully constrains the properties that make up a specific Elastic
document.

Document adapters are instantiated once at runtime, via the
``create_document_adapter()`` function. The purpose of this function is to act
as a shim, returning an ``ElasticDocumentAdapter`` instance *or* an
``ElasticMultiplexAdapter`` instance (see
`Multiplexing Document Adapters <multiplexing-document-adapters_>`__ below);
depending on whether or not a secondary index is defined by the ``secondary``
keyword argument.

A simple example of a document model and its corresponding adapter:

.. code-block:: python

    class Book:

        def __init__(self, isbn, author, title, published):
            self.isbn = isbn
            self.author = author
            self.title = title
            self.published = published


    class ElasticBook(ElasticDocumentAdapter):

        mapping = {"properties": {
            "author": {"type": "text"},
            "title": {"type": "text"},
            "published": {"type": "date"},
        }}

        @classmethod
        def from_python(cls, book):
            source = {
                "author": book.author,
                "title": book.title,
                "published": book.published,
            }
            return book.isbn, source


    books_adapter = create_document_adapter(
        ElasticBook,
        index_name="books",
        type_="book",
    )


Using this adapter in practice might look as follows:

.. code-block:: python

    # index new
    new_book = Book(
        "978-1491946008",
        "Luciano Ramalho",
        "Fluent Python: Clear, Concise, and Effective Programming",
        datetime.date(2015, 2, 10),
    )
    books_adapter.index(new_book)
    # fetch existing
    classic_book = books_adapter.get("978-0345391803")


.. _multiplexing-document-adapters:

Multiplexing Document Adapters
''''''''''''''''''''''''''''''

The ``ElasticMultiplexAdapter`` is a wrapper around two
``ElasticDocumentAdapter`` instances: a primary and a secondary. The
multiplexing adapter provides the same public methods as a standard document
adapter, but it performs Elasticsearch write operations against both indexes in
order to keep them in step with document changes. The multiplexing adapter
provides the following functionality:

- All read operations (``exists()``, ``get()``, ``search()``, etc) are always
  performed against the *primary* adapter only. Read requests are never
  performed against the secondary adapter.
- The ``update()`` write method always results in two sequential requests
  against the underlying indexes:

  1. An update request against the primary adapter that simultaneously fetches
     the full, post-update document body.
  2. An upsert update request against the secondary adapter with the document
     returned in the primary update response.

- All other write operations (``index()``, ``delete()``, ``bulk()``, etc)
  leverage the Elasticsearch `Bulk API`_ to perform the required operations
  against both indexes simultaneously in as few requests against the backend as
  possible (a single request in some cases).

  - The ``index()`` method always achieves the index into both indexes with a
    single request.
  - The ``delete()`` method attempts to perform the delete against both
    indexes in a single request, and will only perform a second request in order
    to index a tombstone on the secondary (if the primary delete succeeded and
    the secondary delete failed with a 404 status).
  - The ``bulk()`` method (the underlying method for all bulk operations)
    performs actions against both indexes simultaneously by chunking the actions
    prior to calling ``elasticsearch.helpers.bulk()`` (as opposed to relying on
    that function to perform the chunking). This allows all bulk actions to be
    applied against both the primary and secondary indexes in parallel, thereby
    keeping both indexes synchronized throughout the duration of potentially
    large (multi-request) bulk operations.

.. _Bulk API: https://www.elastic.co/guide/en/elasticsearch/reference/2.4/docs-bulk.html


Tombstone
---------

The concept of Tombstone in the ES mulitplexer is there to be placeholder for
the docs that get deleted on the primary index prior to that document being
indexed on the secondary index. It means that whenever an adapter is multiplexed
and a document is deleted, then the secondary index will receive a tombstone
entry for that document *if and only if* the primary index delete succeeds and
the secondary index delete fails due to a not found condition (404). The python
class defined to represent these tombstones is
``corehq.apps.es.client.Tombstone``.

Scenario without tombstones: If a multiplexing adapter deletes a document in the
secondary index (which turns out to be a no-op because the document does not
exist there yet), and then that same document is copied to the secondary index
by the reindexer, then it will exist indefinitely in the secondary even though
it has been deleted in the primary.

Put another way:

- Reindexer: gets batch of objects from primary index to copy to secondary.
- Multiplexer: deletes a document in that batch (in both primary and secondary
  indexes).
- Reindexer: writes deleted (now stale) document into secondary index.
- Result: secondary index contains a document that has been deleted.

With tombstones: this will not happen because the reindexer uses a "ignore
existing documents" copy mode, so it will never overwrite a tombstone with a
stale (deleted) document.

Tombstones will only exist in the secondary index and will be deleted as a final
step following a successful sync (reindex) operation. Since tombstones can only
be created while the primary and secondary indexes are out of sync (secondary
index does not yet contain all primary documents), then once the sync is
complete, the multiplexer will no longer create new tombstones.

A sample tombstone document would look like

.. code-block:: python

    {
      "__is_tombstone__" : True
    }


Code Documentation
------------------

.. automodule:: corehq.apps.es.client
   :members:
