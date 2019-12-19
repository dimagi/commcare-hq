Getting Values From CommCare
----------------------------

MOTECH configurations use "value sources" to refer to values in
CommCare, like values of case properties or form questions.


Data Types
^^^^^^^^^^

Integrating structured data with remote systems can involve converting
data from one format or data type to another.

For standard OpenMRS properties (person properties, name properties and
address properties) MOTECH will set data types correctly, and
integrators do not need to worry about them.

But administrators may want a value that is a date in CommCare to a
datetime in a remote system, or vice-versa. To convert from one to the
other, set data types for value sources.

The default is for both the CommCare data type and the external data
type not to be set. e.g. ::

    {
      "expectedDeliveryDate": {
        "doc_type": "CaseProperty",
        "case_property": "edd",
        "commcare_data_type": null,
        "external_data_type": null
      }
    }

To set the CommCare data type to a date and the OpenMRS data type to a
datetime for example, use the following::

    {
      "expectedDeliveryDate": {
        "doc_type": "CaseProperty",
        "case_property": "edd",
        "commcare_data_type": "cc_date",
        "external_data_type": "omrs_datetime"
      }
    }

For the complete list of CommCare data types, see `MOTECH constants`_.
For the complete list of DHIS2 data types, see `DHIS2 constants`_. For
the complete list of OpenMRS data types, see `OpenMRS constants`_.


.. _MOTECH constants: https://github.com/dimagi/commcare-hq/blob/master/corehq/motech/const.py
.. _DHIS2 constants: https://github.com/dimagi/commcare-hq/blob/master/corehq/motech/dhis2/const.py
.. _OpenMRS constants: https://github.com/dimagi/commcare-hq/blob/master/corehq/motech/openmrs/const.py


Import-Only and Export-Only Values
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In configurations like OpenMRS Atom feed integration that involve both
sending data to OpenMRS and importing data from OpenMRS, sometimes some
values should only be imported, or only exported.

Use the ``direction`` property to determine whether a value should only
be exported, only imported, or (the default behaviour) both.

For example, to import a patient value named "hivStatus" as a case
property named "hiv_status" but not export it, use
``"direction": "in"``::

    {
      "hivStatus": {
        "doc_type": "CaseProperty",
        "case_property": "hiv_status",
        "direction": "in"
      }
    }

To export a form question, for example, but not import it, use
``"direction": "out"``::

    {
      "hivStatus": {
        "doc_type": "FormQuestion",
        "case_property": "hiv_status",
        "direction": "out"
      }
    }

Omit ``direction``, or set it to ``null``, for values that should be
both imported and exported.


The value_source Module
-----------------------

.. automodule:: corehq.motech.value_source
   :members:


Getting Values From JSON Responses
----------------------------------

OpenMRS observations and Bahmni diagnoses can be imported as extension
cases of CommCare case. This is useful for integrating patient
referrals, or managing diagnoses.

Values from the observation or diagnosis can be imported to properties
of the extension case.

MOTECH needs to traverse the JSON response from the remote system in
order to get the right value. Value sources can use `JSONPath`_ to do
this.

Here is a simplified example of a Bahmni diagnosis to get a feel for
JSONPath::

    {
      "certainty": "CONFIRMED",
      "codedAnswer": {
        "conceptClass": "Diagnosis",
        "mappings": [
          {
            "code": "T68",
            "name": "Hypothermia",
            "source": "ICD 10 - WHO"
          }
        ],
        "shortName": "Hypothermia",
        "uuid": "f7e8da66-f9a7-4463-a8ca-99d8aeec17a0"
      },
      "creatorName": "Eric Idle",
      "diagnosisDateTime": "2019-10-18T16:04:04.000+0530",
      "order": "PRIMARY"
    }

The JSONPath for "certainty" is simply "certainty".

The JSONPath for "shortName" is "codedAnswer.shortName".

The JSONPath for "code" is "codedAnswer.mappings[0].code".


JsonPathCaseProperty
^^^^^^^^^^^^^^^^^^^^

.. autoclass:: corehq.motech.value_source.JsonPathCaseProperty


JsonPathCasePropertyMap
^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: corehq.motech.value_source.JsonPathCasePropertyMap


How to inspect an observation or a diagnosis
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To see what the JSON representation of an OpenMRS observation or Bahmni
diagnosis is, you can use the official `Bahmni demo server`_.

1. Log in as "superman" with the password "Admin123".

2. Click "Registration" and register a patient.

3. Click the "home" button to return to the dashboard, and click
   "Clinical".

4. Select your new patient, and create an observation or a diagnosis for
   them.

5. In a new browser tab or window, open the `Encounter Atom feed`_.

6. Right-click and choose "View Page Source".

7. Find the URL of the latest encounter in the "CDATA" value in the
   "content" tag. It will look similar to this:
   "/openmrs/ws/rest/v1/bahmnicore/bahmniencounter/<UUID>?includeAll=true"

8. Construct the full URL, e.g.
   "https://demo.mybahmni.org/openmrs/ws/rest/v1/bahmnicore/bahmniencounter/<UUID>?includeAll=true"
   where "<UUID>" is the UUID of the encounter.

9. The OpenMRS REST Web Services API `does not make it easy`_ to get a
   JSON-formatted response using a browser. You can use a REST API
   Client like `Postman`_, or you can use a command line tool like
   `curl`_ or `Wget`_.

   Fetch the content with the "Accept" header set to "application/json".

   Using curl ::

       $ curl -u superman:Admin123 -H "Accept: application/json" \
           "https://demo.mybahmni.org/...?includeAll=true" > encounter.json

   Using wget ::

       $ wget --user=superman --password=Admin123 \
           --header="Accept: application/json" \
           -O encounter.json \
           "https://demo.mybahmni.org/...?includeAll=true"

   Open ``encounter.json`` in a text editor that can automatically
   format JSON for you. (`Atom`_ with the `pretty-json`_ package
   installed is not a bad choice.)


.. _JSONPath: https://goessner.net/articles/JsonPath/
.. _Bahmni demo server: https://demo.mybahmni.org/bahmni/home/
.. _Encounter Atom feed: https://demo.mybahmni.org/openmrs/ws/atomfeed/encounter/recent
.. _does not make it easy: https://wiki.openmrs.org/display/docs/REST+Web+Services+API+For+Clients#RESTWebServicesAPIForClients-ResponseFormat
.. _Postman: https://www.getpostman.com/
.. _curl: https://curl.haxx.se/
.. _Wget: https://www.gnu.org/software/wget/
.. _Atom: https://atom.io/
.. _pretty-json: https://atom.io/packages/pretty-json
