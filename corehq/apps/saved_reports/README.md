# Saved Reports

This app manages the backend components of the Saved Reports and Scheduled Email Reports
features. For more information on this bundle of features, see
https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955322/Pre-Configured+Reports#Managing-Saved-and-Scheduled-Email-Reports.

The UI (urls, view code, JS) for saved reports, which unlike the backend is tightly coupled with
the rest of the reports UI, lives in the `reports` app. Otherwise `saved_reports` depends on
`reports`, but not the other way around.
