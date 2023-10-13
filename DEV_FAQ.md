# Developer FAQ

This is a starting point for troubleshooting issues that frequently occur once your local environment
is set up and you've started working on a significant code change.

## General Advice

- Use the developers section of the [Dimagi Forum](https://forum.dimagi.com/) for help with issues.
- Some features are limited to specific software plans. Use the `make_domain_enterprise_level` command
to mark your local project as a test project and grant access to all features.

## Common Problems
> I created local forms and/or cases, but I don't see them in reports.

ElasticSearch data is out of date. See [ElasticSearch](https://github.com/dimagi/commcare-hq/blob/master/DEV_FAQ.md#elasticsearch) below.

> I created local cases, but some other part of HQ that filters by case type doesn't show my case types.

ElasticSearch data is out of date. See [ElasticSearch](https://github.com/dimagi/commcare-hq/blob/master/DEV_FAQ.md#elasticsearch) below.

> My local downloads/uploads aren't working

Look back over the [celery setup](https://github.com/dimagi/commcare-hq/blob/master/DEV_SETUP.md#running-commcare-hq).

Many background tasks on HQ will run fine locally, if you don't run celery but do have `CELERY_TASK_ALWAYS_EAGER=True` in local settings, but some do require celery (typically those that have a task and also a polling job, which is how most downloads and uploads work).

> My JS/LESS changes aren't showing up (caching, staticfiles)

Double check that your browser isn't caching. In Chrome, this is Dev Tools > Settings > Preferences > Network and check "Disable cache (while DevTools is open)"

Also double check that you're editing the source file, under `corehq/apps/<app_name>/static`, not a file in `staticfiles`

> Web Apps and/or App Preview aren't working at all

Formplayer isn't running properly. See [Formplayer](https://github.com/dimagi/commcare-hq/blob/master/DEV_FAQ.md#formplayer) below.

> My web server is throwing a slew of web socket errors

It happens, try restarting.

## Generating Sample Data

### SMS

Check out the `generate_fake_sms_data` command.

### Applications

If you have an application on commcarehq.org, follow [these instructions](https://confluence.dimagi.com/display/commcarepublic/Copying+an+Application+between+Projects+or+Servers) to copy it to your local environment.

There are also [three template apps](https://github.com/dimagi/commcare-hq/tree/master/corehq/apps/app_manager/static/app_manager/template_apps) checked into the codebase.
You can run [load_app_from_slug](https://github.com/dimagi/commcare-hq/blob/6021df8639dc0053c8dbdbb8690993be708776c5/corehq/apps/app_manager/views/apps.py#L510) in a django shell to import one of these apps. Note that you may wish to only run the first few lins of `load_app_from_slug` if you don't care about your app having multimedia.

### Cases

The easiest way to add cases locally is generally to use your local case importer. [Docs](https://confluence.dimagi.com/display/commcarepublic/Importing+Cases+Using+Excel)
for this are extensive, but at its most basic, you can just upload a single-column file with a bunch of case names to create cases.

### Cases + App + Data Dictionary

The `create_case_fixtures` command will add a sample app, a data dictionary, and a set of relevant cases.

## ElasticSearch

ElasticSearch is the data source for reports, exports, and an assortment of parts of other features.
Most issues with data not appearing locally, if you've already done something to create that data, are issues with ElasticSearch.

You can run ElasticSearch continuously, mimicking a production environment, or on an as-needed basis. Either one of these can be simpler,
depending on how much you're working with ES data.

As described in the [dev setup guide](https://github.com/dimagi/commcare-hq/blob/master/DEV_SETUP.md#running-commcare-hq), you can
use `run_ptop` to keep ES continually up to date.

Alternatively, you can run `ptop_reindexer_v2` as needed to sync individual indexes. `ptop_reindexer_v2` works on one index at a time.
Running it without any arguments will list the available indexes. The indexes you're most likely to use:
+ `sql-form` and `sql-case` populate form-based and case-based reports and exports
+ `user` and `group` may be useful, depending on what you're working on
+ `case_search` populates the Case list Explorer and Explore Case Data reports, as well as the case search/claim feature. For now, this data stands as a duplicate but different format of the origin `case` index and at some point in the future, features that use the legacy `case` index will move to using `case-search`.
+ `sms` populates messaging reports and SMS exports
+ You do **not** care about `case` or `form`, which are only used on legacy domains that store forms and cases in CouchDB.

## Formplayer

You can run formplayer either in Docker or as a standalone service. It's simpler to run via Docker.
If you're doing formplayer development, you'll need to run it as a separate service.

When troubleshooting formplayer in docker, use standard docker commands to view logs: `docker logs <formplayer_container_name>`

Formplayer expects HQ to be running on port 8000. If you run HQ on a different port, you'll need to modify settings and run formplayer outside of docker.

If you run formplayer as a separate service, make sure you're not acciddentally also running it in Docker - HQ's Docker script's `up` command will start it.

If you run into "Unable to connect" formplayer errors, try the following:
- Running formplayer as a standalone service instead of in Docker
- Visiting localhost:8000 instead of 0.0.0.0:8000 when using your locally run HQ app
- If running HQ app on 127.0.0.1:8000 and observe CORS error in browser's network tab while making API request to formplayer via localhost:8080, change HQ app url to use localhost:8000

See the [Formplayer README](https://github.com/dimagi/formplayer/blob/master/README.md)
and [Formplayer setup for HQ](https://github.com/dimagi/commcare-hq/blob/master/DEV_SETUP.md#formplayer).
