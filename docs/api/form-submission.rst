Form Submission API
===================

CommCare's Submission API implements the OpenRosa standard Form Submission API for submitting XForms over HTTP/S. You can find details of the `Form Submission API standard here <https://bitbucket.org/javarosa/javarosa/wiki/FormSubmissionAPI>`_.
  

Submitting Forms
----------------

There are two ways to submit a form to CommCare HQ:

1. As multipart/form-data; CommCare uses this method in J2ME.
2. As the body of a POST request; CommCare does this on Android.

Below are sample commands for submitting an XForm saved in a file called "xform.xml" to the domain called "demo". (You will need to change these two values in the commands below to suit your own purposes.)

Submission as multipart/form-data
---------------------------------

.. code-block:: bash

    $ curl -F "xml_submission_file=@xform.xml" \
        -u mobile.worker@demo.commcarehq.org:password \
        "https://www.commcarehq.org/a/demo/receiver/api/"

One way to think of this is that the incoming request looks exactly like a request sent by submitting the XForm using the following multi-part HTML form:

.. code-block:: html

    <form method="post"
          enctype="multipart/form-data"
          action="https://www.commcarehq.org/a/demo/receiver/api/">
      <input type="file" name="xml_submission_file"/>
      <input type="submit" value="Submit form"/>
    </form>

Submission as the Body of a POST Request
----------------------------------------

.. code-block:: bash

    $ curl -d @xform.xml \
        -u mobile.worker@demo.commcarehq.org:password \
        "https://www.commcarehq.org/a/demo/receiver/api/"
                                                                                                                   
There is no equivalent of this as an HTML form because the command above submits the contents of the file as the request body.                                                                                                                   

Submitting for a Specific Application
-------------------------------------

In a number of places, CommCare reporting relies on tagging form submissions with the application that they belong to. To tag a form submission with its application, submit it to its application's URL:

.. code-block:: text

    https://www.commcarehq.org/a/demo/receiver/[APPLICATION_ID]/

Application ID can be found in the application edit URL. Example:

.. code-block:: text

    https://www.commcarehq.org/a/demo/apps/view/952a0b480c7c10dde777b2485375d2237/

Application ID: ``952a0b480c7c10dde777b2485375d2237``

The XForm
----------

The Submission API is specifically for submitting XForms.

If you are not already working with XForms, the easiest way to get started is to use a form that has already been submitted to CommCare. If your project focuses on cases, go to the "Case List" report, choose a case, and select the "Case History" tab. There you will find a list of the form submissions that built the case. Choose a form, and select the "Raw XML" tab. You will find the XForm submission.

If your project is just based on forms, not cases, use the "Submit History" report. Choose a form, and select the "Raw XML" tab.

Once you have an example, modify it to suit your needs.

Let us go through an example of an XForm submission, to see what you might want to keep, change, or drop:

.. code-block:: xml

    <?xml version="1.0" ?>
    <data name="Enregistrer un cas COVID-19"
          uiVersion="1"
          version="41"
          xmlns="http://openrosa.org/formdesigner/9baceb4c25a5">
      <consent_list>
        <consent_confirmation>yes</consent_confirmation>
      </consent_list>
      <patient_information>
        <covid_id>
          <id_region>KAR</id_region>
          <id_district>BAS</id_district>
          <id_number>306</id_number>
          <unique_id>KAR-BAS-306</unique_id>
          <auto_id>WSW2Y36</auto_id>
        </covid_id>
        <basic_demo>
          <given_name>Moujid</given_name>
          <family_name>GOUPAWEMEY</family_name>
        </basic_demo>
        <name_family_given>GOUPAWEMEY, Moujid</name_family_given>
        <patient_status>suspected</patient_status>
        <patient_location>1.2345678 9.0123456 7.8 901.2</patient_location>
        <suspect>
          <suspected_label>OK</suspected_label>
        </suspect>
      </patient_information>
      <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
        <n1:deviceID>commcare_37478fd5-2730-4a14-a847-84e8848a1ff5</n1:deviceID>
        <n1:timeStart>2020-06-08T18:38:13.855Z</n1:timeStart>
        <n1:timeEnd>2020-06-08T18:41:33.207Z</n1:timeEnd>
        <n1:username>exampleuser</n1:username>
        <n1:userID>de8cc5191f9b4e2a846069f0659fa35e</n1:userID>
        <n1:instanceID>dca03509-4446-41dc-8352-2bb6f8516c7b</n1:instanceID>
        <n2:appVersion xmlns:n2="http://commcarehq.org/xforms">CommCare Version 2.48. Build 461457</n2:appVersion>
      </n1:meta>
    </data>

