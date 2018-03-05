MOTECH
======

MOTECH is a Data Integration Layer that is currently integrated with CommCare.  

History
-------

There was a previous version of MOTECH based on OSGI and the Spring Framework originally developed by the Grameen Foundation.  Information on MOTECH 1.0 can be found [HERE] <- (Insert links to MOTECH 1.0 documentation).  This platform was supporting both web-application use cases as well as data integration.  Due to the incompatability of OSGI and Spring in subsequent releases, MOTECH is now focused on data integration. 

Currently, MOTECH is fully integrated to leverage CommCare's frameworks, including:  

* To take advantage of CommCare HQ's multi-tenant architecture
* To make it easier and faster for CommCare HQ developers to maintain and extend it, considering CommCare integrations are the primary use case currently. 

Framework
--------------------

MOTECH is designed to enable multiple types of integrations:  

* Simple Transactional integration where a single action triggers one or more atomic integrations with 3rd party systems in either direction.  An exmaple is [INSERT HERE]
* Complex Transactional integration where a single action requires multiple API calls to complete the integration and cannot recover gracefully if a failure between calls occurs.  An example is a single registration form in CommCare generating a patient and encounter in OpenMRS.    
* Aggregate data integration where multiple actions in CommCare are aggregated an the result is pushed to a 3rd party system.  An example is CommCare tranactional data being aggregated into a Data Source (INSERT LINK) and being pushed to DHIS2 as aggregate data.  

Current Integrations
--------------------

MOTECH Development has prioritized the integrations most commonly requested by our community, chief among them are:

* Custom trigger based on integrations
* DHIS2
* OpenMRS

Repeaters
-----------------
Repeaters is the way to.... [INSERT HERE]

DHIS2 Module
-----------------

DHIS2 is a Health Information System that offers organisations and governments a visual dashboard of health-related data, across geographical areas, time periods, and demographics: [INSERT LINK]

DHIS2 allows third-party systems like CommCare to send it two kinds of data:

* Data that pertains to single events and individuals, for DHIS2 to aggregate within DHIS2.
* Data that has already been aggregated

The DHIS2 integration module in MOTECH enables aggregate data to be sent to DHIS2.  Individual data can be sent vi
MOTECH 1 took the first approach.

We found that often DHIS2 was not configured to accept this data, and would require the work of an administrator on behalf of the project organisation or government to set it up, which could be onerous. And so with MOTECH 2 we took the second approach.

Subsequently we have found a demand for both approaches, and so we may extend MOTECH to be able to to both.

CommCare aggregates and categorises data for DHIS2 using UCRs, and sends it at regular intervals.

Configuring a DHIS2 server is done under *Project Settings* > *DHIS2 Connection Settings*. Mapping UCR columns to DHIS2 data types is done under *Project Settings* > *DHIS2 DataSet Maps*


OpenMRS (& Bahmni) Module
----------------------------

OpenMRS is used for storing and managing patient data. Bahmni is a hospital management system built on top of OpenMRS. Integration with Bahmni implies integration with OpenMRS.

Because there is quite a lot of overlap between the kind of data that CommCare uses and the kind that OpenMRS uses, integration between these two systems has the potential to be richer than the integration between CommCare and DHIS2.

OpenMRS integration is under development, and this information may date quickly.

CommCare can import data from OpenMRS using OpenMRS's Reporting API.

CommCare sends data to OpenMRS using its Web Services API. All data sent to OpenMRS relates to what OpenMRS refers to as "patients", "visits", "encounters" and "events". In CommCare these correspond to properties of one or a handful of case types, and values of some form questions. CommCare uses Repeaters to build and send a workflow of requests to OpenMRS, populated using both cases and forms.

Currently under development is the ability to import "live" (or very recent) changes from OpenMRS using its Atom Feed API. This will update CommCare cases, and will appear similar to the system form submissions of a case import.
