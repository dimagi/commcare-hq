### Adding a new Privilege

To add a new `Privilege`

+ Make sure there are no existing Privileges that you can reuse
+ Add the new privilege in appropriate places in `privileges.py` according to software plans
+ Run `python manage.py makemigrations --empty accounting` to create a migration
+ Rename the migration file to something more meaningful. (From Django 1.8+ you can supply a name to the makemigrations command: --name <migration_name>)
+ Add the following operation to the list of operations:

```python
migrations.RunPython(cchq_prbac_bootstrap),
```

This will create a new `Privilege` for you to use. See (Django data migrations)[https://docs.djangoproject.com/en/1.8/topics/migrations/#data-migrations] for more information.

### Removing a deprecated Privilege

To remove an old `Privilege`

+ Remove occurrences of the desired Privilege from all the places.
+ Add the privilege to `cchq_prabac_bootstrap.Command.OLD_PRIVILEGES`
+ Run migration

This will clean up discontinued privileges.
