.. _migrations-in-practice:

Migrations in Practice
======================

Background
~~~~~~~~~~

Definitions
-----------

**Schema migration** - Modifies the database schema, say by adding a new column
or changing properties of an existing column. Usually pretty fast but can get
complicated if not backwards-compatible.

**Data migration** - Modifies data already in the database. This has the
potential to be quite slow

**Django migration** - A migration (either kind) that is run automatically on
deploy by ``./manage.py migrate``. These are in files like
``corehq/apps/<app>/migrations/0001_my_migration.py``

**Management command** - Some data migrations are written as management
commands. These are then run either manually via a commcare-cloud command or
automatically from inside a django migration using ``call_command``. These are
in files like ``corehq/apps/<app>/management/commands/my_command.py``

**Private release** - If you need to run code from a branch that’s not currently
deployed, use a `private release`_.

.. _`private release`: https://github.com/dimagi/commcare-cloud/blob/master/src/commcare_cloud/fab/README.md#private-releases


General Principles
------------------

**Don’t block deploys** - If you write a migration that will take more than 15
minutes to run on any server (typically production will have the most data and
therefore be the slowest), take care to run it outside of a deploy, otherwise
that deploy will hang. How do you know if your migration will take too long? Run
it on staging and compare the amount of data on staging to the amount of data on
prod to estimate. If in any kind of doubt, err on the side of caution. In
practice, any migration that touches common models - users, apps, domains - will
need to be run outside of a deploy, while migrations to tiny tables (thousands
of rows) or flagged features with few users may be able to run in a deploy.

**Deploys are not instantaneous** - Deploys will push new code, run the
migrations in that new code, and *then* switch the servers to the new code. The
site will be active this whole time. Users or tasks can add or modify data after
the start of the migration and before the code switch and you need to account
for that.

**All migration states should be valid** - Similar to the above, you must
consider the states before, during, and after the migration. Will the active
code handle all three states correctly?

**Master should always be deployable** - If you have a PR with a migration that
requires manual handling, don’t merge it until you are prepared to handle it.

**Remember third parties** - We’ll often manage migrations manually for at least
prod and india, but third parties run environments that we can’t manage
directly. Be sure that whatever changes are necessary will be applied
automatically on these environments, though it will likely require running data
migrations during deploy. If the change may be disruptive or *requires* manual
handling, `we’ll need to communicate it out in advance <announce_>`_.

.. _announce: https://confluence.dimagi.com/display/saas/Announcing+changes+affecting+third+parties


Practical Considerations
------------------------

**Handling new data** - There’s likely a code change that writes to the database
in the new way going forward. It cannot be deployed until any requisite schema
changes have been implemented.

**Migrating old data** - This will be handled via a django migration, a
management command, or both. Typically, small/simple migrations are handled by a
django migration and large/complex ones use a django migration that runs a
management command. It cannot run until any schema changes are deployed.

**Dealing with the gap** - We generally can’t pause the servers, put everything
to rights, then restart. Rather, we must ensure that we’re saving new data
properly before migrating old data, or otherwise ensure that all data from
before, during, and after the migration is handled correctly.

**Backwards-incompatible changes** - These are best avoided. A common workaround
is to treat it as two migrations - one to store the data (in duplicate, with any
necessary syncing code) the new way, then a later migration to remove the old
way from the schema. With couchdb, this is a little easier, since you don’t need
to remove the old schema once all the data is migrated.

**Idempotence and resumability** - If at all possible, you should design your
management command to be run multiple times without changing the result,
breaking, or redoing work. This means it should expect that some data in the db
might already be migrated, and only operate on unmigrated data. This should
happen performantly. This will help with some of the below migration strategies
and make dealing with unexpected failures much smoother.

**Shim code for the transition** - Another useful pattern in some circumstances
is to write short-lived code that can deal with both versions of the data in the
db. This can make the transition much easier. One example of this is overriding
the ``wrap`` method on a couch Document. Be sure to make a clean-up PR that
drops support for the old version to be merged later once it’s no longer needed.

**Migration-dependent code** - This is the reason the migration is being
performed. You need to make sure all data is migrated before code depending on
it is released.

**Testing** - Complex migrations can justify unit tests. These tests are often
short-lived, but they can protect against highly disruptive and lengthy data
cleanup caused by a bug. With migrations, plan for the worst. `Example tests`_
for a `management command`_.

.. _`Example tests`: https://github.com/dimagi/commcare-hq/blob/45b9c9040e72ebfc0058f209e2d3f99b8dfd6d16/custom/covid/tests/test_management_commands.py#L42-L107

.. _`management command`: https://github.com/dimagi/commcare-hq/blob/master/custom/covid/management/commands/add_hq_user_id_to_case.py

