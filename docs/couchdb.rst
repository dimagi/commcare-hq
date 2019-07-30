Playing nice with Cloudant/CouchDB
==================================

We have a lot of views:

.. code-block:: bash

    $ find . -path *_design*/map.js | wc -l
         159

Things to know about views:

1. Every time you create or update a doc, each map function is run on it
   and the btree_ for the view is updated based on the change
   in what the maps emit for that doc.
   Deleting a doc causes the btree to be updated as well.
2. Every time you update a view, all views in the design doc need to be run, from scratch,
   in their entirety, on every single doc in the database, regardless of doc_type.

.. _btree: http://guide.couchdb.org/draft/btree.html

Things to know about our Cloudant cluster:

1. It's slow. You have to wait in line just to say "hi".
   Want to fetch a single doc? So does everyone else.
   Get in line, I'll be with you in just 1000ms.
2. That's pretty much it.

Takeaways:

1. Don't save docs! If nothing changed in the doc, just don't save it.
   Couchdb isn't smart enough to realize that nothing changed,
   so saving it incurs most of the overhead of saving a doc that actually changed.
2. Don't make http requests! If you need a bunch of docs by id,
   get them all in one request or a few large requests
   using ``dimagi.utils.couch.database.iter_docs``.
3. Don't make http requests! If you want to save a bunch of docs,
   save them all at once
   (after excluding the ones that haven't changed and don't need to be saved!)
   using ``MyClass.get_db().bulk_save(docs)``.
   If you're writing application code that touches a number of related docs
   in a number of different places, you want to bulk save them, and you understand the warning in its docstring,
   you can use ``dimagi.utils.couch.bulk.CouchTransaction``.
   Note that this isn't good for saving thousands of documents,
   because it doesn't do any chunking.
4. Don't save too many docs in too short a time!
   To give the views time to catch up, rate-limit your saves if going through
   hundreds of thousands of docs. One way to do this is to save N docs
   and then make a tiny request to the view you think will be slowest to update,
   and then repeat.
5. Use different databases!
   All forms and cases save to the main database, but there is a `_meta` database we have just added for new doc or migrated doc types.
   When you use a different database you create two advantages:
   a) Documents you save don't contribute to the view indexing load of all of the views in the main database.
   b) Views you add don't have to run on all forms and cases.
6. Split views!
   When a single view changes, the **entire design doc** has to reindex.
   If you make a new view, it's much better to make a new design doc for it than to put it in with some other big, possibly expensive views.
   We use the `couchapps` folder/app for this.
