How Data Mapping Works
======================

DHIS2-, OpenMRS- and FHIR Integration all use the ValueSource class to
map CommCare data to API resources.

A ValueSource is given in JSON format. e.g.

.. code-block:: javascript

   {
     "case_property": "active",
     "jsonpath": "$.active"
   }

This ValueSource maps the value from the case property named "active" to
the "active" property of an API resource.


Different Sources of Values
---------------------------

The ValueSource class supports several different sources of values:

* ``case_property``: As seen above, a ValueSource can be used for
  fetching a value from a case property, or setting a value on a case
  property.

* ``form_question``: Fetches a value from a form question. e.g.
  "/data/foo/bar" will get the value of a form question named "bar" in
  the group "foo". Form metadata is also available, e.g.
  "/metadata/received_on" is the server time when the form submission
  was received. You can find more details in the source code at
  corehq.motech.value_source:FormQuestion

* ``case_owner_ancestor_location_field``: Specifies a location metadata
  field name. The ValueSource will start at the location of the case
  owner, traverse up their location hierarchy, and return the first
  value it finds for a location with that field. This can be used for
  mapping CommCare locations to locations or organization units in a
  remote system.

* ``form_user_ancestor_location_field``: Specifies a location metadata
  field name. Similar to `case_owner_ancestor_location_field` but for
  forms instead of cases.  The ValueSource will start at the location of
  the user who submitted the form, traverse up their location hierarchy,
  and return the first value it finds for a location with that field.
  This can be used for mapping CommCare locations to locations or
  organization units in a remote system.

* ``subcase_value_source``: Defines a ValueSource to be evaluated on the
  subcases of a case. e.g.

  .. code-block:: javascript

     {
       "subcase_value_source": {"case_property": "name"}
       "case_type": "child",
       "is_closed": false,
       "jsonpath": "$.childrensNames"
     }

* ``supercase_value_source``: Defines a ValueSource to be evaluated on
  the parent/host case of a case. e.g.

  .. code-block:: javascript

     {
       "supercase_value_source": {"case_property": "name"}
       "referenced_type": "mother",
       "jsonpath": "$.mothersName"
     }

* ``value``: A constant value. This can be used for exporting a
  constant, or it can be combined with `case_property` for importing a
  constant value to a case property. See
  corehq.motech.value_source:ConstantValue for more details.




Data Types
----------

Integrating structured data with remote systems can involve converting
data from one format or data type to another. Use data type declarations
to cast the data type of a value.

For standard OpenMRS properties (person properties, name properties and
address properties) MOTECH will set data types correctly, and
integrators do not need to worry about them.

But administrators may want a value that is a date in CommCare to a
datetime in a remote system, or vice-versa. To convert from one to the
other, set data types for value sources.

The default is for both the CommCare data type and the external data
type not to be set. e.g.

.. code-block:: javascript

   {
     "expectedDeliveryDate": {
       "case_property": "edd",
       "commcare_data_type": null,
       "external_data_type": null
     }
   }

To set the CommCare data type to a date and the OpenMRS data type to a
datetime for example, use the following:

.. code-block:: javascript

   {
     "expectedDeliveryDate": {
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
----------------------------------

In configurations like OpenMRS Atom feed integration that involve both
sending data to OpenMRS and importing data from OpenMRS, sometimes some
values should only be imported, or only exported.

Use the ``direction`` property to determine whether a value should only
be exported, only imported, or (the default behaviour) both.

For example, to import a patient value named "hivStatus" as a case
property named "hiv_status" but not export it, use
``"direction": "in"``:

.. code-block:: javascript

   {
     "hivStatus": {
       "case_property": "hiv_status",
       "direction": "in"
     }
   }

To export a form question, for example, but not import it, use
``"direction": "out"``:

.. code-block:: javascript

   {
     "hivStatus": {
       "case_property": "hiv_status",
       "direction": "out"
     }
   }

Omit ``direction``, or set it to ``null``, for values that should be
both imported and exported.


Getting Values From JSON Documents
----------------------------------

JSONPath has emerged as a standard for navigating JSON documents. It
is supported by `PostgreSQL`_, `SQL Server`_, and others. ValueSource
uses it to read values from JSON API resources.

And, in the case of FHIR Integration, it also uses it to build FHIR
resources.

See the `article by Stefan Goessner`_, who created JSONPath, for more
details.

OpenMRS observations and Bahmni diagnoses can be imported as extension
cases of CommCare case. This is useful for integrating patient
referrals, or managing diagnoses.

Values from the observation or diagnosis can be imported to properties
of the extension case. MOTECH needs to traverse the JSON response from
the remote system in order to get the right value. Value sources can use
JSONPath to do this.

Here is a simplified example of a Bahmni diagnosis to get a feel for
JSONPath:

.. code-block:: javascript

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

For more details, see :ref:`openmrs-how_to_inspect` in the documentation
for the MOTECH OpenMRS & Bahmni Module.


.. _PostgreSQL: https://www.postgresql.org/docs/12/functions-json.html#FUNCTIONS-SQLJSON-PATH
.. _SQL Server: https://docs.microsoft.com/en-us/sql/relational-databases/json/json-path-expressions-sql-server
.. _article by Stefan Goessner: https://goessner.net/articles/JsonPath/


The value_source Module
-----------------------

.. automodule:: corehq.motech.value_source
   :members:
