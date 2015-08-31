### Adding a new Privilege

To add a new `Privilege`

+ Make sure there are no existing Privileges that you can reuse
+ Add the new privilege in appropriate places in `privileges,py` according to software plans
+ Run `./manage.py schemamigration accounting <MIGRATION_NAME>` to create a migration
+ Make `forwards` method of the migration call the command `cchq_prbac_bootstrap`.
[Here](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/accounting/south_migrations/0036_update_privileges_custom_logo.py#L11) is an example.

This will create a new `Privilege` for you to use.

### Removing a deprecated Privilege

To remove an old `Privilege`

+ Remove occurrances of the desired Privilege from all the palces.
+ Add the privilege to `cchq_prabac_bootstrap.Command.OLD_PRIVILEGES`
+ Run migration

This will clean up discontinued privileges
