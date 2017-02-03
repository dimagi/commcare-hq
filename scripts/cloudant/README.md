Before trying to use the following commands,
make sure your localsettings are set to the same db prefix as you're trying to create
on cloudant (e.g. `commcarehq` or `staging_commcarehq`).
The examples below, replace `<myuser>` with the username of the cloudant account
you want to run the operation for.

Create all necessary databases
```
python scripts/cloudant/create_databases.py --databases `./manage.py list_couchdbs` --username <myuser>
```

Generate a new api key and add it to all necessary dbs (read-only unless `--admin` is used)
```
python scripts/cloudant/generate_api_key.py --databases `./manage.py list_couchdbs` --username <myuser>
```

Revoke a api key from all necessary dbs
```
python scripts/cloudant/revoke_api_key.py mynolongernecessaryapikey --databases `./manage.py list_couchdbs` --username <myuser>
```

And for completeness, if you already have an API (and don't want to create a new one),
add it to all necessary dbs (read-only unless `--admin` is used)
```
python scripts/cloudant/grant_api_key.py myexistingapikey --databases `./manage.py list_couchdbs` --username <myuser>
```
