OpenClinica integration
=======================

Important Assumptions
---------------------

OpenClinica Study Events can be repeating. In other words, they can have
multiple instances for the same subject. Study Events can contain Item Groups
which are also repeating. When multiple CommCare forms of the same type are
exported to OpenClinica, the export process needs to determine whether to
create new Item Groups for the new forms, or whether to create new Study
Events instead. The choice is based on the date!

.. IMPORTANT:: If the date that the form was started is different, then it is
               considered a new Study Event.

If the date has not changed, it is considered the same Study Event, and a new
Item Group is created instead.


Required Case Properties
------------------------

* Each subject must have a "subject key" property. This can potentially be
  generated from the subject's name, but must be unique within the OpenClinica
  instance.

* Each subject must have one "study subject ID" for each study they are
  enrolled in. This needs to be unique within the study.

The following constants are retrieved from study metadata, which is available
from OpenClinica. To retrieve:

1. Log into OpenClinica
2. Navigate to the study by clicking the study name at the top left of the
   page
3. Download the study metadata be clicking on "Download the study metadata
   **here**."
4. For this first OpenClinica integration project, study metadata is simply
   saved in `custom/openclinica/study_metadata.xml`, but future projects will
   need to be more generic, and save study metadata for each project in a
   database.

The project partner will be able to furnish you with this document from their
production OpenClinica instance.


Integration Methods
-------------------

Integration has two possible routes:

* OpenClinica Web Service (SOAP)
* ODM-formatted export


OpenClinica Web Service
-----------------------

This allows forms to be forwarded on submission. The benefit is that
data is immediately available in OpenClinica. The disadvantage is that
OpenClinica must be configured in such a way that an OpenClinica "Event"
maps one-to-one to a CommCare form. This makes the project vulnerable to
the precise configuration of OpenClinica, and the timing of changing a
previous, working configuration to match the CommCare app.

For more information, see:
https://docs.openclinica.com/3.1/technical-documents/openclinica-web-services-guide


ODM Export
----------

ODM is an XML-based format for exchanging clinical trial data. The
disadvantage of using an export is that the process is manual. But the
benefit is that building the export can be done entirely on the CommCare
side to meet the OpenClinica configuration, without any changes to
OpenClinica required.

For more information, see: http://www.cdisc.org/odm

.. NOTE:: This integration is written for OpenClinica 3.5, because that
          is the version that KEMRI currently uses. From version 3.6,
          the ``UpsertOn`` XML tag is available to perform imports of
          existing data.


Chosen Approach
---------------

For this project we have chosen to implement the ODM export. For a
future project we may look at changing the OpenClinica configuration to
match the CommCare app, and implement web service integration once that
has been done.
