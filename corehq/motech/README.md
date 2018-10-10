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
is CommCare tranactional data being aggregated into a
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

**Custom repeaters** are defined in code, and subclass any of the
`BaseRepeater` classes. They allow the developer to create custom
payloads that can compile data from multiple sources and be sent in any
format, including `JSON`, `XML` and `SOAP`. Custom triggers for when to
send this data are also defined in code. These trigger methods are run
whenever the model in question (`case`, `form`, or `application`) is
changed.

All repeaters are hooked into the **MOTECH management dashboard**. This
allows project managers to create and delete specific repeater
instances, and contains tools to audit and debug sent, queued and
cancelled messages.

You can find more details in [the Repeaters README](./repeaters/README.md).


DHIS2 Module
------------

[DHIS2](https://www.dhis2.org/) is a Health Information System that
offers organisations and governments a visual dashboard of health-
related data, across geographical areas, time periods, and demographics.

DHIS2 allows third-party systems like CommCare to send it two kinds of
data:

* Data that pertains to single events and individuals, for DHIS2 to
aggregate within DHIS2.
* Data that has already been aggregated

The DHIS2 integration module in MOTECH enables aggregate data to be sent
to DHIS2. Currently, the DHIS2 module does not send individual data.

CommCare aggregates and categorises data for DHIS2 using UCRs, and sends
it at regular intervals.

Configuring a DHIS2 server is done under *Project Settings* >
*DHIS2 Connection Settings*. Mapping UCR columns to DHIS2 data types is
done under *Project Settings* > *DHIS2 DataSet Maps*


OpenMRS (& Bahmni) Module
-------------------------

[OpenMRS](https://openmrs.org/) is used for storing and managing patient
data. [Bahmni](https://www.bahmni.org/) is an EMR and hospital system
built on top of OpenMRS. Integration with Bahmni implies integration
with OpenMRS.

### Importing data from OpenMRS to CommCare
CommCare can import data from OpenMRS using OpenMRS's Reporting API.

### Sending data from CommCare to OpenMRS
CommCare sends data to OpenMRS using its Web Services API.

All data sent to OpenMRS relates to what OpenMRS refers to as
"patients", "visits", "encounters" and "events". In CommCare these
correspond to properties of one or a handful of case types, and values
of some form questions.

CommCare uses Repeaters to build and send a workflow of requests to
OpenMRS, populated using both cases and forms.


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
