# Upgrade to new version of Postgres in Docker

This example upgrades PostgreSQL 14.18 to 18.3. Substitute the versions you're upgrading to/from as needed below.

[!NOTE]
The data directory structure changed in postgres containers >= 18.
Previously data lived in ~/.local/share/dockerhq/postgresql/data.
Now data lives in ~/.local/share/dockerhq/postgresql/<major_version>/docker.

## Dump all databases to a file

Run the following command to make a backup of all postgres data in a local file:

```sh
docker exec -i hqservice-postgres-1 pg_dumpall -U commcarehq | gzip > pg-backup.sql.gz
```

Open the file with vim (or any editor that will automatically decompress the contents) and verify that it contains the expected content:

```sh
vim pg-backup.sql.gz
```

The first lines in the file should be something like

```sql
--
-- PostgreSQL database cluster dump
--
```

## Move the old data directory out of the way

Failing to do this step will prevent the new version of postgres from starting. A new data directory will be created automatically when the new version starts.

First, stop the postgresql service in docker:

```sh
# this uses the commcare-hq docker script
./scripts/docker stop postgres
```

Adjust `DATA_DIR` as needed to point to the place where docker stores data for postgres.

```sh
DATA_DIR=~/.local/share/dockerhq/postgresql
sudo mv $DATA_DIR ${DATA_DIR}14
```

The old data directory can be deleted when you're confident you will no longer need it.

## Upgrade docker image and start it

```sh
docker pull dimagi/docker-postgresql

# this uses the commcare-hq docker script
./scripts/docker up -d postgres  # --> Recreating hqservice-postgres-1
```

## Verify new database version

```sh
sudo ls $DATA_DIR  # should see a directory for 18
```

## Finally, restore the dumped databases

```sh
gzip -cd pg-backup.sql.gz | docker exec -i hqservice-postgres-1 psql -U commcarehq
# should see a lot of output here as databases are created, etc.
```

Reset commcarehq user password (adjust this command to set the password you use locally). This may only be necessary for some major version upgrades.
```sh
docker exec -i hqservice-postgres-1 psql -U commcarehq -c "ALTER USER commcarehq WITH PASSWORD 'commcarehq';"
```
