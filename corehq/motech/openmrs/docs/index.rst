The MOTECH OpenMRS & Bahmni Module
==================================

See the `MOTECH README`_ for a brief introduction to OpenMRS and Bahmni
in the context of MOTECH.


.. _MOTECH README: https://github.com/dimagi/commcare-hq/blob/master/corehq/motech/README.md#the-openmrs--bahmni-module>


.. contents::
   :local:


OpenmrsRepeater
---------------

.. autoclass:: corehq.motech.openmrs.repeaters.OpenmrsRepeater


OpenMRS Repeater Location
-------------------------

Assigning an OpenMRS repeater to a location allows a project to
integrate with multiple OpenMRS/Bahmni servers.

Imagine a location hierarchy like the following:

* (country) South Africa

  + (province) Gauteng

  + (province) Western Cape

    - (district) City of Cape Town

    - (district) Central Karoo

      * (municipality) Laingsburg

Imagine we had an OpenMRS server to store medical records for the city
of Cape Town, and a second OpenMRS server to store medical records for
the central Karoo.

When a mobile worker whose primary location is set to Laingsburg submits
data, MOTECH will search their location and the locations above it until
it finds an OpenMRS server. That will be the server that their data is
forwarded to.

When patients are imported from OpenMRS, either using its Atom Feed API
or its Reporting API, and new cases are created in CommCare, those new
cases must be assigned an owner.

The owner will be the *first* mobile worker found in the OpenMRS
server's location. If no mobile workers are found, the case's owner will
be set to the location itself. A good way to manage new cases is to have
just one mobile worker, like a supervisor, assigned to the same location
as the OpenMRS server. In the example above, in terms of organization
levels, it would make sense to have a supervisor at the district level
and other mobile workers at the municipality level.

See also: :ref:`patient_finders-label`


OpenmrsConfig
-------------

.. autoclass::  corehq.motech.openmrs.openmrs_config.OpenmrsConfig


An OpenMRS Patient
------------------

The way we map case properties to an OpenMRS patient is based on how
OpenMRS represents a patient. Here is an example of an OpenMRS patient
(with some fields removed)::

    {
      "uuid": "d95bf6c9-d1c6-41dc-aecf-1c06bd71386c",
      "display": "GAN200000 - Test DrugDataOne",

      "identifiers": [
        {
          "uuid": "6c5ab204-a128-48f9-bfb2-3f65fd06785b",
          "identifier": "GAN200000",
          "identifierType": {
            "uuid": "81433852-3f10-11e4-adec-0800271c1b75",
          }
        }
      ],

      "person": {
        "uuid": "d95bf6c9-d1c6-41dc-aecf-1c06bd71386c",
        "display": "Test DrugDataOne",
        "gender": "M",
        "age": 3,
        "birthdate": "2014-01-01T00:00:00.000+0530",
        "birthdateEstimated": false,
        "dead": false,
        "deathDate": null,
        "causeOfDeath": null,
        "deathdateEstimated": false,
        "birthtime": null,

        "attributes": [
          {
            "display": "primaryContact = 1234",
            "uuid": "2869508d-3484-4eb7-8cc0-ecaa33889cd2",
            "value": "1234",
            "attributeType": {
              "uuid": "c1f7fd17-3f10-11e4-adec-0800271c1b75",
              "display": "primaryContact"
            }
          },
          {
            "display": "caste = Tribal",
            "uuid": "06ab9ef7-300e-462f-8c1f-6b65edea2c80",
            "value": "Tribal",
            "attributeType": {
              "uuid": "c1f4239f-3f10-11e4-adec-0800271c1b75",
              "display": "caste"
            }
          },
          {
            "display": "General",
            "uuid": "b28e6bbc-91aa-4ba4-8714-cdde0653eb90",
            "value": {
              "uuid": "c1fc20ab-3f10-11e4-adec-0800271c1b75",
              "display": "General"
            },
            "attributeType": {
              "uuid": "c1f455e7-3f10-11e4-adec-0800271c1b75",
              "display": "class"
            }
          }
        ],

        "preferredName": {
          "display": "Test DrugDataOne",
          "uuid": "760f18ea-9321-4c31-9a43-338089fc5b4b",
          "givenName": "Test",
          "familyName": "DrugDataOne"
        },

        "preferredAddress": {
          "display": "123",
          "uuid": "c41f82e2-6af2-459c-96ff-26b66c8887ae",
          "address1": "123",
          "address2": "gp123",
          "address3": "Raigarh",
          "cityVillage": "RAIGARH",
          "countyDistrict": "Raigarh",
          "stateProvince": "Chattisgarh",
          "country": null,
          "postalCode": null
        },

        "names": [
          {
            "display": "Test DrugDataOne",
            "uuid": "760f18ea-9321-4c31-9a43-338089fc5b4b",
            "givenName": "Test",
            "familyName": "DrugDataOne"
          }
        ],

        "addresses": [
          {
            "display": "123",
            "uuid": "c41f82e2-6af2-459c-96ff-26b66c8887ae",
            "address1": "123",
            "address2": "gp123",
            "address3": "Raigarh",
            "cityVillage": "RAIGARH",
            "countyDistrict": "Raigarh",
            "stateProvince": "Chattisgarh",
            "country": null,
            "postalCode": null
          }
        ]
      }
    }

