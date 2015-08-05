# Millennium Villages Project Reports

## Overview

MVP reports are build off of a very complicated indicator framework. The configuration for the indicators lives in a combination of the code and couch. The indicators themselves live on copies of the form and case documents that are saved to a second database (commcarehq__mvp-indicators). The indicators live in a property called `computed_`  which is added to the documents by two pillows (the `MVPFormIndicatorPillow` and `MVPCaseIndicatorPillow`). The pillows are also responsible for copying the document from the primary database to the secondary one, which happens at the same time.

## The `INDICATOR_CONFIGURATION` Document

The `INDICATOR_CONFIGURATION` document (which lives in Couch DB) maps domains to indicator namespaces. On prod there is only one namespace (`"mvp_indicators"`). This document is how CommCare HQ knows that a domain is using the indicators in this framework.

### Initializing the `INDICATOR_CONFIGURATION` Document

Create a document in Couch DB with the following structure:

```
{
   "_id": "INDICATOR_CONFIGURATION",
   "namespaces": {}
}
```

### Add a Project to the `INDICATOR_CONFIGURATION` Document

If your project has the slug `mvp-sauri` (this is what comes after
`www.commcarehe.org/a/ in your project's URL), then you would add the following
 to the `namespaces` dictionary, so that it looks like:

 ```
 "namespaces": {
    "mvp-sauri": [
        ["mvp_indicators", "MVP"]
    ]
 }
 ```

## The `IndicatorDefinition` documents

The `IndicatorDefinition` documents also live in the Couch Database. Each `IndicatorDefinition` has a number of attributes (namespace, domain, etc.) that describe how it should be applied to data.

Indicators get computed whenever a form or case is submitted. They can depend on the form/case itself as well as the forms/cases referenced in that form/case. They do not depend on any other indicators and only on primary data.

Here is a quick summary of some supported types.


Type                              | Purpose
----------------------------------|-----------------------
FormLabelIndicatorDefinition      | Map an xmlns to a label and save it on the document
FormDataAliasIndicatorDefinition  | Get a specific value from a form (based on a question ID)
CaseDataInFormIndicatorDefinition | Lookup a case property from the case that was submitted with the form
FormDataInCaseIndicatorDefinition | A _case_ indicator, that updates forms whenever they are submitted against a case


## Form processing

This walks through what happens when a form is processed by the pillow. An analogous set of steps happen for cases (although cases are actually more complicated).

1. The `change_transform` function handles deletions and then calls `process_indicators`
2. All `FormIndicatorDefinition` objects for the form's `(domain, xmlns)` combination are pulled out
3. Those `FormIndicatorDefinition`s are applied to the form in bulk
4. The form is saved back to the new database.

## Case processing

Case processing is very similar to form processing except there is a final step. All form-dependent indicators are applied to all the case's forms each time the case is processed. This means that the case processing can update indicators in forms!


## Debugging Tips

### Have a Copy of the Project, its Applications, and its Users on a Local Instance

1) Make sure your project has the same `slug`. For instance, if your project on
production is located at www.commcarehq.org/a/mvp-sauri/ make sure that locally
the project lives at localhost:8000/a/mvp-sauri/.

2) Make sure your LOCAL user is a Django Admin by going to localhost:8000/admin/
search for your user and checking staff and is admin. Then and subscribe your
project to the Dimagi Enterprise plan, by going to Project Settings > Current Subscription >
Change Plan and select Enterprise.

3) On the PRODUCTION machine, navigate to each application that project and
follow the steps outlined for [Transferring an Application Between
Projects or Servers](https://help.commcarehq.org/display/commcarepublic/Transferring+an+Application+Between+Projects+or+Servers)
to copy each application to your LOCAL project.

4) LOCALLY: Navigate to the Reports section of your project. If you do not
see the Administer Indicators option as a second tier of navigation (blue bar
below the main navigation), then add the project to your
`INDICATOR_CONFIGURATION` document in Couch DB (steps described earlier in
this document).

5) Once you are able to see the Administer Indicators option under reports
on the PRODUCTION copy of your application, navigate to Other Actions >
Download Indicators Export. Save the .json file. Visit the LOCAL copy of your
project space, and click on Bulk Import Indicators. Select the file you just
downloaded and upload the file. You should now have a copy of your indicator
definitions locally.

6) Copy the Mobile Workers from PRODUCTION by visiting your project space's Users
tab > Mobile Workers and clicking Bulk Upload. Download the Mobile Workers
excel spreadsheet and add a password for each mobile worker.

Make sure that the `celeryd` process is running LOCALLY:

```
python manage.py celeryd -v 2 -BE
````

Navigate to Users > Mobile Workers and click Bulk Upload. Upload the excel
file that you downloaded from production here.


### Submit Forms to Your Local Project Space

The best way to test whether or not your indicator views have the correct logic
is to submit real forms to your local instance.

1) For indicators to process incoming forms properly, you need to be running
pillowtop alongside your server instance. Do this by running:

```
python manage.py run_ptop --all
```

2) If you know the ID of your form, download its XML from the PRODUCTION copy
of your project space by visiting:

```
/a/<project_name>/reports/form_data/<form_id>/download/
```

3) LOCALLY: Go to your project space's Project Settings > Basic and un-check
"Only accept secure submissions"

4) Follow the steps outlined in the [Submission API help](https://help.commcarehq.org/display/commcarepublic/Submission+API)
to submit your downloaded form (as an .xml document) to your local copy of
CommCare HQ.


### Check Form Processing in Couch DB

Once you've submitted your form to HQ, you can see how it was processed by
visiting

```
http://localhost:5984/_utils/document.html?<database_name>/<form_id>
```

Things to look for:

- Is `mvp_indicators` populated with data? If no, then check:
    - is ptop running?
    - were there errors in the couch view? (look at your couch db's log file)

- Are the values what you expect?

- Are some of the indicators present, but others that should be there missing?
If so, check your couch view for those missing indicators, as you may have a
javascript error.


### Debugging Report Views

Both the MVIS and CHW reports have debug views that could be useful in gathering
document IDs that are contributing toward some indicator totals.

#### MVIS Debugging

The MVIS indicator API can be accessed by visiting:

```
/a/<project_name>/reports/custom/partial/health_coordinator/?indicator=<indicator_slug>&debug=true&cache=false&num_prev=1
```

`cache` parameter turns on and off caching. `num_prev` is the number of months
to include in the retrospective. An additional parameter called `current_month`
is the month you'd like to start the retrospective from. For example if we
wanted October 2014, we would specify `current_month=2014-10`.

NOTE: It's highly recommended that you only fetch one or two months at a time
(`num_prev` is 0 or 1) because some of the debugging calculations can take a VERY
long time.

#### CHW Debugging

The CHW indicator API can be accessed by visiting:

```
/a/<project_name>/reports/custom/partial/chw_manager/?indicator=<indicator_slug>&debug=true&cache=false
```
