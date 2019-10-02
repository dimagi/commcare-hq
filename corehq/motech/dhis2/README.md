MOTECH's DHIS2 Module
=====================

See the [MOTECH README](../README.md#dhis2-module) for a brief
introduction to DHIS2 in the context of MOTECH.

MOTECH supports three ways of integrating with DHIS2:
* Forwarding aggregated data as DHIS2 DataSets
* Forwarding form question values as DHIS2 Anonymous Events
* Forwarding cases as DHIS2 Tracked Entity Instances, along with form
  question values as events of those instances.

Use the "Enable DHIS2 integration" feature flag to enable these.


Logging
-------

All requests sent to DHIS2, and the responses from DHIS2, are logged
and available under **Project Settings** > **MOTECH Logs**.


DataSets
--------

DataSets are sets of aggregated data. In the context of MOTECH, this is
data that has been collected using CommCare over a month or a quarter,
and then aggregated with a user-configurable report (UCR).


### UCRs for DataSets

Each column of the UCR maps to a DHIS2 DataElement + CategoryOptionCombo
pair. You will need to refer to DHIS2 to know what data you want, and
how it needs to be broken down, to determine the DataElements and the
CategoryOptionCombos you need.

If different rows have data from different periods, you can add a column for
the DHIS2 DataSet period, given in the format "yyyyMM" if the period is
monthly, e.g. "200403", or "yyyyQn" if the period is quarterly, where
"Q" is a literal "Q" and "n" is a number from 1 to 4, e.g. "2004Q1".

If different rows belong to different organisation units, you can
include a column for the row's orgUnitID.


### DataSet Map Configuration

To map UCR columns for a DHIS2 DataSet, go to **Project Settings** >
**DHIS2 DataSet Maps**.

The first part is where you set properties that apply to the whole
DataSet. If all the data in the UCR is for the same organisation unit,
specify it here, otherwise configure the name of the column where the
OrgUnitID can be found.

There are three ways to determine the period for the DataSet:

1. If the UCR is always for the same period, set it in "Period
   (YYYYMM)".
2. If different rows have data from different periods, set the column
   that contains the period in "Period column".
3. If MOTECH should pull the report for the previous period (month or
   quarter), and if the report has a date filter, choose "Report filter
   sets Period"

Then proceed to set the UCR Column, DataElementID,
CategoryOptionComboID, and optionally a comment, for each DataValue to
be sent to DHIS2.

You can map multiple DataSets here. Each will be sent in a separate API
call to DHIS2.

Save your configuration by clicking the "Update DHIS2 DataSet maps"
button.


### Testing

To test your configuration, click "Send data now".

Check **Project Settings** > **MOTECH Logs** to inspect the requests
sent to DHIS2, and the responses from DHIS2.


Anonymous Events
----------------

CommCare form data can be sent to DHIS2 as Anonymous Events. Form data
will be sent as forms are submitted.

This is configured under **Project Settings** > **Data Forwarding** >
**Forward Forms to DHIS2 as Anonymous Events**.

If it is not already defined, add a forwarding location. (This is
sometimes refered to as a "forwarder", and in the source code it is a
[`Dhis2Repeater`](./repeaters.py).) Enter the details of the DHIS2
server.

**NOTE**: The value for "**URL to forward to**" should not include the
"api" part of the URL. For example, if you are testing using the DHIS2
demo server, the URL might be something like,
"https://play.dhis2.org/2.31.5/".

When you are done, click "Start Forwarding".

To configure the integration, click "Configure".

**NOTE**: The Anonymous Events configuration uses a JSON interface, like
user-configurable reports. It was found that integrators preferred this
to an HTML interface because it allowed them to reuse their own
templates, and copy-and-paste configurations from their text editor of
choice.

"Form configs" are a list of [`Dhis2FormConfig`](./dhis2_config.py)
definitions. The following is an example:

    [
      {
        "doc_type": "Dhis2FormConfig",
        "xmlns": "http://openrosa.org/formdesigner/C3156B64-C380-4A38-B00E-C8E4D81EDCF9",
        "program_id": "WomWTaHk5mx",
        "event_date": {
          "doc_type": "FormQuestion",
          "form_question": "/data/event_date"
        },
        "event_status": "COMPLETED",
        "org_unit_id": {
          "doc_type": "FormUserAncestorLocationField",
          "location_field": "dhis_id",
        },
        "datavalue_maps": [
          {
            "doc_type": "FormDataValueMap",
            "data_element_id": "M8yQ1rWomWT",
            "value": {
              "doc_type": "FormQuestionMap",
              "form_question": "/data/home_delivery",
              "value_map": {
                "yes": 1,
                "no": 0
              }
            }
          },
          {
            "doc_type": "FormDataValueMap",
            "data_element_id": "Hk5mxrWomWT",
            "value": {
              "doc_type": "FormQuestion",
              "form_question": "/data/birth_outcome"
            }
          }
        ]
      }
    ]

There is only one Dhis2FormConfig definition in this example. The form
is identified by its XMLNS,
"http://openrosa.org/formdesigner/C3156B64-C380-4A38-B00E-C8E4D81EDCF9".

The event date is determined from a form question, "/data/event_date".
(It is possible to use the time when the form was opened on the device
("/data/meta/timeStart") or when it was completed ("/data/meta/timeEnd")
but if the device's clock is inaccurate, or has been changed, then the
date could be wrong. Depending on the nature of the data, the user may
be reporting an event that has already occurred. Sometimes it is best to
prompt the user for the event date.)

"datavalue_maps" map form data to DHIS2 DataValues. They are
[`FormDataValueMap`](./dhis2_config.py) definitions. In each one a DHIS2
DataElement ID is given, and a CommCare ValueSource. The value source
can be a ConstantString if the value of the data element is always the
same; or a FormQuestion; or a FormQuestionMap if CommCare values map to
DHIS2 values.

There are several ways to set the DHIS2 organisation unit ID:

* It could be set to a constant for all submissions of this form. This
  is the case in the example given above. The ValueSource is set to a
  "ConstantString", and a constant value is given. This is unlikely
  though, because usually forms will be submitted for many locations or
  organisation units.
* It could be that the organisation unit is selected by the user from a
  lookup table. In this scenario, the org_unit_id would be saved to a
  hidden value in the form, and the ValueSource would be a FormQuestion
  where "form_question" is set to the hidden value.
* It could be that locations in the project space have equivalent
  organisation units in DHIS2. If "org_unit_id" is not specified in the
  Dhis2FormConfig definition, then the MOTECH uses the CommCare location
  of the mobile worker who submitted the form, and checks its location
  fields for a location property named "dhis_id".


### Matching CommCare locations with DHIS2 oganisation units

1. Navigate to **Users** > **Organization Structure** and click the "Edit
   Location Fields" button.
2. Add a field with "Location Property" set to "dhis_id". (It is
   important that you use this spelling.) Set "Label" to something like
   "DHIS2 OrgUnit ID".
3. Click "Save Fields".

You can now either add the DHIS2 OrgUnit ID to each location one by one,
or download the Organization Structure, and add them in bulk using, for
example, a spreadsheet with a lookup to match CommCare locations with
DHIS2 OrgUnits.


### Testing

Once the integration is configured, you can test it by submitting a
form, and checking **Project Settings** > **Data Forwarding Records**.
Form submissions will appear here with "Record Status" "Pending". Queued
payloads are forwarded every four minutes. To send it immediately, click
"Resend Payload".

Check **Project Settings** > **MOTECH Logs** to inspect the requests
sent to DHIS2, and the responses from DHIS2.


Tracked Entities
----------------

DHIS2 *tracked entity instances* are analogous to CommCare *cases*.

*Tracked entity types* are like *case types*, and are used for tracking
people, buildings, equipment, lab samples, etc.

*Tracked entity attributes* are the same as *case properties*. In
CommCare you don't have to define them, but you can using the Data
Dictionary. In DHIS2 you do have to define them.

Events are categorised into programs. There are two kinds of programs:
* Tracker programs, where events are associated with a tracked entity
  instance. MOTECH supports integrating CommmCare data with tracker
  programs by forwarding cases to DHIS2 as tracked entity instances,
  along with the data from the forms that register or update those
  cases.
* Event programs, where events are not associated with a tracked entity
  instance. MOTECH supports integrating CommmCare data with event
  programs by forwarding forms to DHIS2 as anonymous events.

Tracked entity API requests include the same kind of data as anonymous
event API requests, and also include case property data.


### Getting Started

A good way to see how DHIS2 Tracked Entity integration works is to
create a simple app and send data to DHIS2's demo server. The demo
server has useful sample data, and it gets reset every 24 hours so you
have a fresh environment to work with.


#### Explore DHIS2

We will use the DHIS2 MNCH program as an example. Open 
https://play.dhis2.org/ in your browser and choose "Stable demo". You
will be taken to the login page of the version of DHIS2 that is
currently tagged the stable version, e.g.
"https://play.dhis2.org/2.31.5/...". Log in with the username "admin"
and the password "district". The dashboard page will appear.

Click the grid icon / Rubik's cube in the top right, and choose
"Maintenance". This is where we can find details of the program that we
want to build an app for. Select the "Program" tab at the top. In the
"Program" box, click the "List" icon.

Choose the "MNCH / PNC (Adult Woman)" tracker program from the list.
Among the program details you can see that the tracked entity type is
given as "Person".

Take a look at the URL in your browser. It ends with
"/program/uy2gU8kT1jF". "uy2gU8kT1jF" is the ID of the program. The
browser URL is a simple way of finding the ID of just about anything in
DHIS2. We will need IDs to configure the integration.

Click "Enrollment details" at the top. Note that the "incident date" is
given as "LMP Date". Our app will need to collect this date in a form.

Click "Attributes" at the top. You will find the
"program tracked entity attributes". These are the case properties that
we will want to include in our app. The searchable tracked entity
attributes will be useful for finding existing tracked entity instances,
and those should be in our app's registration form.

Click "Program stages" at the top. Program stages could correspond to
different forms in our app. To get started we will just create a form
for "ANC 1st visit". Select it, scroll down and click "Assign data
elements". You will find a list of possible form questions. Note that
for ANC 1, none of them are marked as compulsory. If any were, those
ones would have to be included in our form. For simplicity, we will just
include "MCH Visit Comment".


#### Create a basic CommCare app

We will create a small CommCare app with just one case list menu, a form
to register a woman, and a follow-up form for an ANC 1 visit.

If your project space has the Data Dictionary available, it would be a
good place to start because we know the case properties already.

Create a new app, add a case list menu. In "Registration Form", add
the following questions:
* "Given name" (Question ID: `given_name`)
* "Family name" (Question ID: `family_name`)
* "Date of birth" (Question ID: `date_of_birth`)

Check the question IDs are spelled as above. We will be using them when
we configure the integration, and typos can result in missing values.

("Unique ID" is another attribute of the Person tracked entity type, but
it is not mandatory so we can skip it.)

Make a hidden a question for the case's name with question ID `name`
that joins `given_name` and `family_name`. e.g.
`join(' ', #form/given_name, upper-case(#form/family_name))`

In the settings for "Registration Form", save all questions as case
properties with the same name. We will be exporting them to DHIS2 as
tracked entity attributes.

In "Followup Form", add questions:
* "LMP Date" (Question ID: `lmp_date`)
* "Visit Comment" (Question ID: `visit_comment`)
* and the rest of the case properties, so you can modify them if you
  want.

In the settings for "Followup Form", save the questions that are also in
"Registration Form" to case properties, but you don't need to save
`lmp_date` or `visit_comment`. We will be exporting those to DHIS2 as
the event date and a data element respectively.


#### Configure the integration

Navigate to "Project Settings" > "Data Forwarding". Under "Forward Cases
as DHIS2 Tracked Entities" click "Add a forwarding location".

Set "URL to forward to" to the URL for the DHIS2 stable demo, which at
the time of writing is "https://play.dhis2.org/2.31.5/". Development on
DHIS2 is steady, and your version number will be different.
"Authentication protocol" is "Basic", and "Username" and "Password" are
"admin" and "district" respectively.

Click "Start forwarding".

On the "Data Forwarding" page, under "Forward Cases as DHIS2 Tracked
Entities", you will now find a row for "play.dhis2.org". Click the
"Configure" button to the right of it.

Paste the following into "Case config":
```json
{
  "doc_type": "Dhis2CaseConfig",
  "case_type": "case",
  "te_type_id": "nEenWmSyUEp",
  "tei_id": {
    "doc_type": "CaseProperty",
    "case_property": "dhis2_tei_id"
  },
  "org_unit_id": {
    "doc_type": "CaseOwnerAncestorLocationField",
    "location_field": "dhis_id"
  },
  "attributes": {
    "w75KJ2mc4zz": {
      "doc_type": "CaseProperty",
      "case_property": "given_name"
    },
    "zDhUuAYrxNC": {
      "doc_type": "CaseProperty",
      "case_property": "family_name"
    },
    "iESIqZ0R0R0": {
      "doc_type": "CaseProperty",
      "case_property": "date_of_birth"
    }
  },
  "finder_config": {
    "property_weights": [
      {
        "case_property": "given_name",
        "weight": "0.35"
      },
      {
        "case_property": "family_name",
        "weight": "0.55"
      },
      {
        "case_property": "date_of_birth",
        "weight": "0.1"
      }
    ],
    "confidence_margin": "0.5"
  },
  "form_configs": [
    {
      "doc_type": "Dhis2FormConfig",
      "xmlns": "http://openrosa.org/formdesigner/F850C145-D805-4B35-925B-A7D35141FD13",
      "program_id": "uy2gU8kT1jF",
      "program_stage_id": {
        "doc_type": "ConstantString",
        "value": "eaDHS084uMp"
      },
      "org_unit_id": {
        "doc_type": "FormUserAncestorLocationField",
        "location_field": "dhis_id"
      },
      "event_date": {
        "doc_type": "FormQuestion",
        "form_question": "/data/lmp_date"
      },
      "event_status": "ACTIVE",
      "datavalue_maps": [
        {
          "data_element_id": "OuJ6sgPyAbC",
          "value": {
            "doc_type": "FormQuestion",
            "form_question": "/data/visit_comment"
          }
        }
      ]
    }
  ]
}
```

That looks long, so let us break it down, and go through each chunk.

MOTECH supports integrating more than one case type with a DHIS2 server,
but to start we will just configure one. "case type" is set to "case",
which is the initial case type for a case list menu. Normally it would
make sense for this case type to have the same or a similar name as the
tracked entity type, like "person", or "mother".

"te_type_id" is "nEenWmSyUEp". This is the ID of the tracked entity
type, "Person".

Next is "tei_id". This is the case property that will store the ID of
the tracked entity instance. The next time that the case is forwarded to
DHIS2, MOTECH will use the value of this case property to retrieve the
tracked entity instance immediately, and avoid having to search DHIS2
for it again.

"org_unit_id" specifies how MOTECH should determine the ID of the DHIS2
location that this request applies to. DHIS2 is often used on a national
scale, so everything needs to be associated with a location. For
CommCare projects that are specific to a small geographical location the
org unit could be a constant. But usually we will look it up based on
the location of the mobile worker who submitted the form, or the
location of the mobile worker, group or location that owns the case. In
this example we are using the case owner. MOTECH will look at the
location metadata for the field named "dhis_id", and use the value it
finds there. If it does not find a value, it will check the next
ancestor location until it finds a value. (If it gets to the top of the
location hierarchy without finding a value, it will leave out the
org_unit_id from the request. If the org unit is required then the
request will fail.)

The "attributes" dictionary is keyed on the IDs of tracked entity
attributes in DHIS2, and maps them to their corresponding case
properties. This is how MOTECH determines which attributes to update
when registering or updating a tracked entity instance. You can use case
properties or constants, but it is not recommended to use form
questions because if the case is updated by a form that is missing that
question, DHIS2 will remove the value of the attribute from the tracked
entity instance instead of leaving it the same.

"finder_config" manages the configuration of how MOTECH searches DHIS2
to find a matching tracked entity instance for a case.

Each case property that is used to determine a match is assigned a
weight. The case is compared with the search results, and the weights of
each case property that matches the corresponding attribute of a tracked
entity instance are added together to come up with a score for that
tracked entity instance. If the score is 1.0 or more then that tracked
entity instance is considered a candidate. Usually there is only one
candidate. But if there is more than one, MOTECH compares the scores of
the top candidates, and if the score of the first candidate is much
higher than the rest, then that candidate is considered a match.
"confidence_margin" sets how much higher the top score needs to be from
the second best score. But if the candidates' scores are too close to
call, then MOTECH does not guess. An error is raised and that case is
not forwarded to DHIS2.

"form_configs" reuses the configuration that MOTECH uses to send forms
to DHIS2 as Events. "xmlns" identifies the form, and "program_id" is the
ID of the DHIS2 Program the events belong to. If the program has more
than one stage, the program stage that the event is for must also be
given. This is usually a "ConstantString", but it could potentially come
from a form question value.

"event_date" is the date of the start of the event. "event_status" is
one of "ACTIVE", "COMPLETED", "VISITED", "SCHEDULED", "OVERDUE" or
"SKIPPED".

And lastly, "datavalue_maps" sets DHIS2 data element values. In this
example we are only collecting one, but setting data element values is
the reason we send Events to DHIS2, and usually there will be many.

Save the configuration by clicking "Update DHIS2 Tracked Entity
configuration".


#### Set up locations

In the configuration, "org_unit_id" is mentioned twice. For the tracked
entity, its value is found using `CaseOwnerAncestorLocationField`:

    "org_unit_id": {
      "doc_type": "CaseOwnerAncestorLocationField",
      "location_field": "dhis_id"
    },

For the tracked entity's events, its value is found using
`FormUserAncestorLocationField`:

    "org_unit_id": {
      "doc_type": "FormUserAncestorLocationField"
      "location_field": "dhis_id",
    },

These do similar things. They both search up the location hierarchy, of
the case owner and the form user respectively, looking for a value in a
location metadata field named "dhis_id".

This value should be the ID of the DHIS2 organization unit that
corresponds with the CommCare location.

Using the same method that you used to find the ID of programs in DHIS2,
by opening their page in your browser and checking the URL, look up the
IDs of the organization units you need.

Then in CommCare HQ, edit the corresponding location, and add that ID to
to the location's metadata, in a field named "dhis_id".


#### Test

To test our configuration, open the app in App Preview and register a
woman.

Then click on "MOTECH Logs" and confirm the requests sent to DHIS2 all
succeeded.
