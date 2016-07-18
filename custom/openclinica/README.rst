OpenClinica integration
=======================

Getting Started
---------------

This section is addressed to OpenClinica administrators, but it is
useful for project managers and field managers to know how studies are
managed with CommCare.

1. In OpenClinica, create the study, import the CRFs, and add all the
   users who will be using CommCare.

   When creating the users, please let the Dimagi/CommCare administrator
   know the convention you use to set their usernames, or give them the
   list of usernames. They will need this because the Study Metadata
   that OpenClinica provides includes the first names and last names of
   the users, but not their usernames, and corresponding users will need
   to be created on CommCare with matching usernames.

2. Save the Study Metadata from Study > "Download the study metadata
   **here**". Give this to the Dimagi/CommCare developer or project
   manager.

   They will store the Study Metadata in the project settings in
   CommCare, and add CommCare mobile workers with the same usernames,
   first names and last names.

3. Using CommCare, users will register subjects, and enter study data
   throughout the project.

4. In CommCareHQ, go to Reports > View All > Custom Reports: ODM Export.
   The report will list all the study subjects and their study events.

   If you do not have OpenClinica web services enabled for this
   project, you will need to add all the subjects and schedule their
   events in OpenClinica. This is necessary because OpenClinica does
   not import subjects or events via CDISC ODM.

5. Click the "Export to OpenClinica" button on the report. This will
   create a CDISC ODM document.

   If you have OpenClinica web services enabled for this project, this
   will also create the subjects for you and schedule the events of
   newly-created subjects. (You will need to schedule new events of
   existing subjects in OpenClinica due to limitations in event
   management in OpenClinica web services.)

   You can now import the CDISC ODM document into OpenClinica.


CommCare Integration with OpenClinica
-------------------------------------

CommCare integration with OpenClinica is bidirectional, in that
CommCare can import CDISC ODM-formatted study metadata to create an app,
and can export data using OpenClinica's Web Service, and as a CDISC ODM
document for OpenClinica to import.


Creating a CommCare app from Study Metadata
-------------------------------------------

Apps are created using a management command: ::

    $ python manage.py odm_to_app <domain> <app-slug> <odm-doc>

Generated apps have two case types, "subject" for study subjects, and a
child case type, "event" for the subject's study events. Questions will
have the name assigned to them in the study metadata.

Apps include a module for registering subjects. Subject screening is
out of the scope of the CRF documents that define a study, and so
subject registration introduces an important aspect of using CommCare
for clinical studies: CommCare can be used to manage workflow in a way
that OpenClinica cannot.

App builders can modify the generated app to include workflow processes,
and edit and split up forms in a way that makes them more useable. As
long as forms remain in modules of "event" case type and question names
match their CDSIC ODM IDs, the export will be able to build a CDISC ODM
document with all the necessary data.


OpenClinica Web Service
-----------------------

The OpenClinica web service is different from many other CommCare
integrations with third-party services in that the web service is best
suited to the end of a project, instead of as data arrives.

There are two reasons for this. The first is that the web service
accepts data in CDISC ODM format, which does not allow CommCare forms
to be submitted to OpenClinica as they arrive. It is best suited to
submitting complete data for a study subject. The second is that the
the web service has a limited ability to manage study events. (All data
for a subject is organised by study event.)

As a result, web service integration is associated with data export
instead of form submission. As mentioned before, we use the web service
to create subjects and schedule their study events in OpenClinica in
preparation for importing the CDISC ODM document.

For more information about the OpenClinica web service, see:
https://docs.openclinica.com/3.1/technical-documents/openclinica-web-services-guide


CDISC ODM Export
----------------

CDISC ODM is an XML-based format for exchanging clinical trial data. The
disadvantage of using an export is that the process is manual. But the
benefit is that building the export can be done entirely on the CommCare
side to meet the OpenClinica configuration, without any changes to
OpenClinica required.

For more information, see: http://www.cdisc.org/odm

.. NOTE:: This integration is written for OpenClinica 3.5. From version 3.6,
          the ``UpsertOn`` XML tag is available to perform imports of
          existing data.