There are several things here to note:

* A patient has a UUID, identifiers, and a person.

* Other than "uuid", most of the fields that might correspond to case
  properties belong to "person".

* "person" has a set of top-level items like "gender", "age",
  "birthdate", etc.  And then there are also "attributes". The top-level
  items are standard OpenMRS person properties. "attributes" are custom,
  and specific to this OpenMRS instance. Each attribute is identified by
  a UUID.

* There are two kinds of custom person attributes:

  1. Attributes that take any value (of its data type). Examples from
     above are "primaryContact = 1234" and "caste = Tribal".

  2. Attributes whose values are selected from a set. An example from
     above is "class", which is set to "General". OpenMRS calls these
     values "Concepts", and like everything else in OpenMRS each concept
     value has a UUID.

* A person has "names" and a "preferredName", and similarly "addresses"
  and "preferredAddress". Case properties are only mapped to
  preferredName and preferredAddress. We do not keep track of other
  names and addresses.


OpenmrsCaseConfig
-----------------

Now that we know what a patient looks like, the ``OpenmrsCaseConfig``
schema will make more sense. It has the following fields that correspond
to OpenMRS's fields:

* patient_identifiers
* person_properties
* person_attributes
* person_preferred_name
* person_preferred_address

Each of those assigns values to a patient one of three ways, and each
way is configured in an ``OpenmrsCaseConfig`` using a subclass of
``ValueSource``:

1. It can assign a constant. This uses the ``ConstantString`` subclass
   of ``ValueSource``. e.g. ::

       "person_properties": {
         "birthdate": {
           "doc_type": "ConstantString",
           "value": "Oct 7, 3761 BCE"
         }
       }

2. It can assign a case property value. Use ``CaseProperty`` for this.
   e.g. ::

       "person_properties": {
         "birthdate": {
           "doc_type": "CaseProperty",
           "case_property": "dob"
         }
       }

3. It can map a case property value to a concept UUID.
   ``CasePropertyMap`` does this. e.g. ::

       "person_attributes": {
         "c1f455e7-3f10-11e4-adec-0800271c1b75": {
           "doc_type": "CasePropertyMap",
           "case_property": "class",
           "value_map": {
             "sc": "c1fcd1c6-3f10-11e4-adec-0800271c1b75",
             "general": "c1fc20ab-3f10-11e4-adec-0800271c1b75",
             "obc": "c1fb51cc-3f10-11e4-adec-0800271c1b75",
             "other_caste": "c207073d-3f10-11e4-adec-0800271c1b75",
             "st": "c20478b6-3f10-11e4-adec-0800271c1b75"
           }
         }
       }

.. NOTE:: An easy mistake when configuring ``person_attributes``: The
          OpenMRS UUID of a person attribute type is different from the
          UUID of its concept. For the person attribute type UUID,
          navigate to *Administration* > *Person >
          *Manage PersonAttribute Types* and select the person attribute
          type you want. Note the greyed-out UUID. This is the UUID that
          you need. If the person attribute type is a concept, navigate
          to *Administration* > *Concepts* > *View Concept Dictionary*
          and search for the person attribute type by name. Select it
          from the search results. Note the UUID of the concept is
          different. Select each of its answers. Use their UUIDs in
          ``value_map``.

