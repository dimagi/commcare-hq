# Context
Right now it's not possible to view context about what data was exported
when someone downloads an export.

# Goal

https://dimagi.atlassian.net/browse/SAAS-19581

When someone downloads an export, our system should record a summary of the export:

- the type of export (form, case, sms, etc.)
- the subtype (form type, case type, etc.)
- the filters applied
- the columns (questions / properties) included
- the number of rows returned

as well as the timestamp when the download occurred.

This can be as simple as just a logging.info call when an export is successfully generated and ready for download.
(It should include the download id so we can see if it was actually downloaded.)

We want to make sure we're logging enough information to be helpful,
without incurring disproportionate costs due to the quantity of bytes logged, searched, and stored.
Log files are shipped to CloudWatch Logs where they are stored semi-permanently (at least 6 years).
