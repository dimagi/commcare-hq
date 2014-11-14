Playing nice with Cloudant/CouchDB
===

We have a lot of views:

.. code-block:: bash

    $ find . -path *_design*/map.js | wc -l
         227

Things to know about views:

1. Every time you create or update doc, each map function is run on it
   and the btree_ for the view is updated based on the change
   in what the maps emit for that doc.
   Deleting a doc causes the btree to be updated as well.
2. Every time you update a view, it needs to be run, from scratch,
   in its entirety, on every single doc in the database, regardless of doc_type.

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
4. Don't save too many docs in too short a time!
   To give the views time to catch up, rate-limit your saves if going through
   hundreds of thousands of docs. One way to do this is to save N docs
   and then make a tiny request to the view you think will be slowest to update,
   and then repeat.
