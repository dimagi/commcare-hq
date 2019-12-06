The MOTECH DHIS2 Module
=======================

See the [MOTECH README](../README.md#the-dhis2-module) for a brief
introduction to DHIS2 in the context of MOTECH.

MOTECH currently supports two ways of integrating with DHSI2: Forwarding
aggregated data as DHIS2 DataSets; and forwarding form question values
as DHIS2 Anonymous Events.

Use the "Enable DHIS2 integration" feature flag for both.


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
**Forward to DHIS2**.

If it is not already defined, add a forwarding location. (This is
sometimes refered to as a "forwarder", and in the source code it is a
[`Dhis2Repeater`](./repeaters.py).) Enter the details of the DHIS2
server. When you are done, click "Start Forwarding".

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
          "form_question": "/data/event_date",
        },
        "event_status": "COMPLETED",
        "org_unit_id": {
          "doc_type": "ConstantString",
          "value": "NwGKQaHk5mx",
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
