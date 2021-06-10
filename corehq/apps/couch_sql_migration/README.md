# Migrate Forms and Cases from Couch to SQL

The commands:

```sh
./manage.py couch_domain_report --help
./manage.py migrate_multiple_domains_from_couch_to_sql --help
./manage.py migrate_domain_from_couch_to_sql --help
./manage.py couch_sql_diff --help
```

## Setup

First, from a machine where you have `commcare-cloud` installed, check if there
are any Couch domains that need to be migrated:

```sh
commcare-cloud <env> django-manage couch_domain_report
```

You can stop here if the total at the bottom of the report is zero. Your
environment does not need to be migrated. On the other hand, if the total is
non-zero, proceed to setup and run migrations.

The migration commands outlined in this document are typically run on a "limited
release" on a machine in your CommCareHQ cluster, usually the `django_manage`
machine. 8GB of RAM is recommended, although small domains may require less.
It is also recommended to use a tmux or screen session so that network
disruptions between your workstation and the `django_manage` machine do not
interrupt migration processes. Proceed to setup a limited release and tmux or screen
session:

```sh
ENV=<your-env-name>

commcare-cloud $ENV fab setup_limited_release:keep_days=30
# make a note of the release directory path

# start a screen session
commcare-cloud $ENV ssh django_manage -t screen -S forms-migration

# if the connection drops, use the following command to reconnect
commcare-cloud $ENV ssh django_manage -t screen -x forms-migration

# in the screen session
sudo -iu cchq
export RELEASE_PATH=...  # set to the limited release path created above
export CCHQ_MIGRATION_STATE_DIR=~/forms-migration  # customize path as desired
mkdir $CCHQ_MIGRATION_STATE_DIR
cd $RELEASE_PATH
source python_env-3.6/bin/activate
```

Continuing in the screen session, run the `couch_domain_report` command again
with the `--output-dir=...` option.

```sh
./manage.py couch_domain_report --output-dir=$CCHQ_MIGRATION_STATE_DIR
```

Text files containing lists of domains will be created for various domain size
categories. Additionally a `domains.csv` file is created with all domains to be
migrated along with various statistics including an estimate of migration time.
It may be useful to copy the CSV data into an Excel document to track progress,
marking each row as it is completed. Migrations may be run in batches or
individually for larger domains. For example, to migrate all domains that have
no forms:

```sh
./manage.py migrate_multiple_domains_from_couch_to_sql --live $CCHQ_MIGRATION_STATE_DIR/no_forms.txt
```

## Migration status (`stats`)

At any time before, during, or after a migration, the `stats` sub-command may
be used to inspect migration state, including whether a migration is in
progress, how many forms and cases have been migrated, diff counts, etc.

```sh
./manage.py migrate_domain_from_couch_to_sql <domain> stats
```

In general it is unsafe to run multiple migration command processes on a domain
simultaneously because the underlying state storage (a SQLite database) is not
multi-process safe. Therefore, this (or any other command) should only be run
when no other migration command is currently running on the domain.

### `stats` output columns

- **Docs**: number of documents migrated.
- **Diffs**: number of documents with unexpected differences between the Couch and
  SQL version. It may be necessary to run `couch_sql_diff ... filter` after
  various operations (e.g., `--patch`) to recalculate this column.
- **Missing**: number of documents found in Couch but not SQL. This can be updated
  with the `--missing-docs=...` option.
- **Changes**: number of documents with patchable differences between the Couch and
  SQL version. Diffs are put in this category if they are a result of a known
  difference between the Couch and SQL form processors.

## Migrating domains

One or more domains can be migrated (serially) with a single command.

```sh
./manage.py migrate_multiple_domains_from_couch_to_sql --live domain-list.txt
# domain_list.txt must contain a single domain name to be migrated on each line
```

Alternate command syntax: list one or more domain(s) on the command line. Note
the colon (`:`) before each domain name.

```sh
./manage.py migrate_multiple_domains_from_couch_to_sql --live :domain1:domain2...
```

There will be a very short period during each domain migration in which form
submissions are disabled for the domain. It is short enough that end users are
very unlikely to notice.

At the end of each migration it will be committed if it is clean (if there are
no unresolved diffs), and otherwise left in a "live" migrating state where diffs
can be inspected and patched as needed. If the migration is not committed it
must be finished and committed manually (see next section).

## "Live" migration with minimal downtime

A "live" migration can be done on a domain where the migration may take a long
time. A few hopefully infrequently used operations will be disabled while the
migration is in "live" (or `dry_run`) mode:

- Edit forms (only available on Pro plans and above)
- Delete or (un)archive form
- Delete or (un)archive user

Additionally, form submissions will be disabled for a short period at the end of
the migration to finalize the migration and do some sanity checks to verify that
the migration was successful. Other than these operations, the domain will be
fully operational throughout the process.

Starting or continuing a "live" migration:

```sh
./manage.py migrate_domain_from_couch_to_sql <domain> MIGRATE --live

# inspect and patch diffs as necessary
./manage.py couch_sql_diff <domain> show --select=<doc_type> [--changes]
./manage.py migrate_domain_from_couch_to_sql <domain> MIGRATE --patch
```

These commands can be run repeatedly until all forms and cases have been
migrated. Diffs may be inspected, patched, and repaired as needed.

After the initial `MIGRATE --live` command is run the domain will remain in
"live" migration state, regardless of whether the `--live` switch is used on
subsequent `MIGRATE` commands, until `MIGRATE --finish` is run.

