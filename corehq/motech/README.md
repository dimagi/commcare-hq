MOTECH
======

This document uses "MOTECH" and "MOTECH 2" interchangeably.

MOTECH is how CommCare interfaces with other systems.


History
-------

What we now refer to as "MOTECH 1" is a product developed by the Grameen Foundation, and works with CommCare to interface with other systems.

Dimagi chose to develop the functionality relevant to CommCare into the CommCare HQ platform for a range of reasons, including:

* To take advantage of CommCare HQ's multi-tenant architecture (MOTECH 1 required installing a separate instance for each project)
* To make it easier and faster for CommCare HQ developers to maintain and extend it
* Tighter coupling with CommCare, for the opportunity to improve the CommCare-related functionality for integrations

This functionality is what we now refer to as "MOTECH", or "MOTECH 2" to differentiate it from "MOTECH 1".


Current Integrations
--------------------

MOTECH 2 development has prioritized the integrations needed most by partners and projects. Chief among these are:

* DHIS2
* OpenMRS

MOTECH-related settings are found under *Project Settings* in CommCare HQ. MOTECH code is located in the corehq/motech/ directory.


DHIS2 Integration
-----------------

DHIS2 is a Health Information System that offers organisations and governments a visual dashboard of health-related data, across geographical areas, time periods, and demographics.

DHIS2 allows third-party systems like CommCare to send it two kinds of data:

* Data that pertains to single events and individuals, for DHIS2 to aggregate
* Data that has already been aggregated and categorized as DHIS2 would

MOTECH 1 took the first approach.

We found that often DHIS2 was not configured to accept this data, and would require the work of an administrator on behalf of the project organisation or government to set it up, which could be onerous. And so with MOTECH 2 we took the second approach.

Subsequently we have found a demand for both approaches, and so we may extend MOTECH to be able to to both.

CommCare aggregates and categorises data for DHIS2 using UCRs, and sends it at regular intervals.

Configuring a DHIS2 server is done under *Project Settings* > *DHIS2 Connection Settings*. Mapping UCR columns to DHIS2 data types is done under *Project Settings* > *DHIS2 DataSet Maps*


OpenMRS & Bahmni Integration
----------------------------

OpenMRS is used for storing and managing patient data. Bahmni is a hospital management system built on top of OpenMRS. Integration with Bahmni implies integration with OpenMRS.

Because there is quite a lot of overlap between the kind of data that CommCare uses and the kind that OpenMRS uses, integration between these two systems has the potential to be richer than the integration between CommCare and DHIS2.

OpenMRS integration is under development, and this information may date quickly.

CommCare can import data from OpenMRS using OpenMRS's Reporting API.

CommCare sends data to OpenMRS using its Web Services API. All data sent to OpenMRS relates to what OpenMRS refers to as "patients", "visits", "encounters" and "events". In CommCare these correspond to properties of one or a handful of case types, and values of some form questions. CommCare uses Repeaters to build and send a workflow of requests to OpenMRS, populated using both cases and forms.

Currently under development is the ability to import "live" (or very recent) changes from OpenMRS using its Atom Feed API. This will update CommCare cases, and will appear similar to the system form submissions of a case import.
