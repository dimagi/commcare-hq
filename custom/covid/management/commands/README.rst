COVID Management Commands
^^^^^^^^^^^^^^^^^^^^^^^^^

So you need to run a script to update a lot of cases. You've come to the right place.

Most of these scripts build off of the base class ``CaseUpdateCommand``, which has the following features:

* Update all cases of a given type, or supply logic to select a subset

* Update cases in bulk

* Skip cases meeting specific criteria

* Run for either a single domain or a single domain plus all of its linked domains.

* Run as a particular user, or just default to SYSTEM_USER

* Throttle updates

* Log activity to a file

For most purposes, it's sufficient to inherit from ``CaseUpdateCommand`` and override ``case_blocks`` and possibly
``find_case_ids``.

For multi-purpose affairs, you may be able to modify or reference ``run_all_management_command``, which runs multiple
management commands across multiple domains.
