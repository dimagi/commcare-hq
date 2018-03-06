MOTECH
======

MOTECH is a Data Integration Layer that is currently integrated with CommCare.

History
-------

There was a previous version of MOTECH based on [OSGI](https://www.osgi.org/) and the [Spring Framework](https://projects.spring.io/spring-framework/) originally developed by the Grameen Foundation.  [Information on MOTECH 1.0 can be found here](http://docs.motechproject.org/en/latest/).  This platform was supporting both web-application use cases as well as data integration.  Due to the incompatability of OSGI and Spring in subsequent releases, MOTECH is now focused on data integration.

Currently, MOTECH is fully integrated to leverage CommCare's frameworks, including:

* To take advantage of CommCare HQ's multi-tenant architecture
* To make it easier and faster for CommCare HQ developers to maintain and extend it, considering CommCare integrations are the primary use case currently.

Framework
---------

MOTECH is designed to enable multiple types of integrations:

* Simple transactional integration where a single action triggers one or more atomic integrations with third-party systems in either direction.  An example is importing OpenMRS patients into CommCare.
* Complex transactional integration where a single action requires multiple API calls to complete the integration.  An example is a single registration form in CommCare generating a patient and encounter in OpenMRS.
* Aggregate data integration where multiple actions in CommCare are aggregated and the result is pushed to a third-party system.  An example is CommCare tranactional data being aggregated into a [Data Source](../apps/userreports/README.md) and being pushed to DHIS2 as aggregate data.

Current Integrations
--------------------

MOTECH Development has prioritized the integrations most commonly requested by our community, chief among them are:

* Custom trigger based on integrations
* DHIS2
* OpenMRS

Repeaters
---------

Repeaters allow integrators to send data from CommCare, formatted as JSON or XML, and send it as an authenticated user to a third-party system over HTTP(S).

DHIS2 Module
------------

[DHIS2](https://www.dhis2.org/) is a Health Information System that offers organisations and governments a visual dashboard of health-related data, across geographical areas, time periods, and demographics.

DHIS2 allows third-party systems like CommCare to send it two kinds of data:

* Data that pertains to single events and individuals, for DHIS2 to aggregate within DHIS2.
* Data that has already been aggregated

The DHIS2 integration module in MOTECH enables aggregate data to be sent to DHIS2.

We found that often DHIS2 was not configured to accept individual data, and would require the work of an administrator on behalf of the project organisation or government to set it up, which could be onerous. And so with MOTECH 2 we took the second approach.

Subsequently we have found a demand for both approaches, and so we may extend MOTECH to be able to to both.

CommCare aggregates and categorises data for DHIS2 using UCRs, and sends it at regular intervals.

Configuring a DHIS2 server is done under *Project Settings* > *DHIS2 Connection Settings*. Mapping UCR columns to DHIS2 data types is done under *Project Settings* > *DHIS2 DataSet Maps*


OpenMRS (& Bahmni) Module
-------------------------

[OpenMRS](https://openmrs.org/) is used for storing and managing patient data. [Bahmni](https://www.bahmni.org/) is an EMR and hospital system built on top of OpenMRS. Integration with Bahmni implies integration with OpenMRS.

Because there is quite a lot of overlap between the kind of data that CommCare uses and the kind that OpenMRS uses, integration between these two systems has the potential to be richer than the integration between CommCare and DHIS2.

OpenMRS integration is under development, and this information may date quickly.

CommCare can import data from OpenMRS using OpenMRS's Reporting API.

CommCare sends data to OpenMRS using its Web Services API. All data sent to OpenMRS relates to what OpenMRS refers to as "patients", "visits", "encounters" and "events". In CommCare these correspond to properties of one or a handful of case types, and values of some form questions. CommCare uses Repeaters to build and send a workflow of requests to OpenMRS, populated using both cases and forms.

Currently under development is the ability to import "live" (or very recent) changes from OpenMRS using its Atom Feed API. This will update CommCare cases, and will appear similar to the system form submissions of a case import.
