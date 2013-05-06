# Active Data Management Reports

## Enabling Projects

You can enable projects to view ADM reports in the Reports section of HQ
by adding the following document to your couchdb:

```{
    "_id": "ADM_ENABLED_DOMAINS",
    "domains": []
}```

Specify what domains you'd like to see ADM reports in the array `domains`.

## Configuring HQ

Visit `http://<CCHQ Instance>/adm` to configure ADM reports and columns available to HQ domains.