**Staging** - Prod data is usually much more complex than what you have locally
or what you might write for test cases. Before running your migration on prod,
run it on staging. However, this can cause issues if you need to change your
migration later, or if another migration in the same app conflicts with yours.
Be sure to leave staging in a good state.


Example Migration: User Logging
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Let’s speak about this a bit more concretely with a specific example migration
in mind. This is based on `a real example
<https://github.com/dimagi/commcare-hq/pull/30769>`__, but I’ve idealized it
somewhat here for illustration. Here’s a brief description of a migration which
will be referred back to throughout this document.

We log all changes to users, keeping track of who changed what. We currently
store the ID of the affected user, but now we want to store the username too.
This means we’ll need to make the following four changes:

1. **Schema migration**: Add a new ``user_repr`` field to the log model to hold
   the username
2. **Data migration**: Populate that field for all existing log rows

   a. If this will be run multiple times (more on that below), it should be
      idempotent and resumable.

      i.  Resumability: Rather than update *all* user changelogs, it should
          filter out those that already have ``user_repr`` set, so subsequent
          runs can be much much faster.
      ii. Idempotence: Running the command multiple times should behave the same
          as if it were run only once. For example, the command shouldn’t error
          if it encounters an already migrated log. It also shouldn’t apply a
          modification where unnecessary, like if the migration appended the
          ``user_repr`` to a string, then running it twice might result in
          something like ``"user@example.comuser@example.com"``

3. **Handle new data**: Modify the logging code to populate the ``user_repr`` field
   going forward.
4. **Migration-dependent code**: Update the UI to display the ``user_repr`` and make
   it filterable. We can’t turn this on until all existing logs have ``user_repr``
   set, or at least they’ll need to anticipate that some rows will be missing
   that field.

Because this example exclusively adds new data, there's no cleanup step. Some
migrations will need to remove an "old" way of doing things, which is frequently
done in an additional PR. For low-risk, simple, single-PR migrations, cleanup
might be included in the single PR.


Common types of migrations
~~~~~~~~~~~~~~~~~~~~~~~~~~

Simple
------

If you’re adding a new model or field in postgres that doesn’t need to be
back-populated, you can just put the schema migration in the same PR as the
associated code changes, and the deploy will apply that migration before the new
code goes live. In couch, this type of change doesn't require a migration at
all.

User Logging Example
....................

A "simple" migration would not be suitable for the example user logging
migration described above. If you tried to make all those changes in a single PR
and let it get deployed as-is, you risk missing data. During deploy, the data
migration will be run before the code handling new data properly goes live. Any
users modified in this period would not have the ``user_repr`` populated.
Additionally, the migration might take quite a while to run, which would block
the deploy.

Multiple deploys
----------------

This is the most robust approach, and is advocated for in the `couch-to-sql
<https://commcare-hq.readthedocs.io/couch_to_sql_models.html>`__ pattern. You
make two PRs:

- **PR 1**: Schema migration; handle new data correctly; data migration
  management command
- **PR 2**: Django migration calling the management command; actual code relying
  on the migration

After the first PR is deployed, you can run the migration in a management
command on whatever schedule is appropriate. The Django migration in the second
PR calls the command again so we can be sure it’s been run at least once on
every environment. On production, where the command has been run manually
already, this second run should see that there are no remaining unmigrated
rows/documents in the db and be nearly a noop.

Although using two deploys eliminates the risk of an indeterminate state on
environments that you control, this risk is still present for third party
environments. If the third party doesn't deploy often and ends up deploying the
two PRs together, there’s still a risk of changes happening in the gap between
the migration and the new code going live. The magnitude of this risk depends on
the functionality being migrated - how much data it touches and how frequently
it is used. If necessary, you can mitigate this risk by spacing the deploys so
that third parties are likely to deploy them separately. See `guidelines for
third parties running CommCare <guidelines_>`_.

.. _guidelines: https://github.com/dimagi/commcare-cloud/blob/master/docs/system/maintenance-expectations.md#expectations-for-ongoing-maintenance

User Logging Example
....................

Splitting the example user logging migration across two deploys would be a good
way to ensure everything is handled correctly. You’d split the changes into two
PRs as described above and deploy them separately. The steps would be:

1. **First PR deployed**: Now we have the schema change live, and all new
   changes to users have the ``user_repr`` field populated. Additionally, the
   management command is available for use.
2. **Run the management command**: This can be done in a private release any
   time before the second deploy. This should almost certainly be done on prod.
   Whether or not it needs to be done on the other Dimagi-managed environments
   (india, swiss) depends on how much data those environments have.