There are two more ``OpenmrsCaseConfig`` fields:

* ``match_on_ids``
* ``patient_finder``

``match_on_ids`` is a list of patient identifiers. They can be all or a
subset of those given in OpenmrsCaseConfig.patient_identifiers. When a
case is updated in CommCare, these are the IDs to be used to select the
corresponding patient from OpenMRS. This is done by
``repeater_helpers.get_patient_by_id()``

This is sufficient for projects that import their patient cases from
OpenMRS, because each CommCare case will have a corresponding OpenMRS
patient, and its ID, or IDs, will have been set by OpenMRS.

.. NOTE:: MOTECH has the ability to create or update the values of
          patient identifiers. If an app offers this ability to users,
          then that identifier should not be included in
          ``match_on_ids``. If the case was originally matched using
          only that identifier and its value changes, MOTECH may be
          unable to match that patient again.

For projects where patient cases can be registered in CommCare, there
needs to be a way of finding a corresponding patient, if one exists.

If ``repeater_helpers.get_patient_by_id()`` does not return a patient,
we need to search OpenMRS for a corresponding patient. For this we use
``PatientFinders``. ``OpenmrsCaseConfig.patient_finder`` will determine
which class of ``PatientFinder`` the OpenMRS repeater must use.


.. _patient_finders-label:

PatientFinder
-------------

.. autoclass:: corehq.motech.openmrs.finders.PatientFinder


Creating Missing Patients
^^^^^^^^^^^^^^^^^^^^^^^^^

If a corresponding OpenMRS patient is not found for a CommCare case,
then ``PatientFinder`` has the option to create a patient in
OpenMRS. This is managed with the optional ``create_missing`` property.
Its value defaults to ``false``. If it is set to ``true``, then it will
create a new patient if none are found.

For example::

    "patient_finder": {
        "doc_type": "WeightedPropertyPatientFinder",
        "property_weights": [
            {"case_property": "given_name", "weight": 0.5},
            {"case_property": "family_name", "weight": 0.6}
        ],
        "searchable_properties": ["family_name"],
        "create_missing": true
    }

If more than one matching patient is found, a new patient will not be
created.

All required properties must be included in the payload. This is sure to
include a name and a date of birth, possibly estimated. It may include
an identifier. You can find this out from the OpenMRS Administration UI,
or by testing the OpenMRS REST API.


WeightedPropertyPatientFinder
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: corehq.motech.openmrs.finders.WeightedPropertyPatientFinder


OpenmrsFormConfig
-----------------

MOTECH sends case updates as changes to patient properties and
attributes. Form submissions can also create Visits, Encounters and
Observations in OpenMRS.

Configure this in the "Form configs" section of the OpenMRS Forwarder
configuration.

An example value of Form configs might look like this::

    [
      {
        "doc_type": "OpenmrsFormConfig",
        "xmlns": "http://openrosa.org/formdesigner/9481169B-0381-4B27-BA37-A46AB7B4692D",
        "openmrs_start_datetime": {
          "form_question": "/metadata/timeStart",
          "doc_type": "FormQuestion",
          "external_data_type": "omrs_date"
        },
        "openmrs_visit_type": "c22a5000-3f10-11e4-adec-0800271c1b75",
        "openmrs_encounter_type": "81852aee-3f10-11e4-adec-0800271c1b75",
        "openmrs_observations": [
          {
            "doc_type": "ObservationMapping",
            "concept": "5090AAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "value": {
              "form_question": "/data/height",
              "doc_type": "FormQuestion"
            }
          },
          {
            "doc_type": "ObservationMapping",
            "concept": "e1e055a2-1d5f-11e0-b929-000c29ad1d07",
            "value": {
              "form_question": "/data/lost_follow_up/visit_type",
              "doc_type": "FormQuestionMap",
              "value_map": {
                "Search": "e1e20e4c-1d5f-11e0-b929-000c29ad1d07",
                "Support": "e1e20f5a-1d5f-11e0-b929-000c29ad1d07"
              }
            },
            "case_property": "last_visit_type"
          }
        ]
      }
    ]

