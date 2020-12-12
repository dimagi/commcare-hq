# Migrate Forms and Cases from Couch to SQL

The commands:

```sh
./manage.py migrate_domain_from_couch_to_sql --help
./manage.py migrate_multiple_domains_from_couch_to_sql --help
./manage.py couch_sql_diff --help
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
multi-process safe. Therefore, this should only be run when no other migration
command is currently running.

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

### Migrate multiple domains with downtime

Multiple domains can be migrated (serially) with form submissions disabled
while each migration is in progress. Each migration will be committed if it is
clean, and otherwise reset.

```sh
./manage.py migrate_multiple_domains_from_couch_to_sql domain-list.txt
```

## "Live" migration with minimal downtime

A "live" migration can be done on a large domain where the migration will take a
long time. A few hopefully infrequently used operations will be disabled for the
duration of the migration:

- Edit forms (only available on Pro plans and above)
- Delete or (un)archive form
- Delete or (un)archive user

Additionally, form submissions will be disabled for a short period (a few hours
at most) at the end of the migration to finalize the migration and do some
sanity checks to verify that everything was migrated as expected. Other than
these operations, the domain will be fully operational throughout the process.

IMPORTANT: Migration timelines and limited functionality expectations should be
confirmed before a live migration is started on an active domain. Use the
[support request template](#support-request-template) to initiate confirmation.

Starting a "live" migration:

```sh
./manage.py migrate_domain_from_couch_to_sql <domain> stats
./manage.py migrate_domain_from_couch_to_sql <domain> MIGRATE --live
./manage.py migrate_domain_from_couch_to_sql <domain> MIGRATE --patch  # if necessary
```

These commands can be run repeatedly until all forms and cases have been
migrated (except for any new forms submitted since one hour before the last
form was migrated). Diffs may be inspected, patched, and repaired as needed.

After the initial `MIGRATE --live` command is run the domain will remain in
"live" migration state, regardless of whether the `--live` switch is used on
subsequent `MIGRATE` commands, until `MIGRATE --finish` is run.

When all not-freshly-submitted forms and cases have been migrated and diffs
patched or otherwise resolved, these final commands must be run to finish and
commit the migration. Form submissions will be disabled ("downtime" is instated)
from the time when `MIGRATE --finish` starts until `COMMIT` is completed.

```sh
./manage.py migrate_domain_from_couch_to_sql <domain> MIGRATE --finish
./manage.py migrate_domain_from_couch_to_sql <domain> COMMIT
```

### Live-migrate multiple domains

Multiple live migrations can be started with a single command:

```sh
./manage.py migrate_multiple_domains_from_couch_to_sql --live domain-list.txt
```

Each live migration started this way can be inspected and patched as needed.
The final `MIGRATE --finish` and `COMMIT` steps must be done individually for
each domain.

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
as a persistent data trail.

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

We are planning to migrate the XXXXXXX domain forms and cases from Couch to SQL. No need to mention Couch or SQL to the customer though, to them it's maintenance we need to do to keep our systems operating at peak performance.

The XXXXXXX domain currently has about XXXXXXX forms, which we expect to take about XXXXXXX to migrate. The following operations will be disabled while the migration is in progress:

- Edit forms
- Delete or (un)archive form
- Delete or (un)archive user

Additionally, form submissions will be disabled for a short period (a few hours at most) at the end of the migration to finalize the migration and do some sanity checks to verify that everything was migrated as expected. All other features of CommCare will continue to operate normally throughout the migration.

Please schedule a time for this to be done and confirm that the customer will be able to operate with the above-mentioned constraints. Thank you!
