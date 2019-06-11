# ICDS Migration from PostgreSQL to CitusDB

## Pre migration setup

1. CitusDB cluster fully set up and ready for production use with database created.
    * Ensure [citus.shard_count](https://github.com/dimagi/commcare-cloud/blob/e2d5865a9edfe1306e325051ef8e4973f685d20a/environments/india/postgresql.yml#L59) is set as desired.
3. Update Django settings with new DB:
    * In `DATABASES`
    * In `REPORTING_DATABASES` with key `'icds-ucr-citus'`
4. Check that the following toggles are **disabled** for the ICDS domain:
    * ENABLE_UCR_MIRRORS
    * PARALLEL_AGGREGATION
5. Add mirror engine IDs to all ICDS UCRs for the env:
   ```
   {
      "server_environment": "icds",
      "engine_ids": ["icds-ucr-citus"]
   }
   ```

## Migration process

1. Run migrations on CitusDB to create top level aggregation tables and UCR tables

    ```
    $ python manage.py bootstrap_icds_citus icds-ucr-citus
    ```

2. Create child tables on CitusDB

    ```
    $ python manage.py create_citus_child_tables -s <source engine ID> -t icds-ucr-citus [--dry-run]
    ```

    This can be run multiple times to create additional tables

3. Generate migration database

    ```
    $ python manage.py generate_migration_tables <path to output> --source-engine-id <source engine ID>
    ```

    This will create a Sqlite database at the given path containing:

    * one row per table to migrate
    * date of the given table (based on the table name or check constraint)
    * target table to copy the data into
    * migrated status

4. Copy the data

    Using the `custom/icds_reports/scripts/migrate_tables.py` script repeatedly top copy the data.

    ```
    $ python migrate_tables.py --help
    usage: migrate_tables.py [-h] -D SOURCE_DB -O SOURCE_HOST -U SOURCE_USER -d
                             TARGET_DB -o TARGET_HOST -u TARGET_USER
                             [--start-date START_DATE] [--end-date END_DATE]
                             [--start-after-table START_AFTER_TABLE]
                             [--table TABLE] [--confirm] [--dry-run]
                             [--parallel PARALLEL]
                             db_path

    Migrate DB tables from one DB to another using pg_dump. Compainion to
    custom/icds_reports/management_commands/generate_migration_tables.py

    positional arguments:
      db_path               Path to sqlite DB containing list of tables to migrate

    optional arguments:
      -h, --help            show this help message and exit
      -D SOURCE_DB, --source-db SOURCE_DB
                            Name for source database
      -O SOURCE_HOST, --source-host SOURCE_HOST
                            Name for source database
      -U SOURCE_USER, --source-user SOURCE_USER
                            Name for source database
      -d TARGET_DB, --target-db TARGET_DB
                            Name for target database
      -o TARGET_HOST, --target-host TARGET_HOST
                            Name for target database
      -u TARGET_USER, --target-user TARGET_USER
                            PG user to connect to target DB as. This user should
                            be able to connect to the targetDB without a password.
      --start-date START_DATE
                            Only migrate tables with date on or after this date.
                            Format YYYY-MM-DD
      --end-date END_DATE   Only migrate tables with date before this date. Format
                            YYYY-MM-DD
      --start-after-table START_AFTER_TABLE
                            Skip all tables up to and including this one
      --table TABLE         Only migrate this table
      --confirm             Confirm before each table.
      --dry-run             Only output the commands.
      --parallel PARALLEL   How many commands to run in parallel
    ```

    Notes:
    * For best performance run this either on the source DB host or the target DB host. You can copy the
      script to the host and it should not require any additional libraries to be installed other than python
      itself.
    * For authentication set up a [pgpass](https://www.postgresql.org/docs/9.6/libpq-pgpass.html) file
      for the user running the script.
    * Use `--parallel` to run multiple dumps in parallel
    * The Sqlite database will get updated after each successfull migration so re-running the command after error
      should be safe and will not re-migrate data.
    * Use `--dry-run` to check the command that will be run

5. Repeat step 4 for additional database to be migrated

    e.g. `commcarehq_icds_aggregatedata` on `pgnondashboarducr0`

## Post migration steps:
1. Enable the following toggles:
  * ENABLE_UCR_MIRRORS
  * PARALLEL_AGGREGATION
  * ICDS_COMPARE_QUERIES_AGAINST_CITUS
2. Validate that new data is being added to both databases