This example uses two form question values, "/data/height" and
"/data/lost_follow_up/visit_type". They are sent as values of OpenMRS
concepts "5090AAAAAAAAAAAAAAAAAAAAAAAAAAAA" and
"e1e055a2-1d5f-11e0-b929-000c29ad1d07" respectively.

The OpenMRS concept that corresponds to the form question "/data/height"
accepts a numeric value.

The concept for "/data/lost_follow_up/visit_type" accepts a discrete set
of values. For this we use ``FormQuestionMap`` to map form question
values, in this example "Search" and "Support", to their corresponding
concept UUIDs in OpenMRS.

The ``case_property`` setting for ``ObservationMapping`` is optional.
If it is set, when Observations are imported from OpenMRS (see
:ref:`atom_feed_integration-label` below) then the given
case property will be updated with the value from OpenMRS. If the
observation mapping is uses ``FormQuestionMap`` or ``CasePropertyMap``
with ``value_map`` (like the "last_visit_type" example above), then the
CommCare case will be updated with the CommCare value that corresponds
to the OpenMRS value's UUID.

Set the UUIDs of ``openmrs_visit_type`` and ``openmrs_encounter_type``
appropriately according to the context of the form in the CommCare app.

``openmrs_start_datetime`` is an optional setting. By default, MOTECH
will set the start of the visit and the encounter to the time when the
form was completed on the mobile worker's device.

To change which timestamp is used, the following values for
``form_question`` are available:

* "/metadata/timeStart": The timestamp, according to the mobile worker's
  device, when the form was started
* "/metadata/timeEnd": The timestamp, according to the mobile worker's
  device, when the form was completed
* "/metadata/received_on": The timestamp when the form was submitted
  to HQ.

The value's default data type is datetime. But some organisations may
need the value to be submitted to OpenMRS as just a date. To do this,
set ``external_data_type`` to ``omrs_date``, as shown in the example.


Provider
--------

Every time a form is completed in OpenMRS, it
`creates a new Encounter <https://wiki.openmrs.org/display/docs/Encounters+and+observations>`_.

Observations about a patient, like their height or their blood pressure,
belong to an Encounter; just as a form submission in CommCare can have
many form question values.

The OpenMRS `Data Model <https://wiki.openmrs.org/display/docs/Data+Model>`_
documentation explains that an Encounter can be associated with health
care providers.

It is useful to label data from CommCare by creating a Provider in
OpenMRS for CommCare.

OpenMRS configuration has a field called "Provider UUID", and the value
entered here is stored in ``OpenmrsConfig.openmrs_provider``.

There are three different kinds of entities involved in setting up a
provider in OpenMRS: A Person instance; a Provider instance; and a User
instance.

Use the following steps to create a provider for CommCare:

From the OpenMRS Administration page, choose "Manage Persons" and click
"Create Person". Name, date of birth, and gender are mandatory fields.
"CommCare Provider" is probably a good name because OpenMRS will split
it into a given name ("CommCare") and a family name ("Provider").
CommCare HQ's first Git commit is dated 2009-03-10, so that seems close
enough to a date of birth. OpenMRS equates gender with sex, and is quite
binary about it. You will have to decided whether CommCare is male or
female. When you are done, click "Create Person". On the next page,
"City/Village" is a required field. You can set "State/Province" to
"Other" and set "City/Village" to "Cambridge". Then click "Save Person".

Go back to the OpenMRS Administration page, choose "Manage Providers"
and click "Add Provider". In the "Person" field, type the name of the
person you just created. You can also give it an Identifier, like
"commcare". Then click Save.

You will need the UUID of the new Provider. Find the Provider by
entering its name, and selecting it.

**Make a note of the greyed UUID**. This is the value you will need for
"Provider UUID" in the configuration for the OpenMRS Repeater.

Next, go back to the OpenMRS Administration page, choose "Manage Users"
and click "Add User". Under "Use a person who already exists" enter the
name of your new person and click "Next". Give your user a username
(like "commcare"), and a password. **Under "Roles" select "Provider"**.
Click "Save User".

