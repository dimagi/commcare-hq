Importing cases from a remote FHIR service
==========================================

Overview
--------

CommCare can poll a remote FHIR service, and import resources as new
CommCare cases, or update existing ones.

There are three different strategies available to import resources of a
particular resource type:

1. Import all of them.
2. Import some of them based on a search filter.
3. Import only the ones that are referred to by resources of a different
   resource type.

The first two strategies are simple enough. An example of the third
strategy might be if we want CommCare to import ServiceRequests (i.e.
referrals) from a remote FHIR service, and we want to import only the
Patients that those referrals are for.

CommCare can import only those Patients, and also create parent-child
case relationships linking a ServiceRequest as a child case of the
Patient.


Configuring a FHIRImporter
--------------------------

Currently, all configuration is managed via Django Admin (except for
adding Connection Settings).

.. warning::
    Django Admin cannot filter select box values by domain. Name your
    Connection Setting with the name of your domain so that typing the
    domain name in the select box will find it fast.

    .. TODO: Is this definitely true? Is there no way to filter select
             box values by domain?

In Django Admin, navigate to FHIR > FHIR Importers. If you have any
FHIRImporter instances, they will be listed there, and you can filter by
domain. To add a new one, click "Add FHIR Importer +".

The form is quite straight forward. You will need to provide the ID of a
mobile worker in the "Owner ID" field. All cases that are imported will
be assigned to this user.

This workflow will not scale for large projects. When such a project
comes up, we have planned for two approaches, and will implement one or
both based on the project's requirements:

1. Set the owner to a user, group or location.
2. Assign a FHIRImporter to a CommCare location, and set ownership to
   the mobile worker at that location.


Mapping imported FHIR resource properties
-----------------------------------------

Resource properties are mapped via the Admin interface using
ValueSource definitions, similar to :ref:`admin-interface-mapping` for
data forwarding and the FHIR API. But there are a few important
differences:

The first difference is that FHIRRepeater and the FHIR API use
FHIRResourceType instances (rendered as "FHIR Resource Types" in Django
Admin) to configure mapping; FHIRImporter uses FHIRImporterResourceType
instances ("FHIR Importer Resource Types").

To see what this looks like, navigate to FHIR > FHIR Importer Resource
Types, and click "Add FHIR Importer Resource Type".

Select the FHIR Importer, set the name of the FHIR resource type, and
select the case type.

.. note::
    The resource types you can import are not limited to the resource
    types that can be managed using the Data Dictionary. But if you want
    to send the same resources back to FHIR when they are modified in
    CommCare, then you will either need to stick to the Data Dictionary
    FHIR resource types limitation, or add the resource type you want to
    the list in `corehq/motech/fhir/const.py`_.)

The "Import related only" checkbox controls that third import strategy
mentioned earlier.

"Search params" is a dictionary of search parameters and their values to
filter the resources to be imported. Reference documentation for the
resource type will tell you what search parameters are available. (e.g.
`Patient search parameters`_)

"Import related only" and the "Search params" are applied together, to
allow you to filter related resources.

There is a second important difference between FHIRImporterResourceType
and FHIRResourceType: With FHIRResourceType, the ValueSource
configurations are used for *building* a FHIR resource. With
FHIRImporterResourceType they are used for *navigating* a FHIR resource.

So FHIRResourceType might include ValueSource configs for setting a
Patient's phone number. They might look like this:

.. code:: javascript

    {
      "jsonpath":"$.telecom[0].system",
      "value": "phone"
    }

.. code:: javascript

    {
      "jsonpath":"$.telecom[0].value",
      "case_property": "phone_number"
    }

When we are navigating an imported resource to find the value of the
Patient's phone number, we don't know whether it will be the first item
in the "telecom" list. Instead, we search the "telecom" list for the
item whose "system" is set to "phone". That is defined like this:

.. code:: javascript

    {
      "jsonpath":"$.telecom[?system='phone'].value",
      "case_property": "phone_number"
    }

The third difference is that although the mappings will look the same,
for the most part, they may map to different case properties. This is
because we have found that projects often want a mobile worker to check
some of the imported values before overwriting existing values on the
case. It is wise to confirm with the delivery team how to treat case
properties that can be edited.


.. _corehq/motech/fhir/const.py: https://github.com/dimagi/commcare-hq/blob/master/corehq/motech/fhir/const.py#L35
.. _Patient search parameters: https://www.hl7.org/fhir/patient.html#search
