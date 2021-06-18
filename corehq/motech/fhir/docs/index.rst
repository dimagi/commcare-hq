MOTECH on FHIR
==============

CommCare HQ offers two ways of sharing data over FHIR:
#. The FHIR API exposes CommCare cases as FHIR resources.
#. Data forwarding allows CommCare cases to be sent to remote FHIR
   services.

FHIR-related functionality is currently enabled using the "FHIR
integration" feature flag.


The FHIR API
------------

MOTECH offers a FHIR R4 API. It returns responses in JSON.

The FHIR API is not yet targeted at external users. API users must be
superusers.

The API focuses on the Patient resource. The endpoint for a Patient with
case ID 11111111 would be
https://www.commcarehq.org/a/PROJECT-SPACE/fhir/R4/Patient/11111111

(Throughout this documentation, we will use "PROJECT-SPACE" as a
placeholder value for the name of a project space on CommCare HQ.)

To search for the patient's Observations, the API accepts the
"patient_id" search filter. For example,
https://www.commcarehq.org/a/PROJECT-SPACE/fhir/R4/Observation/?patient_id=11111111


Mapping Case Properties
-----------------------

The FHIR Resources to be shared by the FHIR API are configured using the
Data Dictionary. (The Data Dictionary is enabled using the Data
Dictionary feature flag.)

Click on the "Data" menu, choose "View All", and navigate to "Data
Dictionary".

Select the case type to be mapped to the FHIR "Patient" resource type.

Set the value of the "FHIR ResourceType" dropdown to "Patient".

You will see a table of case properties, and a column titled "FHIR
Resource Property Path". This is where to enter the JSONPath to the
resource property to set.

An example will help to illustrate this: Imagine a "person" case type
with a "first_name" case property, and assume we want to map its value
to the patient's given name.

#. Check the structure of a `FHIR Patient`_ on the HL7 website.

#. Note Patient.name has a cardinality of "0..*", so it is a list.

#. Check the `HumanName`_ datatype.

#. Note Patient.name.given also has a cardinality of "0..*".

#. Refer to `JSONPath expression syntax`_ to see how to refer to
   Patient's first given name. ... You will find it is
   ``$.name[0].given[0]``. (To become more familiar with JSONPath,
   playing with the `JSONPath Online Evaluator`_ can be fun and useful.)

#. Fill the value "$.name[0].given[0]" into the "FHIR Resource Property
   Path" field for the "first_name" case property.

#. Using a tool like the `Postman REST Client`_ or the RESTED
   `Firefox add-on`_ / `Chrome extension`_, call the FHIR API endpoint
   for a patient. e.g.
   https://www.commcarehq.org/a/PROJECT-SPACE/fhir/R4/Patient/11111111
   where the case ID is "11111111". (You will need to configure the REST
   client for `API key authentication`_.) You will get a result similar
   to the following::

       {
         "id": "11111111",
         "resourceType": "Patient",
         "name": [
           {
             "given": [
               "Jane"
             ]
           }
         ]
       }

#. Use JSOPNPath to map the rest of the case properties you wish to
   represent in the Patient resource.


.. _FHIR Patient: https://www.hl7.org/fhir/patient.html#resource
.. _HumanName: https://www.hl7.org/fhir/datatypes.html#HumanName
.. _JSONPath expression syntax: https://goessner.net/articles/JsonPath/index.html#e2
.. _JSONPath Online Evaluator: https://jsonpath.com/
.. _Postman REST Client: https://www.postman.com/product/rest-client/
.. _Firefox add-on: https://addons.mozilla.org/en-US/firefox/addon/rested/
.. _Chrome extension: https://chrome.google.com/webstore/detail/rested/eelcnbccaccipfolokglfhhmapdchbfg
.. _API key authentication: https://confluence.dimagi.com/display/commcarepublic/Authentication#Authentication-ApiKeyauthentication


Advanced Mapping
----------------

The Data Dictionary is useful for mapping values from case properties,
but what about FHIR resource properties whose values are not stored in
case properties? Or FHIR resource properties whose data types are not
the same as their corresponding case properties?

This can done using the Admin site, and is accessible to superusers.

#. Open the Admin site, and navigate to "FHIR Resource Types".

#. Select the case type.

#. In an empty "Value Source Config" textarea, configure a value source
   for setting the FHIR resource property value. For more information
   about value source configuration, see the
   :doc:`Value Source <../../docs/value_source.rst>` documentation.


Forwarding Cases as FHIR Resources
----------------------------------

Data forwarding to FHIR APIs uses the same mapping as the FHIR API.

#. Click the Settings cog in the top right, and choose "Project
   Settings".

#. Go to "Connection Settings" and click "Add Connection Settings" to
   add the connection details for the remote FHIR API.

#. Go to "Data Forwarding" and under "Forward Cases to a FHIR API" click
   "Add a service to forward to".

#. Select the Connection Settings from the dropdown. then click "Start
   Forwarding"

To check that Data Forwarding is configured correctly, create or update
a case whose case type has been mapped to a FHIR resource type. Then
verify in "Remote API Logs" that the data has been sent, and check the
remote service that the data has been received.


Using the FHIR API
------------------

Dimagi offers tools to help others use the CommCare HQ FHIR API:


A CommCare HQ Sandbox
^^^^^^^^^^^^^^^^^^^^^

The sandbox is a suite of Docker containers that launches a complete
CommCare HQ instance and the services it needs:

#. Clone the CommCare HQ repository::

       $ git clone https://github.com/dimagi/commcare-hq.git

#. Launch CommCare HQ using the script provided::

       $ scripts/docker runserver

CommCare HQ is now accessible at http://localhost:8000/


A Reference API Client
^^^^^^^^^^^^^^^^^^^^^^

An simple example of a web service that calls the CommCare HQ FHIR API
to retrieve patient data is available as a reference.

You can find it implemented using the `Flask`_ Python web framework, or
`FastAPI`_ for async Python.


.. _Flask: https://github.com/dimagi/commcare-fhir-web-app/
.. _FastAPI: https://github.com/dimagi/commcare-fhir-web-app/tree/fast_api