Now CommCare's "Provider UUID" will be recognised by OpenMRS as a
provider. Copy the value of the Provider UUID you made a note of earlier
into your OpenMRS configuration in CommCare HQ.


.. _atom_feed_integration-label:

Atom Feed Integration
---------------------

The `OpenMRS Atom Feed Module <https://wiki.openmrs.org/display/docs/Atom+Feed+Module>`_
allows MOTECH to poll feeds of updates to patients and encounters. The
feed adheres to the
`Atom syndication format <https://validator.w3.org/feed/docs/rfc4287.html>`_.

An example URL for the patient feed would be like
"http://www.example.com/openmrs/ws/atomfeed/patient/recent".

Example content::

    <?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>Patient AOP</title>
      <link rel="self" type="application/atom+xml" href="http://www.example.com/openmrs/ws/atomfeed/patient/recent" />
      <link rel="via" type="application/atom+xml" href="http://www.example.com/openmrs/ws/atomfeed/patient/32" />
      <link rel="prev-archive" type="application/atom+xml" href="http://www.example.com/openmrs/ws/atomfeed/patient/31" />
      <author>
        <name>OpenMRS</name>
      </author>
      <id>bec795b1-3d17-451d-b43e-a094019f6984+32</id>
      <generator uri="https://github.com/ICT4H/atomfeed">OpenMRS Feed Publisher</generator>
      <updated>2018-04-26T10:56:10Z</updated>
      <entry>
        <title>Patient</title>
        <category term="patient" />
        <id>tag:atomfeed.ict4h.org:6fdab6f5-2cd2-4207-b8bb-c2884d6179f6</id>
        <updated>2018-01-17T19:44:40Z</updated>
        <published>2018-01-17T19:44:40Z</published>
        <content type="application/vnd.atomfeed+xml"><![CDATA[/openmrs/ws/rest/v1/patient/e8aa08f6-86cd-42f9-8924-1b3ea021aeb4?v=full]]></content>
      </entry>
      <entry>
        <title>Patient</title>
        <category term="patient" />
        <id>tag:atomfeed.ict4h.org:5c6b6913-94a0-4f08-96a2-6b84dbced26e</id>
        <updated>2018-01-17T19:46:14Z</updated>
        <published>2018-01-17T19:46:14Z</published>
        <content type="application/vnd.atomfeed+xml"><![CDATA[/openmrs/ws/rest/v1/patient/e8aa08f6-86cd-42f9-8924-1b3ea021aeb4?v=full]]></content>
      </entry>
      <entry>
        <title>Patient</title>
        <category term="patient" />
        <id>tag:atomfeed.ict4h.org:299c435d-b3b4-4e89-8188-6d972169c13d</id>
        <updated>2018-01-17T19:57:09Z</updated>
        <published>2018-01-17T19:57:09Z</published>
        <content type="application/vnd.atomfeed+xml"><![CDATA[/openmrs/ws/rest/v1/patient/e8aa08f6-86cd-42f9-8924-1b3ea021aeb4?v=full]]></content>
      </entry>
    </feed>

Similarly, an encounter feed URL would be like
"http://www.example.com/openmrs/ws/atomfeed/encounter/recent".

