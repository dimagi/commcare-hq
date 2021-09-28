ElasticSearch
~~~~~~~~~~~~~

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
Each mapping has a hash that reflects the current state of the mapping. This
can just be a random alphanumeric string.
The hash is appended to the index name so the index is called something like
``xforms_1cce1f049a1b4d864c9c25dc42648a45``.  Each type of index has an alias
with the short name, so you should normally be querying just ``xforms``, not
the fully specified index+hash. All of HQ code except the index maintenance
code uses aliases to read and write data to indices.

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

    $ ./manage.py ptop_reindexer_v2 user

Changing a mapping or adding data
---------------------------------
If you're adding additional data to elasticsearch, you'll need modify that
index's mapping file in order to be able to query on that new data.

Adding data to an index
'''''''''''''''''''''''
Each pillow has a function or class that takes in the raw document dictionary
and transforms it into the document that get's sent to ES.  If for example,
you wanted to store username in addition to user_id on cases in elastic,
you'd add ``username`` to ``corehq.pillows.mappings.case_mapping``, then
modify ``transform_case_for_elasticsearch`` function to do the
appropriate lookup.  It accepts a ``doc_dict`` for the case doc and is
expected to return a ``doc_dict``, so just add the ``username`` to that.

Building the new index
''''''''''''''''''''''
Once you've made the change, you'll need to build a new index which uses
that new mapping. Updating index name in the mapping file triggers HQ to
create the new index with new mapping and reindex all data, so you'll
have to update the index hash and alias at the top of the mapping file.
The hash suffix to the index can just be a random alphanumeric string and
is usually the date of the edit by convention. The alias should also be updated
to a new one of format ``xforms_<date-modified>`` (the date is just by convention), so that
production operations continue to use the old alias pointing to existing index.
This will trigger a preindex as outlined in the `Indexes` section. In subsequent commits
alias can be flipped back to what it was, for example ``xforms``. Changing the alias
name doesn't trigger a reindex.


Updating indexes in a production environment
''''''''''''''''''''''''''''''''''''''''''''
Updates in a production environment should be done in two steps, so to not show incomplete data.

1. Setup a release of your branch using cchq <env> setup_limited_release:keep_days=n_days
2. In your release directory, kick off a index using ``./mange.py ptop_preindex``
3. Verify that the reindex has completed successfully
   - This is a weak point in our current migration process
   - This can be done by using ES head or the ES APIs to compare document counts to the previous index.
   - You should also actively look for errors in the ptop_preindex command that was ran
4. Merge your PR and deploy your latest master branch.


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


Querying Elasticsearch - Best Practices
---------------------------------------

Here are the most basic things to know if you want to write readable
and reasonably performant code for accessing Elasticsearch.


Use ESQuery when possible
'''''''''''''''''''''''''

Check out :doc:`/es_query`

 * Prefer the cleaner ``.count()``, ``.values()``,  ``.values_list()``, etc. execution methods
   to the more low level ``.run().hits``, ``.run().total``, etc.
   With the latter easier to make mistakes and fall into anti-patterns and it's harder to read.
 * Prefer adding filter methods to using ``set_query()``
   unless you really know what you're doing and are willing to make your code more error prone
   and difficult to read.


Prefer "get" to "search"
''''''''''''''''''''''''

Don't use search to fetch a doc or doc fields by doc id; use "get" instead.
Searching by id can be easily an order of magnitude (10x) slower. If done in a loop,
this can effectively grind the ES cluster to a halt.

**Bad:**::

    POST /hqcases_2016-03-04/case/_search
    {
      "query": {
        "filtered": {
          "filter": {
            "and": [{"terms": {"_id": [case_id]}}, {"match_all": {}}]
          },
          "query": {"match_all":{}}
        }
      },
      "_source": ["name"],
      "size":1000000
    }

**Good:**::

    GET /hqcases_2016-03-04/case/<case_id>?_source_include=name


Prefer scroll queries
'''''''''''''''''''''

Use a scroll query when fetching lots of records.


Prefer filter to query
''''''''''''''''''''''

Don't use ``query`` when you could use ``filter`` if you don't need rank.


Use size(0) with aggregations
'''''''''''''''''''''''''''''

Use ``size(0)`` when you're only doing aggregations thing—otherwise you'll
get back doc bodies as well! Sometimes that's just abstractly wasteful, but often
it can be a serious performance hit for the operation as well as the cluster.

The best way to do this is by using helpers like ESQuery's ``.count()``
that know to do this for you—your code will look better and you won't have to remember
to check for that every time. (If you ever find *helpers* not doing this correctly,
then it's definitely worth fixing.)
