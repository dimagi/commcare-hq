#!/bin/sh
# This script is run by etc/cron.hourly
# So if you change staging, make sure you don't break this
#
# Log how often this script was called
date >> /tmp/staging_sync.log
# Run sync script
cd /var/django-sites/commcarehq_staging
/var/django-sites/commcarehq_staging/manage.py sync_schema -q dev.commcarehq.org brian test staging.commcarehq.org >> /tmp/staging_sync.log
cd /
