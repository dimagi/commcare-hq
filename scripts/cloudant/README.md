In all of the commands below, you will need `commcare-cloud` to be accessible
and you will need to replace `<env>` with the name of an environment (e.g. production).

Create all necessary databases
```
python scripts/cloudant/create_databases.py --databases `commcare-cloud <env> django-manage list_couchdbs` --username <myuser>
```

Generate a new api key and add it to all necessary dbs (read-only unless `--admin` is used)
```
python scripts/cloudant/generate_api_key.py --databases `commcare-cloud <env> django-manage list_couchdbs` --username <myuser>
```

Revoke a api key from all necessary dbs
```
python scripts/cloudant/revoke_api_key.py mynolongernecessaryapikey --databases `commcare-cloud <env> django-manage list_couchdbs` --username <myuser>
```

And for completeness, if you already have an API (and don't want to create a new one),
add it to all necessary dbs (read-only unless `--admin` is used)
```
python scripts/cloudant/grant_api_key.py myexistingapikey --databases `commcare-cloud <env> django-manage list_couchdbs` --username <myuser>
```
