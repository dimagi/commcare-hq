Instances in suite.xml
======================

Instances are used to reference data beyond the scope of the current XML document.
Examples are the commcare session, casedb, lookup tables, mobile reports, case search data etc.

Instances are added into the suite file in `<entry>` elements and directly in the form XML. This is
done in post processing of the suite file in ``corehq.apps.app_manager.suite_xml.post_process.instances``.

How instances work
------------------
When running applications instances are initialized for the current context using an instance declaration
which ties the instance ID to the actual instance model:

    <instance id="my-instance" ref="jr://fixture/my-fixture" />

This allows using the fixture with the specified ID:

    instance('my-instance')path/to/node

From the mobile code point of view the ID is completely user defined and only used to 'register'
the instance in current context. The index 'ref' is used to determine which instance is attached
to the given ID.

Instances in CommCare HQ
------------------------
In CommCare HQ we allow app builders to reference instance in many places in the application
but don't require that the app builder define the full instance declaration.

When 'building' the app we rely on instance ID conventions to enable the build process to
determine what 'ref' to use for the instances used in the app.

For static instances like 'casedb' the instance ID must match a pre-defined name. For example
* casedb
* commcaresession
* groups

Other instances use a namespaced convention: "type:sub-type". For example:
* commcare-reports:<uuid>
* item-list:<fixture name>

Custom instances
----------------
There are two places in app builder where users can define custom instances:

* in a form using the 'CUSTOM_INSTANCES' plugin
* in 'Lookup Table Selection' case search properties under 'Advanced Lookup Table Options'
