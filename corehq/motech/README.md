MOTECH
======

MOTECH is a Data Integration Layer

It allows sending simple and aggregate data payloads to third-party
systems when certain triggers are met. Triggers and Payloads are easily
defined through custom methods in the MOTECH codebase, and a full suite
of management tools is available to audit and debug sent, queued and
cancelled messages.

Currently, MOTECH is fully integrated to leverage CommCare's frameworks,
including:

* To take advantage of CommCare HQ's multi-tenant architecture
* To make it easier and faster for CommCare HQ developers to maintain
and extend it, considering CommCare integrations are the primary use
case currently.
* If you are interesting in using this without the full CommCare
scaffolding, please reach out to the mailing list to discuss.


Framework
---------

MOTECH is designed to enable multiple types of integration:

* Simple transactional integration where a single action triggers one or
more atomic messages with third-party systems in either direction.  An
example is importing OpenMRS patients into CommCare.
* Complex transactional integration where a single action requires
multiple API calls to complete the integration.  An example is a single
registration form in CommCare generating a patient and encounter in
OpenMRS.
* Aggregate data integration where multiple actions in CommCare are
aggregated and the result is pushed to a third-party system.  An example
is CommCare transactional data being aggregated into a
[Data Source](../apps/userreports/README.md) and being pushed to DHIS2
as aggregate data.


Current Integrations
--------------------

MOTECH currently allows for the following integrations:

* Standard trigger-based integration which forwards all CommCare Case,
Form or Application data to any third-party endpoint. This requires no
code, and is easily configured through a UI.
* Custom trigger-based integrations sending custom payloads to any
third-party endpoint. Triggers and Payloads are defined in code.
* DHIS2
* OpenMRS


Repeaters
---------

Repeaters allow integrators to send data from CommCare and send it as an
authenticated user to third-party systems over HTTP or HTTPS.

MOTECH ships with a suite of **standard repeaters** which can be enabled
through the MOTECH management dashboard. These send all case, form, or
application data to any third-party endpoint. The payload for these is
sent whenever a change is detected. The schema is
[predefined](https://confluence.dimagi.com/pages/viewpage.action?pageId=12224128)
and can be sent as either `XML` or `JSON`.

All repeaters are hooked into the **MOTECH management dashboard**. This
allows project managers to create and delete specific repeater
instances, and contains tools to audit and debug sent, queued and
cancelled messages.

For developer documentation, see the module docstring in
[repeaters/models.py](./repeaters/models.py).


The DHIS2 Module
----------------

[DHIS2](https://www.dhis2.org/) is a Health Information System that
offers organisations and governments a visual dashboard of
health-related data, across geographical areas, time periods, and
demographics.

DHIS2 allows third-party systems like CommCare to send it two kinds of
data:

* Data that pertains to single events and individuals, to be aggregated
by DHIS2
* Data that has already been aggregated

The MOTECH DHIS2 module is able to send both kinds of data.

See the [MOTECH DHIS2 module documentation](./dhis2/README.md) for more
information on configuring and managing integrations with DHIS2.


The OpenMRS & Bahmni Module
---------------------------

[OpenMRS](https://openmrs.org/) is used for storing and managing patient
data. [Bahmni](https://www.bahmni.org/) is an EMR and hospital system
built on top of OpenMRS. Integration with Bahmni implies integration
with OpenMRS.

### Importing data from OpenMRS to CommCare

MOTECH can import data into CommCare from OpenMRS using OpenMRS's
Reporting API and OpenMRS's Atom feed API. The Reporting API is used for
periodic imports, for example monthly. The Atom feed API is for
importing data as it is added or changed in OpenMRS.

### Sending data from CommCare to OpenMRS

MOTECH sends CommCare data to OpenMRS using OpenMRS's Web Services API.

All data sent to OpenMRS relates to what OpenMRS refers to as
"patients", "visits", "encounters" and "observations". Values from
CommCare can be retrieved from case properties, form questions,
locations, etc.

MOTECH sends a workflow of requests to OpenMRS to update patients and
create visits, encounters and observations.

Using MOTECH Data Forwarding in conjunction with OpenMRS's Atom feed
allows bidirectional live updates.

See the [MOTECH OpenMRS and Bahmni module documentation](./openmrs/docs/index.rst)
for more information on configuring and managing integrations with DHIS2.


History
-------

There was a previous version of MOTECH based on
[OSGI](https://www.osgi.org/) and the
[Spring Framework](https://projects.spring.io/spring-framework/)
originally developed by the Grameen Foundation.  Information on MOTECH
1.0 can be found [here](http://docs.motechproject.org/en/latest/). This
platform supported both web-application use cases as well as data
integration.  Due to the incompatability of OSGI and Spring in
subsequent releases, MOTECH is now focused on data integration.