It may be necessary to run `MIGRATE --finish` _before_ patching diffs if they
affect cases that were modified within an hour of the most recent `--live`
migration completion. Therefore it is a good idea to use `--finish` before
patching diffs on active domains. This implies a longer period where form
submissions are disabled. It is possible to `unfinish` (revert to "live" mode)
if `--finish` is run, and then it is not possible to patch all diffs in a timely
manner.

```sh
./manage.py migrate_domain_from_couch_to_sql <domain> unfinish
```

IMPORTANT: do not run multiple migration commands concurrently for a given
domain. Wait for each command to complete before running the next. If necessary,
a migration may be interrupted with a keyboard interrupt (^C, `SIGINT`). The
migration will attempt a clean exit on receiving the first interrupt (this may
take a few minutes). It will exit immedately on the second interrupt, but may be
left in an unclean state and need to be `reset` to ensure complete migration. In
general it is best to wait for clean exit.

Diffs and changes of the following doc types are usually unimportant and may be
ignored after initial inspection to verify they are unimportant:

- CommCareCase-Deleted
- XFormArchived
- XFormDeprecated
- XFormDuplicate
- XFormError
- XFormInstance-Deleted
- HQSubmission
- SubmissionErrorLog

Full documents may be inspected by a superuser using the `raw_doc` view on the
HQ website of the environment where the migration is being performed:

`https://<site_name>/hq/admin/raw_doc/?id=<doc_id>`

Additionally, after inspecting diffs of other doc types (XFormInstance,
CommCareCase) most turn out to be unimportant. For example, the form or case may
be very old or the diff may be insignificant such as a date format change. In
most cases a record of CommCareCase diffs will be saved in a patch form (after
running `--patch`) regardless of whether it could be patched or not, leaving an
audit trail of differences between Couch and SQL cases. This can be verified by
inspecting the last (SQL) form applied to the case after patching.

When all diffs have been patched or otherwise resolved, these final commands
must be run to finish and commit the migration. Form submissions will be
disabled ("downtime" is instated) from the time when `MIGRATE --finish` starts
until `COMMIT` is completed.

```sh
./manage.py migrate_domain_from_couch_to_sql <domain> MIGRATE --finish
./manage.py migrate_domain_from_couch_to_sql <domain> COMMIT
```

After `COMMIT` has successfully run (and the prompt is acknowledged) the domain
will be switched to use the SQL backend. This operation cannot be undone.

## Migrate a single domain with downtime

This process can be used for small domains and/or domains where it does not
matter if form submissions are disabled for an extended period of time.

```sh
./manage.py migrate_domain_from_couch_to_sql <domain> stats
./manage.py migrate_domain_from_couch_to_sql <domain> MIGRATE
./manage.py migrate_domain_from_couch_to_sql <domain> COMMIT  # if clean
```

A migration can be "reset" if there are unresolvable issues that prevent it from
being committed. All migration state will be discarded when this is done. A new
migration can be run at a later time.

```sh
./manage.py migrate_domain_from_couch_to_sql <domain> reset
```

## Patching case diffs

The `MIGRATE --patch` command will patch case _diffs_ and _changes_ to make the
new SQL case look like the old Couch case as much as possible. Discrepancies are
usually the result of bad data states in Couch (causing "diffs") as well as
known differences between the Couch and SQL form processing logic (causing
"changes"). Patching is done by submitting a "patch" form after the case has
been migrated. Each patch form contains a "diff block" with precise details
about what was patched. The diff block contains enough detail to reconstruct
the case as it was before it was patched.

Once a _diff_ or _change_ has been patched it will be removed from the "Diffs"
or "Changes" counts tracked by the `stats` command. This is done even if the
difference could not actually be patched. For example, `opened_by` cannot be
patched because it is a calculated property based on the order in which forms
were submitted. Once a case has been patched and there are no more unpatched
differences its migration is considered to be complete with the patch form left
as a persistent audit trail.

`MIGRATE --patch` is a convenience that performs the operations of a few other
commands. Sometimes it is useful to run those commands individually to debug
the process or inspect intermediate state.

```sh
./manage.py migrate_domain_from_couch_to_sql <domain> MIGRATE --forms=missing
./manage.py couch_sql_diff <domain> patch ...
./manage.py couch_sql_diff <domain> cases --select=pending
```

## Scanning for missing documents

It can be useful to run `--missing-docs=rebuild` as a sanity check toward the
end of very large/long migrations. This will update the missing document counts
reported by the `stats` command. See the `--help` documentation for more
details. Note: a scan for missing documents takes a very small fraction of the
time needed to do a full migration (one million documents can be scanned in a
few minutes).

## Migration sheduling template

Submit the following (replacing XXXXXXX appropriately) to

https://dimagi-dev.atlassian.net/servicedesk/customer/portal/1

## Support request template

Subject: XXXXXXX forms & cases migration

We are planning to migrate the XXXXXXX domain forms and cases from Couch to SQL. No need to mention Couch or SQL to the customer though, to them it's maintenance we need to do to keep our systems operating at peak performance.

The XXXXXXX domain currently has about XXXXXXX forms, which we expect to take about XXXXXXX to migrate. The following operations will be disabled while the migration is in progress:

- Edit forms
- Delete or (un)archive form
- Delete or (un)archive user

Additionally, form submissions will be disabled for a short period (a few hours at most) at the end of the migration to finalize the migration and do some sanity checks to verify that everything was migrated as expected. All other features of CommCare will continue to operate normally throughout the migration.

Please schedule a time for this to be done and confirm that the customer will be able to operate with the above-mentioned constraints. Thank you!
