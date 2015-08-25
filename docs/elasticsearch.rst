ElasticSearch
=============

Indexes
-------
We have indexes for each of the following doc types:
 * Applications - ``hqapps``
 * Cases - ``hqcases``
 * Domains - ``hqdomains``
 * Forms - ``xforms``
 * Groups - ``hqgroups``
 * Users - ``hqusers``
 * Report Cases - ``report_cases``
 * Report Forms - ``report_xforms``
 * SMS logs - ``smslogs``
 * TrialConnect SMS logs - ``tc_smslogs``

The *Report* cases and forms indexes are only configured to run for a few
domains, and they store additional mappings allowing you to query on form
and case properties (not just metadata).

Each index has a corresponding mapping file in ``corehq/pillows/mappings/``.
Each mapping has a hash that reflects the current state of the mapping.
This is appended to the index name so the index is called something like
``xforms_1cce1f049a1b4d864c9c25dc42648a45``.  Each type of index has an alias
with the short name, so you should normally be querying just ``xforms``, not
the fully specified index+hash.

Whenever the mapping is changed, this hash should be updated.  That will
trigger the creation of a new index on deploy (by the ``$ ./manage.py
ptop_preindex`` command).  Once the new index is finished, the alias is
*flipped* (``$ ./manage.py ptop_es_manage --flip_all_aliases``) to point
to the new index, allowing for a relatively seamless transition.


Keeping indexes up-to-date
--------------------------
Pillowtop looks at the changes feed from couch and listens for any relevant
new/changed docs.  In order to have your changes appear in elasticsearch,
pillowtop must be running::

    $ ./manage.py run_ptop --all

You can also run a once-off reindex for a specific index::

    $ ./manage.py ptop_fast_reindex_users


Changing a mapping or adding data
---------------------------------
If you're adding additional data to elasticsearch, you'll need modify that
index's mapping file in order to be able to query on that new data.

Adding data to an index
'''''''''''''''''''''''
Each pillow has a ``change_transform`` method which you can override to
perform additional transformations or lookups on the data.  If for example,
you wanted to store username in addition to user_id on cases in elastic,
you'd add ``username`` to ``corehq.pillows.mappings.case_mapping``, then
modify ``corehq.pillows.case.CasePillow.change_transform`` to do the
appropriate lookup.  It accepts a ``doc_dict`` for the case doc and is
expected to return a ``doc_dict``, so just add the ``username`` to that.

Building the new index
''''''''''''''''''''''
Once you've made the change, you'll need to build a new index which uses
that new mapping, so you'll have to update the hash at the top of the file.
This can just be a random alphanumeric string.  This will trigger a preindex
as outlined in the `Indexes` section.


How to un-bork your broken indexes
----------------------------------
Sometimes things get in a weird state and (locally!) it's easiest to just
blow away the index and start over.

1. Delete the affected index.  The easiest way to do this is with `elasticsearch-head`_.
   You can delete multiple affected indices with
   ``curl -X DELETE http://localhost:9200/*``. ``*`` can be replaced with any regex to
   delete matched indices, similar to bash regex.
2. Run ``$ ./manage.py ptop_preindex && ./manage.py ptop_es_manage --flip_all_aliases``.
3. Try again

.. _elasticsearch-head: https://github.com/mobz/elasticsearch-head


Querying Elasticsearch
----------------------

.. TODO Figure out how to link properly:
Check out `es_query <es_query.html>`_
