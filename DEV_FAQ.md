Developer FAQ
-------------

This is a starting point for troubleshooting issues that frequently occur once your local environment
is set up and you've started working on a singnificant code change.

# General Advice

- Use the developers section of the [Dimagi Forum](https://forum.dimagi.com/) for help with issues.
- Some features are limited to specific software plans. Visit Project Settings > Internal Subscription Management
to mark your local project as a test project and grant access to all features.

# Common Problems
+ I created local forms and/or cases, but I don't see them in reports.
   + ElasticSearch data is out of date. See [#ElasticSearch](#ElasticSearch)
+ I created local cases, but some other part of HQ that filters by case type doesn't show my case types.
   + ElasticSearch data is out of date. See [#ElasticSearch](#ElasticSearch)
+ My local downloads/uploads aren't working
   + Look back over the [celery setup](https://github.com/dimagi/commcare-hq/blob/master/DEV_SETUP.md#running-commcare-hq).
   + Many background tasks on HQ will run fine locally, if you don't run celery but do have `CELERY_TASK_ALWAYS_EAGER=True` in local settings, but some do require celery (typically those that have a task and also a polling job, which is how most downloads and uploads work).
+ My JS/LESS changes aren't showing up (caching, staticfiles)
   + Double check that your browser isn't caching. In Chrome, this is Dev Tools > Settings > Preferences > Network and check "Disable cache (while DevTools is open)"
   + Double check that you're editing the source file, under `corehq/apps/<app_name>/static`, not a file in `staticfiles`
+ Web Apps and/or App Preview aren't working at all
   + Formplayer isn't running properly. See [#Formplayer](#Formplayer)
+ My web server is throwing a slew of web socket errors
   + It happens, try restarting.

+ Running Tests TODO pull from DEV_SETUP
+ Generating Sample Data
+ ElasticSearch TODO pull from document
+ Formplayer TODO pull from document