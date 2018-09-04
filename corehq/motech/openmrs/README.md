MOTECH's OpenMRS Module
=======================

See the [MOTECH README](../README.md#openMRS----bahmni--module) for a
brief introduction to OpenMRS and Bahmni in the context of MOTECH.


The OpenmrsRepeater
-------------------

The OpenmrsRepeater is responsible for updating OpenMRS patients with
changes made to cases in CommCare. It is also responsible for creating
OpenMRS "visits", "encounters" and "observations" when a corresponding
visit form is submitted in CommCare.

It is different from other repeaters in two important details:

1. It updates the OpenMRS equivalent of cases like a CaseRepeater, but
it reads forms like a FormRepeater. So it subclasses CaseRepeater, but
its payload format is form_json.

2. It makes many API calls for each payload.


OpenmrsConfig
-------------

Configuration for an OpenmrsRepeater is stored in an OpenmrsConfig
document. Patient data, which is mapped from a CommCare case, is stored
in OpenmrsConfig.case_config, and adheres to the OpenmrsCaseConfig
document schema. Event, encounter and observation data, which is mapped
from CommCare forms, is stored in OpenmrsConfig.form_configs.

Currently we support one case type and multiple forms. That may change
in the future if we need to map multiple CommCare case types to OpenMRS
patients.


An OpenMRS Patient
------------------

The way we map case properties to an OpenMRS patient is based on how
OpenMRS represents a patient. Here is an example of an OpenMRS patient
(with some fields removed):

```javascript
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
```

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

Now that we know what a patient looks like, the OpenmrsCaseConfig schema
will make more sense. It has the following fields that correspond to
OpenMRS's fields:

* patient_identifiers
* person_properties
* person_attributes
* person_preferred_name
* person_preferred_address

Each of those assigns values to a patient one of three ways, and each
way is configured in an OpenmrsCaseConfig using a subclass of
ValueSource:

1. It can assign a constant. This uses the ConstantString subclass of
   ValueSource. e.g.
   ```javascript
       "person_properties": {
         "birthdate": {
           "doc_type": "ConstantString",
           "value": "Oct 7, 3761 BCE"
         }
       }
   ```

2. It can assign a case property value. Use CaseProperty for this. e.g.
   ```javascript
       "person_properties": {
         "birthdate": {
           "doc_type": "CaseProperty",
           "case_property": "dob"
         }
       }
    ```

3. It can map a case property value to a Concept UUID.
   CasePropertyMap does this. e.g.
   ```javascript
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
    ```

**GOTCHA**: An easy mistake when configuring "person_attributes": The
OpenMRS UUID of a Person Attribute Type is different from the UUID of
its Concept. For the Person Attribute Type UUID, navigate to
Administration > Person > Manage Person Attribute Types and select the
Person Attribute Type you want. Note the greyed-out UUID. This is the
UUID that you need. If the Person Attribute Type is a Concept, navigate
to Administration > Concepts > View Concept Dictionary and search for
the Person Attribute Type by name. Select it from the search results.
Note the UUID of the concept is different. Select each of its Answers.
Use their UUIDs in the "value_map".

There are two more OpenmrsCaseConfig fields:

* match_on_ids
* patient_finder

`match_on_ids` is a list of patient identifiers. They can be all or a
subset of those given in OpenmrsCaseConfig.patient_identifiers. When a
case is updated in CommCare, these are the IDs to be used to select the
corresponding patient from OpenMRS. This is done by
[`repeater_helpers`](repeater_helpers.py)`.get_patient_by_id()`

This is sufficient for projects that import their patient cases from
OpenMRS, because each CommCare case will have a corresponding OpenMRS
patient, and its ID, or IDs, will have been set by OpenMRS.

**NOTE**: MOTECH has the ability to create or update the values of
patient identifiers. If an app offers this ability to users, then that
identifier should not be included in `match_on_ids`. If the case was
originally matched using only that identifier and its value changes,
MOTECH may be unable to match that patient again.

For projects where patient cases can be registered in CommCare, there
needs to be a way of finding a corresponding patient, if one exists.

If `repeater_helpers.get_patient_by_id()` does not return a patient, we
need to search OpenMRS for a corresponding patient. For this we use
PatientFinders. OpenmrsCaseConfig.patient_finder will determine which
class of PatientFinder the OpenmrsRepeater must use.


PatientFinders
--------------

The [PatientFinder](finders.py) base class was developed as a way to
handle situations where patient cases are created in CommCare instead of
being imported from OpenMRS.

When patients are imported from OpenMRS, they will come with at least
one identifier that MOTECH can use to match the case in CommCare with
the corresponding patient in OpenMRS. But if the case is registered in
CommCare then we may not have an ID, or the ID could be wrong. We need
to search for a corresponding OpenMRS patient.

Different projects may focus on different kinds of case properties, so
it was felt that a base class would allow some flexibility, without too
much "YAGNI".

The `PatientFinder.wrap()` method allows you to wrap documents of
subclasses.

The `PatientFinder.find_patients()` method must be implemented by
subclasses. It returns a list of zero, one, or many patients. If it
returns one patient, the OpenmrsRepeater.find_patient() will accept that
patient as a true match.

**NOTE**: The consequences of a false positive (a Type II error) are
severe: A real patient will have their valid values overwritten by those
of someone else. So PatientFinders should be written and configured to
skew towards false negatives (Type I errors). In other words, it is much
better not to choose a patient than to choose the wrong patient.


Provider
--------

In OpenMRS, observations about a patient, like their height or their
blood pressure, can be associated with a data provider. A "provider" is
usually an OpenMRS user who can enter data.

It is useful to label data from CommCare. OpenMRS Configuration has a
field called "Provider's Person UUID", and the value entered here is
stored in OpenmrsConfig.openmrs_provider.

There are three different kinds of entities involved in setting up a
provider in OpenMRS: A Person instance; a Provider instance; and a User
instance.

**NOTE**: The value that OpenMRS expects in the "Provider's Person UUID"
field is a **Person UUID**, not a **Provider UUID**. The distinction is
not obvious in the OpenMRS interface.

Use the following steps to create a provider for CommCare:

From the OpenMRS Administration page, choose "Manage Persons" and click
"Create Person". Name, date of birth, and gender are mandatory fields.
"CommCare Provider" is probably a good name because OpenMRS will split
it into a given name ("CommCare") and a family name ("Provider").
CommCare HQ's first Git commit is dated 2009-03-10, so that seems close
enough to a date of birth. OpenMRS equates gender with sex, and is quite
binary about it. You will have to decided whether CommCare is male or
female. When you are done, click "Create Person".

Make a note of the greyed UUID at the bottom of the next page. This is
the value you will need for "Provider's Person UUID" in the
configuration for the OpenMRS Repeater.

Go back to the OpenMRS Administration page, choose "Manage Providers"
and click "Add Provider". In the "Person" field, type the name of the
person you just created. Then click Save.

Next, go back to the OpenMRS Administration page, choose "Manage Users"
and click "Add User". Under "Use a person who already exists" enter the
name of your new person and click "Next". Give your user a username
(like "commcare"), and a password. **Under "Roles" select "Provider"**.
Click "Save"

Now CommCare's "Provider UUID" will be recognised by OpenMRS as a
provider. Copy the value of the person UUID you made a note of earlier
into your OpenMRS configuration in CommCare HQ.


Atom Feed Integration
---------------------

The [OpenMRS Atom Feed Module](https://wiki.openmrs.org/display/docs/Atom+Feed+Module)
allows MOTECH to poll a feed of updates to patients, concepts,
encounters and observations. The feed adheres to the
[Atom syndication format](https://validator.w3.org/feed/docs/rfc4287.html).

An example URL for the patient feed would be like
http://www.example.com/openmrs/ws/atomfeed/patient/recent

Example content:

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

At the time of writing, the Atom feed does not use ETags or offer HEAD
requests. MOTECH uses a GET request to fetch the document, and checks
the timestamp in the `<updated>` tag to tell whether there is new
content.

The feed is paginated, and the page number is given at the end of the
`href` attribute of the `<link rel="via" ...` tag, which is found at the
start of the feed. A `<link rel="next-archive" ...` tag indicates that
there is a next page.

MOTECH stores the last page number polled in the
`OpenmrsRepeater.atom_feed_last_page` property. When it polls again, it
starts at this page, and iterates "next-archive" links until all have
been fetched.

If this is the first time MOTECH is polling an Atom feed, it uses the
`/recent` URL (as given in the example URL above) instead of starting
from the very beginning. This is to allow Atom feed integration to be
enabled for ongoing projects that may have a lot of established data.
Administrators should be informed that enabling Atom feed integration
will not import all OpenMRS patients into CommCare, but it will add
CommCare cases for patients created in OpenMRS from the moment Atom
feed integration is enabled.

### Adding cases for OpenMRS patients

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
