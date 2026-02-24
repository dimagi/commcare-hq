.. _couch-design-doc-changes:

Couch Design Doc Changes
========================

So you need to make a change to a couch design document? Sorry to hear that.
This document was started after `this retro <retro_>`_, if you'd like to
reference a recent example.

First, some terminology. Couch views (and filters) are stored on design
documents. For example, as of this writing, there is an ``app_manager`` design
document with four views (eg: ``app_manager/applications`` and
``app_manager/builds_by_date``).

Design docs are indexed by creating a temporary design document with the suffix
``-tmp``, doing the index on that in the background, then copying it over the
original (if present) at the end. This avoids service disruptions.

Design documents are managed monolithically, so changing or removing a single
view will also impact everything else on that design doc. For that reason,
current best practice is to use the `couchapps pattern <couchapps_>`_ if you're
adding a new view.

.. _couchapps: https://github.com/dimagi/commcare-hq/blob/master/corehq/couchapps/README.md
.. _retro: https://docs.google.com/document/d/1gy2FCAOnadRBEMeh8PDmOfK684Y7BQYAsrd6LjWy3mU/edit?tab=t.0

Risks, Prep Work
----------------

As with any other DB migration, you should of course follow usual guidance, such
as that described in :ref:`migrations-in-practice`. Couch design doc changes are
initiated by running a management command, with another command to finish. This
must also be automated using the ``RequestReindex`` pattern described `here
<reindex_>`_. That should be thought of as a way to update third-party and dev
environments - it is not a suitable method of reindexing couchdb in large
production environments.

.. _reindex: https://github.com/dimagi/commcare-hq/blob/master/CONTRIBUTING.rst#reindex--migration

It's tough to say how safe the reindex will be - it depends largely on which
database it is. At the time of this writing, the www users DB is corrupted and
cannot be reindexed (though a fix is in the works). The apps DB had OOM errors
last time we attempted to initiate a reindex. If you need to reindex apps, I'd
look into whether you can temporarily scale up the available couch memory.

Regardless of the DB, pick an appropriate time to run the migration in advance,
and ensure any necessary support will be available to assist, should anything go
wrong. Know what to keep an eye on in case problems arise.

Reindex Process
---------------

#. Ensure that the PR containing the design document changes is approved. Do not
   merge it yet.
#. Announce that you will be beginning the migration
#. Pull up the couchdb dashboard in datadog to keep an eye out for problems such
   as memory usage spikes. The "Active Tasks" graph will show the ``index``
   operation.
#. Set up a private release and run ``preindex_everything`` to create the
   temporary design document and start reindexing::

     commcare-cloud <env> preindex-views --commcare-rev <branch_name>

#. Wait until this command completes - it may hang with no output for hours.
   Keep an eye on datadog.
#. Monitor status by running this in a django shell session. It should jump
   around but trend upwards ::

     design_doc = 'latest_apps'  # UPDATE TO THE NEW DESIGN DOC NAME
     db = Application.get_db()  # UPDATE TO THE APPROPRIATE DB

     from time import sleep
     total_update_seq = int(db.info()['update_seq'].split('-')[0])
     path = db._database_path(f'_design/{design_doc}-tmp/_info')
     while True:
        seq = db._request_session.get(path).json()['view_index']['update_seq']
        pct_complete = seq / total_update_seq
        print(f"{pct_complete:.1%} complete")
        sleep(15)

#. When the preindex command completes, first try querying the new view on the
   `-tmp` design document. For example ::

     list(db.view('latest_apps-tmp/view', reduce=False, limit=1))

#. If all looks good, it's time to copy the temporary design doc back over the
   existing one ::

     commcare-cloud <env> django-manage --release <release_name> sync_finish_couchdb_hq

#. Now double check that you can perform the queries you expect
#. Repeat on other environments
#. Merge your branch. When the deploy goes out, the django migration requesting
   a reindex will noop on environments that have already been preindexed.


Improvements to Tooling
-----------------------

This process is pretty haphazard - if you've got the time and the inclination,
here are some suggestions to improve the tooling and process.

Add monitoring to preindex_everything
.....................................

This document describes a method of checking reindex process - there's probably
something more authoritative available too (check the ``index`` task?). Either
way, this should be incorporated in to the ``preindex_everything`` command, so
it's clearer that something is still happening, and to show progress (could even
predict time remaining).

Improve stateful index task tracking
....................................

The ``preindex_everything`` command sets a cache in redis to track the status of
the ongoing reindex, but this isn't tied to the current deploy process. We could
develop this out to reliably (and resumably) check the actual reindex status,
not just that of the task that initiated the reindex.

Make RequestReindex fault tolerant
..................................

``RequestReindex`` sets a global ``should_reindex`` flag that is later inspected
when deciding whether to run a migration. However, if the deploy fails between
those steps, the reindex will not be run. That happened when testing on staging.

It might be better to make the migration command block on the completion of the
reindex, such as by checking the redis state flag set by
``preindex_everything``.