The "data" node
~~~~~~~~~~~~~~~

.. code-block:: xml

    <data name="Enregistrer un cas COVID-19"
          uiVersion="1"
          version="41"
          xmlns="http://openrosa.org/formdesigner/9baceb4c25a5">

- Change "name" and "version" to something useful to you. They are optional, but "name" can be useful for reporting.
- Change "xmlns" to something that indicates the origin of the form submission. For this example, 'xmlns="http://example.org/covid19/"' could be appropriate.

The "data/meta" node
~~~~~~~~~~~~~~~~~~~~

This node should always be a direct child of the root node (``data`` in this instance):

.. code-block:: xml

    <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
      <n1:deviceID>commcare_37478fd5-2730-4a14-a847-84e8848a1ff5</n1:deviceID>
      <n1:timeStart>2020-06-08T18:38:13.855Z</n1:timeStart>
      <n1:timeEnd>2020-06-08T18:41:33.207Z</n1:timeEnd>
      <n1:username>exampleuser</n1:username>
      <n1:userID>de8cc5191f9b4e2a846069f0659fa35e</n1:userID>
      <n1:instanceID>dca03509-4446-41dc-8352-2bb6f8516c7b</n1:instanceID>
      <n2:appVersion xmlns:n2="http://commcarehq.org/xforms">CommCare Version 2.48. Build 461457</n2:appVersion>
    </n1:meta>

- ``deviceID``: Use the device ID to set an identifier for the source of the submitted data.
- ``timeStart``: When the user opened the form. If the form is built programmatically, "now" is a reasonable value.
- ``timeEnd``: When the user completed the form. Like "timeStart", "now" is a reasonable fallback.
- ``username``: The name of the user / mobile worker who submitted the form.
- ``userID``: The ID of the user / mobile worker who submitted the form.
- ``instanceID``: A unique ID for this form submission. Generate a new Version 4 UUID for every form submission.
- ``appVersion``: If the form belongs to an app, this can offer useful context for its data. You can submit an empty node if it is not relevant.


Case Management
---------------

The form above is simply a nested structure of answers to form questions. Case management is a powerful feature of CommCare that it is not using.

Here is a form that registers a case using the data provided by the answers to the form questions shown above:

.. code-block:: xml

    <?xml version="1.0" ?>
    <data name="Enregistrer un cas COVID-19"
          uiVersion="1"
          version="41"
          xmlns="http://openrosa.org/formdesigner/9baceb4c25a5">
      <!-- ... form questions and answers ... -->
      <n0:case case_id="47035f62-c91d-4811-adfd-9d925bc61b99"
               date_modified="2020-06-08T18:41:33.207Z"
               user_id="de8cc5191f9b4e2a846069f0659fa35e"
               xmlns:n0="http://commcarehq.org/case/transaction/v2">
        <n0:create>
          <n0:case_name>GOUPAWEMEY, Moujid</n0:case_name>
          <n0:owner_id>de8cc5191f9b4e2a846069f0659fa35e</n0:owner_id>
          <n0:case_type>covid_19_case</n0:case_type>
        </n0:create>
        <n0:update>
          <n0:case_location>9.2612578 0.7801739 0.0 500.0</n0:case_location>
          <n0:case_status>suspected</n0:case_status>
          <n0:family_name>KPIGMARE</n0:family_name>
          <n0:given_name>Didjate</n0:given_name>
          <n0:name_family_given>KPIGMARE, Didjate</n0:name_family_given>
          <n0:unique_id>KAR-BAS-306</n0:unique_id>
        </n0:update>
      </n0:case>
      <!-- ... meta ... -->
    </data>

If you only want to create or update cases, your form can omit the form questions and answers.

The "data/case" node
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: xml

    <n0:case case_id="47035f62-c91d-4811-adfd-9d925bc61b99"
             date_modified="2020-06-08T18:41:33.207Z"
             user_id="de8cc5191f9b4e2a846069f0659fa35e"
             xmlns:n0="http://commcarehq.org/case/transaction/v2">

- The "case_id" attribute is mandatory and must be unique. Use a UUID4 identifier.
- One form can create and update multiple cases. If this is your use case, just add more "data/case" nodes.

The "data/case/create" node
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: xml

    <n0:create>
      <n0:case_name>GOUPAWEMEY, Moujid</n0:case_name>
      <n0:owner_id>de8cc5191f9b4e2a846069f0659fa35e</n0:owner_id>
      <n0:case_type>covid_19_case</n0:case_type>
    </n0:create>

