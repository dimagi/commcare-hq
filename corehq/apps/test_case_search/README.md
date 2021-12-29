# Testing Changes to Case Search

This module is to more easily try out changes to the case search system for
better results, specifically focused on matching addresses and multi-word names
or case properties. It is meant for testing only, and should not interfere with
the actively used case search index. Everything happens on a new elasticsearch
index called `new_case_search_test`.

The main usage of this module is through the management command
`test_new_case_search`, which provides the following options

 * `--reset` Deleting the index if it exists, rebuild it, and populate it with
   some fixture data.
 * `--load-domain` Load all cases from a domain into the index
 * `--query` Run some predefined queries against the index

This will likely see considerable change as testing gets underway. By using a
transient, easily-rebuilt index, we can iterate more quickly. This index is not
hooked into pillowtop or the elasticsearch index registry, so data changes won't
automatically propagate.


## Customizations

This system is currently set up to mirror the existing case search index.
Changes are likely to go in one of three places:

**The Mapping**
This index uses `corehq/pillows/mappings/test_case_search_mapping.json` as its
mapping. Changes to how elasticsearch stores and indexes data go there.

**Preprocessing**
Particularly for addresses, we may end up doing some preprocessing of data to
normalize it before sending to elasticsearch. In fitting with how pillowtop
work, this sort of change can be tested by modifying
`corehq.apps.test_case_search.administer.transform_case_for_elasticsearch`.

**Querying**
New types of queries can be tested in a shell session, a standalone script, or
by modifying `corehq.apps.test_case_search.queries.run_all_queries`. To support
this, there is a scaffolding for providing fixture data in
`corehq.apps.test_case_search.fixture_data.CASES_FIXTURE`. This can all be
modified as needed.
