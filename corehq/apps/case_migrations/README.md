# Case Migrations

This feature allows technical users to handle their own case migrations using xforms.

## Current components

* Basic form to trigger a case migration
* Restore endpoint to be used by webapps

## TODOs

* WebApps component to run a migration
  * `send_migration_to_nimbus` should do what it says
  * Web apps can then send each case ID to
    `/a/<domain>/case_migrations/restore/<case_id>/`
    to get a restore containing that case's network.
* Store migrations in a DB
* One-click revert