- All the tags inside the "data/case/create" node above are mandatory.
- The form must provide the ID of the mobile worker or CommCare location who will own all cases that the form creates.
- Cases must also have a case type and a name.

The "data/case/update" node
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: xml

    <n0:update>
      <n0:case_location>9.2612578 0.7801739 0.0 500.0</n0:case_location>
      <n0:case_status>suspected</n0:case_status>
      <n0:family_name>KPIGMARE</n0:family_name>
      <n0:given_name>Didjate</n0:given_name>
      <n0:name_family_given>KPIGMARE, Didjate</n0:name_family_given>
      <n0:unique_id>KAR-BAS-306</n0:unique_id>
    </n0:update>

- The tags inside the "data/case/update" node are custom case properties.
- Normal variable name rules apply (all ASCII, starts with a letter, no spaces or punctuation other than underscores). It is convention to use snake case.

The User
~~~~~~~~

It is possible to set the case "owner_id" and the form "userID" to the ID of a web user (a user who is able to log into CommCare HQ) and the form "username" to their username, but by default their cases will not appear in reports.

It is strongly recommended to use the ID and username of a mobile worker.

Response
--------

The response to a form submission is an XML payload as follows:

.. code-block:: xml

    <OpenRosaResponse xmlns="http://openrosa.org/http/response">
        <message nature="{{nature}}">{{message}}</message>
    </OpenRosaResponse>

It has two pieces of data:

- **nature**: Intended to classify the response.
- **message**: A human-readable message.

In addition to the response XML, the HTTP response code is also important.

OpenRosa V 2.0
--------------

Response Codes
~~~~~~~~~~~~~~

.. list-table:: Response Codes
   :widths: 10 20 50
   :header-rows: 1

   * - Response
     - Nature
     - Meaning
   * - 201
     - submit_success
     - Form was received and successfully processed.
   * - 201
     - submit_error
     - Form was received but could not be processed.
       See 'message' for more details.
   * - 401
     - -
     - Authentication failed.
       User not allowed to submit forms or authentication credentials incorrect.
   * - 500
     - submit_error
     - Unable to process form XML. Usually due to malformed XML.
   * - 500
     - -
     - Unexpected server error.

Example Success Response
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: xml

    <OpenRosaResponse xmlns="http://openrosa.org/http/response">
        <message nature="submit_success">   √   </message>
    </OpenRosaResponse>

Example Error Response
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: xml

    <OpenRosaResponse xmlns="http://openrosa.org/http/response">
        <message nature="submit_error">InvalidCaseIndex: Case '349580db10da4a67b7089c541742c88b' references non-existent case '9766f50abda94c26a4569df5ce6dda6d'</message>
    </OpenRosaResponse>

OpenRosa V 3.0
--------------

Response Codes
~~~~~~~~~~~~~~

.. list-table:: Response Codes
   :widths: 10 20 50
   :header-rows: 1

   * - Response
     - Nature
     - Meaning
   * - 201
     - submit_success
     - Form was received and successfully processed.
   * - 422
     - processing_failure
     - Form received but an error occurred during processing.
       Re-submission likely to result in the same error (e.g., InvalidCaseId).
       Mobile device will 'quarantine' the form and set the quarantine message to the response.
   * - 500
     - submit_error
     - Unable to process form XML. Usually due to malformed XML.
   * - 500
     - -
     - Unexpected server error.

Code Example
-------------

The `submission_api_example` repository on GitHub has an example script to illustrate how to use the Submission API to create CommCare cases. It also has a short explanation of what the code does, so that you can use it as a reference for implementing in your own language or adapt it for your own use case.

Application-Specific Submissions
--------------------------------

A number of places in CommCare reporting rely on tagging form submissions with the application to which they belong. To have forms submitted to the API 'tagged' with the appropriate application, you should submit them to the application-specific URL:

.. code-block:: text

    https://www.commcarehq.org/a/demo/receiver/[APPLICATION ID]/

The application ID can be found in the application edit URL. Example:

.. code-block:: text

    https://www.commcarehq.org/a/demo/apps/view/952a0b480c7c10dde777b2485375d2237/

Application ID: ``952a0b480c7c10dde777b2485375d2237``

Additional Notes
----------------

For compatibility with CommCare ODK, the Android CommCare client, the URLs above can also be replaced with:

.. code-block:: text

    https://www.commcarehq.org/a/demo/receiver/submission/


