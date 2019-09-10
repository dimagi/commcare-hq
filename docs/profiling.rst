Profiling
=========

Practical guide to profiling a slow view or function
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This will walkthrough one way to profile slow code using the `@profile decorator <https://github.com/dimagi/dimagi-utils/blob/master/dimagi/utils/decorators/profile.py>`_.

At a high level this is the process:

#. Find the function that is slow
#. Add a decorator to save a raw profile file that will collect information about function calls and timing
#. Use libraries to analyze the raw profile file and spit out more useful information
#. Inspect the output of that information and look for anomalies
#. Make a change, observe the updated load times and repeat the process as necessary

Finding the slow function
^^^^^^^^^^^^^^^^^^^^^^^^^

This is usually pretty straightforward.
The easiest thing to do is typically use the top-level entry point for a view call.
In this example we are investigating the performance of commtrack location download, so the relevant function would be commtrack.views.location_export.

.. code-block:: python

    @login_and_domain_required
    def location_export(request, domain):
        response = HttpResponse(mimetype=Format.from_format('xlsx').mimetype)
        response['Content-Disposition'] = 'attachment; filename="locations.xlsx"'
        dump_locations(response, domain)
        return response

Getting a profile dump
^^^^^^^^^^^^^^^^^^^^^^

To get a profile dump, simply add the following decoration to the function.::

    from dimagi.utils.decorators.profile import profile
    @login_and_domain_required
    @profile('locations_download.prof')
    def location_export(request, domain):
        response = HttpResponse(mimetype=Format.from_format('xlsx').mimetype)
        response['Content-Disposition'] = 'attachment; filename="locations.xlsx"'
        dump_locations(response, domain)
        return response

Now each time you load the page a raw dump file will be created with a timestamp of when it was run.
These are created in /tmp/ by default, however you can change it by adding a value to your settings.py like so::

    PROFILE_LOG_BASE = "/home/czue/profiling/"

Note that the files created are huge; this code should only be run locally.

Profiling in production
^^^^^^^^^^^^^^^^^^^^^^^
The same method can be used to profile functions in production. Obviously we want to be able to
turn this on and off and possibly only profile a limited number of function calls.

This can be accomplished by using an environment variable to set the probability of profiling a function.
Here's an example:

.. code-block:: python

    @profile_prod('locations_download.prof', probability=float(os.getenv('PROFILE_LOCATIONS_EXPORT', 0))
    def location_export(request, domain):
        ....

By default this wil not do any profiling but if the `PROFILE_LOCATIONS_EXPORT` environment variable
is set to a value between 0 and 1 and the Django process is restarted then the function will
get profiled. The number of profiles that are done will depend on the value of the environment
variable. Values closer to 1 will get more profiling.

You can also limit the total number of profiles to be recorded using the `limit` keyword argument.
You could also expose this via an environment variable or some other method to make it configurable:

.. code-block:: python

    @profile_prod('locations_download.prof', 1, limit=10)
    def location_export(request, domain):
        ....

.. warning:: In a production environment the `limit` may not apply absolutely since there are likely
    multiple processes running in which case the limit will get applied to each one. Also, the limit will be reset
    if the processes are restarted.

    Any profiling in production should be closely monitored to ensure that
    it does not adversely affect performance or fill up available disk space.

Creating a more useful output from the dump file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The raw profile files are not human readable, and you need to use something
like `cProfile <https://docs.python.org/2/library/profile.html#module-cProfile>`_ to make them
useful.
A script that will generate what is typically sufficient information to analyze
these can be found in the `commcarehq-scripts`_ repository.
You can read the source of that script to generate your own analysis, or just
use it directly as follows::

   $ ./reusable/convert_profile.py /path/to/profile_dump.prof

.. _commcarehq-scripts: https://github.com/dimagi/commcarehq-scripts/blob/master/reusable/convert_profile.py


Reading the output of the analysis file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The analysis file is broken into two sections.
The first section is an ordered breakdown of calls by the **cumulative** time spent in those functions.
It also shows the number of calls and average time per call.

The second section is harder to read, and shows the callers to each function.

This analysis will focus on the first section.
The second section is useful when you determine a huge amount of time is being spent in a function but it's not clear where that function is getting called.

Here is a sample start to that file::

    loading profile stats for locations_download/commtrack-location-20140822T205905.prof
             361742 function calls (355960 primitive calls) in 8.838 seconds

       Ordered by: cumulative time, call count
       List reduced from 840 to 200 due to restriction <200>

       ncalls  tottime  percall  cumtime  percall filename:lineno(function)
            1    0.000    0.000    8.838    8.838 /home/czue/src/commcare-hq/corehq/apps/locations/views.py:336(location_export)
            1    0.011    0.011    8.838    8.838 /home/czue/src/commcare-hq/corehq/apps/locations/util.py:248(dump_locations)
          194    0.001    0.000    8.128    0.042 /home/czue/src/commcare-hq/corehq/apps/locations/models.py:136(parent)
          190    0.002    0.000    8.121    0.043 /home/czue/src/commcare-hq/corehq/apps/cachehq/mixins.py:35(get)
          190    0.003    0.000    8.021    0.042 submodules/dimagi-utils-src/dimagi/utils/couch/cache/cache_core/api.py:65(cached_open_doc)
          190    0.013    0.000    7.882    0.041 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/couchdbkit/client.py:362(open_doc)
          396    0.003    0.000    7.762    0.020 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/http_parser/_socketio.py:56(readinto)
          396    7.757    0.020    7.757    0.020 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/http_parser/_socketio.py:24(<lambda>)
          196    0.001    0.000    7.414    0.038 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/couchdbkit/resource.py:40(json_body)
          196    0.011    0.000    7.402    0.038 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/restkit/wrappers.py:270(body_string)
          590    0.019    0.000    7.356    0.012 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/http_parser/reader.py:19(readinto)
          198    0.002    0.000    0.618    0.003 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/couchdbkit/resource.py:69(request)
          196    0.001    0.000    0.616    0.003 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/restkit/resource.py:105(get)
          198    0.004    0.000    0.615    0.003 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/restkit/resource.py:164(request)
          198    0.002    0.000    0.605    0.003 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/restkit/client.py:415(request)
          198    0.003    0.000    0.596    0.003 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/restkit/client.py:293(perform)
          198    0.005    0.000    0.537    0.003 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/restkit/client.py:456(get_response)
          396    0.001    0.000    0.492    0.001 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/http_parser/http.py:135(headers)
          790    0.002    0.000    0.452    0.001 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/http_parser/http.py:50(_check_headers_complete)
          198    0.015    0.000    0.450    0.002 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/http_parser/http.py:191(__next__)
    1159/1117    0.043    0.000    0.396    0.000 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/jsonobject/base.py:559(__init__)
        13691    0.041    0.000    0.227    0.000 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/jsonobject/base.py:660(__setitem__)
          103    0.005    0.000    0.219    0.002 /home/czue/src/commcare-hq/corehq/apps/locations/util.py:65(location_custom_properties)
          103    0.000    0.000    0.201    0.002 /home/czue/src/commcare-hq/corehq/apps/locations/models.py:70(<genexpr>)
      333/303    0.001    0.000    0.190    0.001 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/jsonobject/base.py:615(wrap)
          289    0.002    0.000    0.185    0.001 /home/czue/src/commcare-hq/corehq/apps/locations/models.py:31(__init__)
            6    0.000    0.000    0.176    0.029 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/couchdbkit/client.py:1024(_fetch_if_needed)

.. seealso:: `Description of columns <https://docs.python.org/2/library/profile.html#instant-user-s-manual>`_

The most important thing to look at is the cumtime (cumulative time) column.
In this example we can see that the vast majority of the time (over 8 of the 8.9 total seconds) is spent in the cached_open_doc function (and likely the library calls below are called by that function).
This would be the first place to start when looking at improving profile performance.
The first few questions that would be useful to ask include:

* Can we optimize the function?
* Can we reduce calls to that function?
* In the case where that function is hitting a database or a disk, can the code be rewritten to load things in bulk?

In this practical example, the function is clearly meant to already be caching (based on the name alone) so it's possible that the results would be different if caching was enabled and the cache was hot.
It would be good to make sure we test with those two parameters true as well.
This can be done by changing your localsettings file and setting the following two variables::

    COUCH_CACHE_DOCS = True
    COUCH_CACHE_VIEWS = True

Reloading the page twice (the first time to prime the cache and the second time to profile with a hot cache) will then produce a vastly different output::

    loading profile stats for locations_download/commtrack-location-20140822T211654.prof
             303361 function calls (297602 primitive calls) in 0.484 seconds

       Ordered by: cumulative time, call count
       List reduced from 741 to 200 due to restriction <200>

       ncalls  tottime  percall  cumtime  percall filename:lineno(function)
            1    0.000    0.000    0.484    0.484 /home/czue/src/commcare-hq/corehq/apps/locations/views.py:336(location_export)
            1    0.004    0.004    0.484    0.484 /home/czue/src/commcare-hq/corehq/apps/locations/util.py:248(dump_locations)
    1159/1117    0.017    0.000    0.160    0.000 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/jsonobject/base.py:559(__init__)
            4    0.000    0.000    0.128    0.032 /home/czue/src/commcare-hq/corehq/apps/locations/models.py:62(filter_by_type)
            4    0.000    0.000    0.128    0.032 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/couchdbkit/client.py:986(all)
          103    0.000    0.000    0.128    0.001 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/couchdbkit/client.py:946(iterator)
            4    0.000    0.000    0.128    0.032 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/couchdbkit/client.py:1024(_fetch_if_needed)
            4    0.000    0.000    0.128    0.032 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/couchdbkit/client.py:995(fetch)
            9    0.000    0.000    0.124    0.014 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/http_parser/_socketio.py:56(readinto)
            9    0.124    0.014    0.124    0.014 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/http_parser/_socketio.py:24(<lambda>)
            4    0.000    0.000    0.114    0.029 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/couchdbkit/resource.py:40(json_body)
            4    0.000    0.000    0.114    0.029 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/restkit/wrappers.py:270(body_string)
           13    0.000    0.000    0.114    0.009 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/http_parser/reader.py:19(readinto)
          103    0.000    0.000    0.112    0.001 /home/czue/src/commcare-hq/corehq/apps/locations/models.py:70(<genexpr>)
        13691    0.018    0.000    0.094    0.000 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/jsonobject/base.py:660(__setitem__)
          103    0.002    0.000    0.091    0.001 /home/czue/src/commcare-hq/corehq/apps/locations/util.py:65(location_custom_properties)
          194    0.000    0.000    0.078    0.000 /home/czue/src/commcare-hq/corehq/apps/locations/models.py:136(parent)
          190    0.000    0.000    0.076    0.000 /home/czue/src/commcare-hq/corehq/apps/cachehq/mixins.py:35(get)
          103    0.000    0.000    0.075    0.001 submodules/dimagi-utils-src/dimagi/utils/couch/database.py:50(iter_docs)
            4    0.000    0.000    0.075    0.019 submodules/dimagi-utils-src/dimagi/utils/couch/bulk.py:81(get_docs)
            4    0.000    0.000    0.073    0.018 /home/czue/.virtualenvs/commcare-hq/local/lib/python2.7/site-packages/requests/api.py:80(post)

Yikes! It looks like this is already quite fast with a hot cache!
And there don't appear to be any obvious candidates for further optimization.
If it is still a problem it may be an indication that we need to prime the cache better, or increase the amount of data we are testing with locally to see more interesting results.

Aggregating data from multiple runs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In some cases it is useful to run a function a number of times and aggregate the profile data.
To do this follow the steps above to create a set of '.prof' files (one for each run of the function) then use the
`gather_profile_stats.py`_ script to aggregate the data.

This will produce a file which can be analysed with the `convert_profile.py`_ script.

.. _gather_profile_stats.py: https://github.com/dimagi/commcarehq-scripts/blob/master/reusable/gather_profile_stats.py
.. _convert_profile.py: https://github.com/dimagi/commcarehq-scripts/blob/master/reusable/convert_profile.py

Additional references
^^^^^^^^^^^^^^^^^^^^^
* http://django-extensions.readthedocs.org/en/latest/runprofileserver.html

Memory profiling
~~~~~~~~~~~~~~~~

Refer to these resources which provide good information on memory profiling:

* `Diagnosing memory leaks <http://chase-seibert.github.io/blog/2013/08/03/diagnosing-memory-leaks-python.html>`_
* `Using heapy <http://smira.ru/wp-content/uploads/2011/08/heapy.html>`_
* `Diving into python memory <https://github.com/CyrilPeponnet/cyrilpeponnet.github.com/blob/master/_posts/2014-09-18-diving-into-python-memory.md>`_
* `Memory usage graphs with ps <http://brunogirin.blogspot.com.au/2010/09/memory-usage-graphs-with-ps-and-gnuplot.html>`_
    * `while true; do ps -C python -o etimes=,pid=,%mem=,vsz= >> mem.txt; sleep 1; done`

* You can also use the "resident_set_size" decorator and context manager to print the amount of memory allocated to python before and after the method you think is causing memory leaks:


.. code-block:: python

    from dimagi.utils.decorators.profile import resident_set_size

    @resident_set_size()
    def function_that_uses_a_lot_of_memory:
        [u'{}'.format(x) for x in range(1,100000)]

    def somewhere_else():
        with resident_set_size(enter_debugger=True):
            # the enter_debugger param will enter a pdb session after your method has run so you can do more exploration
            # do memory intensive things
