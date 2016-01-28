HQ Management Commands
=======================

..
    Please add to and edit this doc as you see fit.
    Running the --help command will give you a docstring you can use
    in the definition.
    Include usage or an example if it's not obvious.
    Let's keep the definitions alphabetical for now, or else break it
    into logical sections.


This is a list of useful management commands.  They can be run using
``$ python manage.py <command>`` or ``$ ./manage.py <command>``.
For more information on a specific command, run
``$ ./manage.py <command> --help``

**bootstrap**
    Bootstrap a domain and user who owns it.
    Usage::
    $ ./manage.py bootstrap [options] <domain> <email> <password>

**bootstrap_app**
    Bootstrap an app in an existing domain.
    Usage::
    $ ./manage.py bootstrap_app [options] <domain_name> <app_name>

**clean_pyc**
    Removes all python bytecode (.pyc) compiled files from the project.

**copy_domain**
    Copies the contents of a domain to another database.
    Usage:: 
    $ ./manage.py copy_domain [options] <sourcedb> <domain>

**ptop_fast_reindex_fluff**
    Fast reindex of fluff docs.
    Usage::
    $ ./manage.py ptop_fast_reindex_fluff [options] <domain> <pillow_class>

**run_ptop**
    Run the pillowtop management command to scan all _changes feeds

**runserver**
    | Starts a lightweight web server for development which outputs additional debug information.
    | ``--werkzeug``  Tells Django to use the Werkzeug interactive debugger.

**syncdb**
    | Create the database tables for all apps in INSTALLED_APPS whose tables haven't already been created, except those which use migrations.
    | ``--migrate`` Tells South to also perform migrations after the sync.

**test**
    Runs the test suite for the specified applications, or the entire site if no apps are specified.
    Usage::
    $ ./manage.py test [options] [appname ...]