Example content::

    <?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>Patient AOP</title>
      <link rel="self" type="application/atom+xml" href="https://13.232.58.186/openmrs/ws/atomfeed/encounter/recent" />
      <link rel="via" type="application/atom+xml" href="https://13.232.58.186/openmrs/ws/atomfeed/encounter/335" />
      <link rel="prev-archive" type="application/atom+xml" href="https://13.232.58.186/openmrs/ws/atomfeed/encounter/334" />
      <author>
        <name>OpenMRS</name>
      </author>
      <id>bec795b1-3d17-451d-b43e-a094019f6984+335</id>
      <generator uri="https://github.com/ICT4H/atomfeed">OpenMRS Feed Publisher</generator>
      <updated>2018-06-13T08:32:57Z</updated>
      <entry>
        <title>Encounter</title>
        <category term="Encounter" />
        <id>tag:atomfeed.ict4h.org:af713a2e-b961-4cb0-be59-d74e8b054415</id>
        <updated>2018-06-13T05:08:57Z</updated>
        <published>2018-06-13T05:08:57Z</published>
        <content type="application/vnd.atomfeed+xml"><![CDATA[/openmrs/ws/rest/v1/bahmnicore/bahmniencounter/0f54fe40-89af-4412-8dd4-5eaebe8684dc?includeAll=true]]></content>
      </entry>
      <entry>
        <title>Encounter</title>
        <category term="Encounter" />
        <id>tag:atomfeed.ict4h.org:320834be-e9c8-4b09-a99e-691dff18b3e4</id>
        <updated>2018-06-13T05:08:57Z</updated>
        <published>2018-06-13T05:08:57Z</published>
        <content type="application/vnd.atomfeed+xml"><![CDATA[/openmrs/ws/rest/v1/bahmnicore/bahmniencounter/0f54fe40-89af-4412-8dd4-5eaebe8684dc?includeAll=true]]></content>
      </entry>
      <entry>
        <title>Encounter</title>
        <category term="Encounter" />
        <id>tag:atomfeed.ict4h.org:fca253aa-b917-4166-946e-9da9baa901da</id>
        <updated>2018-06-13T05:09:12Z</updated>
        <published>2018-06-13T05:09:12Z</published>
        <content type="application/vnd.atomfeed+xml"><![CDATA[/openmrs/ws/rest/v1/bahmnicore/bahmniencounter/c6d6c248-8cd4-4e96-a110-93668e48e4db?includeAll=true]]></content>
      </entry>
    </feed>

At the time of writing, the Atom feeds do not use ETags or offer HEAD
requests. MOTECH uses a GET request to fetch the document, and checks
the timestamp in the ``<updated>`` tag to tell whether there is new
content.

The feeds are paginated, and the page number is given at the end of the
``href`` attribute of the ``<link rel="via" ...`` tag, which is found at
the start of the feed. A ``<link rel="next-archive" ...`` tag indicates
that there is a next page.

MOTECH stores the last page number polled in the
``OpenmrsRepeater.atom_feed_status["patient"].last_page`` and
``OpenmrsRepeater.atom_feed_status["encounter"]last_page``  properties.
When it polls again, it starts at this page, and iterates
``next-archive`` links until all have been fetched.

If this is the first time MOTECH is polling an Atom feed, it uses the
``/recent`` URL (as given in the example URL above) instead of starting
from the very beginning. This is to allow Atom feed integration to be
enabled for ongoing projects that may have a lot of established data.
Administrators should be informed that enabling Atom feed integration
will not import all OpenMRS patients into CommCare, but it will add
CommCare cases for patients created in OpenMRS from the moment Atom
feed integration is enabled.

Adding cases for OpenMRS patients
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

MOTECH needs three kinds of data in order to add a case for an OpenMRS
patient:

1. The **case type**. This is set using the OpenMRS Repeater's "Case
   Type" field (i.e. OpenmrsRepeater.white_listed_case_types). It must
   have exactly one case type specified.

2. The **case owner**. This is determined using the OpenMRS Repeater's
   "Location" field (i.e. OpenmrsRepeater.location_id). The owner is set
   to the first mobile worker (specifically CommCareUser instance) found
   at that location.

3. The **case properties** to set. MOTECH uses the patient_identifiers,
   person_properties, person_preferred_name, person_preferred_address,
   and person_attributes given in "Case config"
   (OpenmrsRepeater.openmrs_config.case_config) to map the values of an
   OpenMRS patient to case properties. All and only the properties in
   "Case config" are mapped.

The **name of cases** updated from the Atom feed are set to the display
name of the *person* (not the display name of patient because it often
includes punctuation and an identifier).

When a new case is created, its case's owner is determined by the
CommCare location of the OpenMRS repeater. (You can set the location
when you create or edit the OpenMRS repeater in *Project Settings* >
*Data Forwarding*.) The case will be assigned to the first mobile worker
found at the repeater's location. The intention is that this mobile
worker would be a supervisor who can pass the case to the appropriate
person.


.. include:: ../corehq/motech/docs/value_source.rst