3. **Second PR deployed**: This will run the management command again,
   but since all logs have already been migrated, it won’t actually make any
   changes and should run fast - see the migrations best practices section
   below. This will also make sure third party environments have the change
   applied. This second PR also finally contains user-facing references to the
   ``user_repr`` field, since by the time the code switch happens, everything
   will have been migrated.


Single Deploy
-------------

**While this single-deploy option is tempting compared to waiting weeks to get out
a multi-deploy migration, it’s really only suitable for specific situations like
custom work and unreleased features, where we can be confident the drawbacks are
insignificant.**

The main drawbacks are:

  * This method requires manually running the Django migrations which are normally
    only run during deploy. Running migrations manually on a production environment
    is generally a bad idea.
  * It is possible that there will be a gap in data between the final run of the
    data migration command and the new going live (due to the sequence of events
    during a deploy).

If you decide to go down this route you should split your changes into two PRs:

- **PR 1**: Schema migration; data migration management command
- **PR 2**: Handle new data correctly; Django migration calling the management
  command; actual code relying on the migration

Once the PRs have both been approved, **merge PR 1**, then set up a private release
containing that change. Merging the PR first will prevent migration conflicts with
anyone else working in the area, and it's a good idea that anything run on a
production environment is on the master branch.

Run your schema migration and management command directly:

    ``cchq <ENV> django-manage --release=<NAME> migrate <APP_NAME>``
    ``cchq <ENV> django-manage --release=<NAME> my_data_migration_command``

Then merge PR 2. The subsequent deploy will run your management command again,
though it should be very quick this time around, since nearly all data has been
migrated, and finally the code changes will go live.

The big limitation here is that there’s a gap between the final run of the
management command and go-live (especially with the variation). Any changes in
the interim won’t be accounted for. This is sometimes acceptable if you’re
confident no such changes will have happened (eg, the migration pertains only to
a custom feature, and we know that project won’t have relevant activity during
that period).

User Logging Example
....................

Consider attempting to apply our example user logging migration with a single
deploy. Make two PRs as described, so they can be merged independently. Then
while coordinating with the team, merge the first PR, deploy a private release,
and run the schema migration, then the management command.

The second PR can be merged and go live with the next deploy. This django
migration will re-run the management command, picking up any new changes since
it was previously run. In our case, this should be a small enough data set that
it won’t hinder the deploy. *However*, any changes in the window between that
run and go-live will not be migrated. To pick up those changes, you can run the
management command a third time after the deploy, which will ensure all user
logs have been migrated.

This is still not ideal, since for the period between go-live and this third
run, there will be missing data in the DB and that data will be in-use in the
UI. Remember also that third party environments will have the management command
run only once, on the second deploy (unless we announce this as a required
maintenance operation), which would mean their data would have a gap in it.

Best practices for data migrations in Python
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Consider codifying boundaries for your migration** - This is especially useful
for large migrations that might require manual intervention or special handling
on third party environments. See detailed instructions in the
:ref:`auto-managed-migration-pattern` doc.

**Don’t fetch all data at once** - Instead, use an iterator that streams data in
chunks (note that django queryset’s ``.iter()`` method does not do this). Some
models have their own performant getters, for others, consider
``queryset_to_iterator`` for SQL models, ``iter_update`` or ``IterDB`` for couch
models. The ``chunked`` function is also helpful for this.

**Don’t write all data at once** - Instead, write data in chunks (ideally) or
individually (if needed, or if performance isn’t a concern). For couch, use
``IterDB``, ``iter_update``, or ``db.bulk_save``. For SQL, use
``django_bulk_update``. Remember though that these bulk options won’t call the
``save()`` method of your model, so be sure to check for any relevant side
effects or signals that happen there and either trigger them manually or use
individual saves in this instance.

**Don’t hold all data in memory** - Since you’re submitting in chunks anyways,
consider writing your changes in chunks as you iterate through them, rather than
saving them all up and submitting at the end.

**Don’t write from elasticsearch** - It’s sometimes necessary to use ES to find
the data that needs to be modified, but you should only return the ids of the
objects you need, then pull the full objects from their primary database before
modifying and writing.

**Check your assumptions** - Consider what could go wrong and encode your
assumptions about the state of the world. Eg: if you expect a field to be blank,
check that it is before overwriting. Consider what would happen if your
migration were killed in the middle - would that leave data in a bad state?
Would the migration need to redo work when run again? Couch data in particular,
since it's less structured than SQL, can contain surprising data, especially in
old documents.

**Only run migrations when needed** - All historical migrations are run whenever
a new environment is set up. This means your migrations will be run in every
future test run and in every future new production or development environment.
If your migration is only relevant to environments that already have data in the
old format, decorate it with ``@skip_on_fresh_install`` so that it is a noop for
new environments.
