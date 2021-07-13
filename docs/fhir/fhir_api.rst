The FHIR API
============

CommCare offers a FHIR R4 API. It returns responses in JSON.

The FHIR API is not yet targeted at external users. API users must be
superusers.

The API focuses on the Patient resource. The endpoint for a Patient
would be
``https://www.commcarehq.org/a/<domain>/fhir/R4/Patient/<case-id>``

To search for the patient's Observations, the API accepts the
"patient_id" search filter. For example,
``https://www.commcarehq.org/a/<domain>/fhir/R4/Observation/?patient_id=<case-id>``


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

CommCare HQ is now accessible at ``http://localhost:8000/``


A Reference API Client
^^^^^^^^^^^^^^^^^^^^^^

A simple example of a web service that calls the CommCare HQ FHIR API
to retrieve patient data is available as a reference.

You can find it implemented using the `Flask`_ Python web framework, or
`FastAPI`_ for async Python.


.. _Flask: https://github.com/dimagi/commcare-fhir-web-app/
.. _FastAPI: https://github.com/dimagi/commcare-fhir-web-app/tree/fast_api
