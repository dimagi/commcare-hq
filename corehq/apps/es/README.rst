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
"Document Adapters".

.. toctree::

    Management Adapter
    Document Adapters
    Code Documentation


Management Adapter
''''''''''''''''''

There is only one management adapter, ``ElasticManageAdapter``. This adapter is
used for performing all cluster management tasks such as creating and updating
indices and their mappings, changing index settings, changing cluster settings,
etc.  This functionality is split into a separate class for a few reasons:

1. The management adapter is responsible for low-level Elastic operations which
   document adapters should never be performing because the scope of a document
   adapter does not extend beyond a single index.
2. Elasticsearch 5+ implements security features which limit the kinds of
   operations a connection can be used for. The separation in these client
   adapter classes is designed to fit into that model.

The management adapter does not need any special parameters to work with, and
can be instantiated and used directly:

.. code-block:: python

    adapter = ElasticManageAdapter()
    adapter.index_create("books")
    mapping = {"properties": {
        "author": {"type": "text"},
        "title": {"type": "text"},
        "published": {"type": "date"},
    }}
    adapter.index_put_mapping("books", "book", mapping)
    adapter.index_refresh("books")
    adapter.index_delete("books")


Document Adapters
'''''''''''''''''

Document adapters are created on a per-index basis and include specific
properties and functionality necessary for maintaining a single type of "model"
document in a single index.  Each index in Elasticsearch needs to have a
cooresponding ``ElasticDocumentAdapter`` subclass which defines how the Python
model is applied to that specific index.  At the very least, a document adapter
must define the following:

- An ``_index_name`` attribute whose value is the name of the Elastic index
  used by the adapter. This attribute must be private to support proper index
  naming between production code and tests.
- A ``type`` attribute whose value is the name is the Elastic ``_type`` for
  documents used by the adapter.
- A ``mapping`` which defines the structure and properties for documents managed
  by the adapter.
- A ``from_python()`` classmethod which can convert a Python model object into the
  JSON-serializable format for writing into the adapter's index.

The combination of ``(index_name, type)`` constrains the document adapter to
a specific HQ document mapping.  Comparing an Elastic cluster to a Postgres
database (for the sake of analogy), the Elastic **index** is analogous to a
Postgres **schema** object (e.g. ``public``), and the ``_type`` property is
analogous to a Postgres **table** object. The combination of both index name
*and* ``_type`` fully constrains the properties that make up a specific Elastic
document.

A simple example of a document model and its cooresponding adapter:

.. code-block:: python

    class Book:

        def __init__(self, isbn, author, title, published):
            self.isbn = isbn
            self.author = author
            self.title = title
            self.published = published


    class ElasticBook(ElasticDocumentAdapter):

        _index_name = "books"
        type = "book"
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

Using this adapter in practice might look as follows:

.. code-block:: python

    adapter = ElasticBook()
    # index new
    new_book = Book(
        "978-1491946008",
        "Luciano Ramalho",
        "Fluent Python: Clear, Concise, and Effective Programming",
        datetime.date(2015, 2, 10),
    )
    adapter.index(new_book)
    # fetch existing
    classic_book = adapter.fetch("978-0345391803")


Code Documentation
''''''''''''''''''

.. automodule:: corehq.apps.es.client
   :members:
