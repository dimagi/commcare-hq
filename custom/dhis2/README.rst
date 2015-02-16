World Vision Sri Lanka Nutrition project: DHIS2 API integration
===============================================================

For the WV Sri Lanka Nutrition project, CommCare integrates with the DHIS2
REST API.


Specification
-------------

1. Users can use CommCareHQ to manually associate information on the
   DHIS2 instance (ex. reporting organizations, user identifiers) with
   mobile workers created in CommCareHQ.

   1. Custom user data in CommCareHQ will be used to specify a custom
      field on each mobile worker called dhis2_organization_unit_id.
      This will contain the ID of the DHSI2 organization unit that the
      mobile worker (midwife) is associated with and submitted data for.
      The organization unit ID will be included as a case property on
      each newly created case.

2. CommCareHQ will be setup to register child entities in DHIS2 and
   enroll them in the Pediatric Nutrition Assessment and Underlying Risk
   Assessment programs when new children are registered through
   CommCareHQ. This will be done through the DHIS2 API and may occur as
   soon as data is received by CommCareHQ from the mobile, or be
   configured to run on a regular basis.

   1. When a new child_gmp case is registered on CommCareHQ, we will use
      the DHIS2 trackedEntity API to generate a new Child entity. We
      will also register that new entity in a new Pediatric Nutrition
      Assessment program. The new Child entity will be updated with the
      attribute ccqh_case_id that contains the case ID of the CommCareHQ
      case.

   2. The Pediatric Nutrition Assessment program will be updated with
      First Name, Last Name, Date of Birth, Gender, Name of
      Mother/Guradian, Mobile Number of the Mother and Address
      attributes.

   3. For children of the appropriate risk level (conditions to be
      decided) we will also enroll that Child entity in the Underlying
      Risk Assessment program.

   4. The entity will be registered for the organization unit specified
      by the dhis2_organization_unit_id case property.

   5. If a CommCareHQ case does not have a dhis2_organization_unit_id

   6. The corresponding CommCareHQ case will be updated with the IDs of
      the registered entity and each program that entity was registered
      in. This will be used for later data submissions to DHIS2.

3. CommCareHQ will be configured to use the DHIS2 API and download a
   list of registered children on a regular basis. This will be used to
   create new child cases for nutrition tracking in CommCare or to
   associate already registered child cases on the mobile with the DHIS2
   child entities and the Pediatric Nutrition Assessment and Underlying
   Risk Assessment programs.

   1. Custom code in HQ will run on a periodic basis (nightly) to poll
      the DHIS2 trackedEntity API and get a list of all registered Child
      entities

   2. For all child entities without a provided ccqh_case_id attribute,
      a new child_gmp case will be registered on CommCareHQ. It will be
      assigned to a mobile worker with the appropriate
      dhis2_organization_unit_id corresponding to the organization of
      the tracked entity in DHIS2.

   3. The registered child_gmp will be updated with additional case
      properties to indicate its corresponding DHIS2 entities and
      programs.

   4. Once the case has been registered in CommCareHQ, the DHIS2 tracked
      entity will be updated with the corresponding ccqh_case_id.

4. CommCareHQ will use the DHIS API to send received nutrition data to
   DHIS2 as an event that is associated with the correct entity,
   program, DHIS2 user and organization.

   1. On a periodic basis, CommCareHQ will submit an appropriate event
      using the DHIS2 events API (Multiple Event with Registration) for
      any unprocessed Growth Monitoring forms.

   2. The event will only be submitted if the corresponding case has a
      DHIS2 mapping (case properties that indicate they DHIS2 tracked
      entity instance and programs for the case). If the case is not yet
      mapped to DHIS2, the Growth Monitoring form will not be processed
      and could be processed in the future (if the case is later
      associated with a DHIS entity).

   3. The event will contain the program ID associated with case, the
      tracked entity ID and the program stage (Nutrition Assessment). It
      will also contain the recorded height and weight as well as
      mobile-calculated BMI and Age at time of visit.


DHIS API documentation
----------------------

In DHIS2, tracked entity instances are analogous to cases. Tracked
entities are user-defined data types of tracked entity instances. Their
attributes are also user-defined, and are named tracked entity
attributes.

In the World Vision Sri Lanka Nutrition project the tracked entity we
are interested in is called "Child", and corresponds to the "child_gmp"
CommCareHQ case type.

DHIS2 tracked entity instances are enrolled in programs, for which
reports are generated. A report datum is called an "event".

All data is structured with a tree to allow for a multi-tenant API where
user-defined data is strictly separated. The nodes of this tree are
named "organisation units" (which DHIS2 has borrowed from X.500's and
LDAP's organizational units). In the DHIS2 context, an organisation unit
is usually a country, region or facility.

API queries need to specify the organisation unit as a parameter named
"ou". By default, instances are returned for only that organisation
unit, using tracked entities defined at that node and above. To fetch
instances at that node and below, pass the parameter
"ouMode=DESCENDANTS".

apps.dhis2.org offers a well populated sample API. By using GET request
parameters in your browser, you don't need any plugins or addons for
testing. The username is "admin" and password "district".

You can get a list of organisation units from
https://apps.dhis2.org/demo/api/organisationUnits.json?links=false A
snippet looks like this:

.. code-block:: javascript

    {
        "pager": {
            "page": 1,
            "pageCount": 27,
            "total": 1332,
            "nextPage": "https://apps.dhis2.org/demo/api/organisationUnits?page=2"
        },
        "organisationUnits": [
            {
                "id": "Rp268JB6Ne4",
                "created": "2012-02-17T14:54:39.987+0000",
                "name": "Adonkia CHP",
                "lastUpdated": "2014-11-25T08:37:54.322+0000",
                "code": "OU_651071"
            },
            {
                "id": "cDw53Ej8rju",
                "created": "2012-02-17T14:54:39.987+0000",
                "name": "Afro Arab Clinic",
                "lastUpdated": "2014-11-25T08:37:53.882+0000",
                "code": "OU_278371"
            },
            // ...
            {
                "id": "t52CJEyLhch",
                "created": "2012-02-17T14:54:39.987+0000",
                "name": "Baoma MCHP",
                "lastUpdated": "2014-11-25T08:37:54.074+0000",
                "code": "OU_233393"
            }
        ]
    }

Here is a snippet of a list of tracked entities from
https://apps.dhis2.org/demo/api/trackedEntities?format=json&ou=jmIPBj66vD6

.. code-block:: javascript

    {
        "pager": {
            "page": 1,
            "pageCount": 1,
            "total": 7
        },
        "trackedEntities": [
            {
                "id": "bVkFYAvoUCP",
                "created": "2014-03-12T13:17:00.183+0000",
                "name": "ARV commodity",
                "lastUpdated": "2014-03-26T12:48:03.209+0000",
                "href": "https://apps.dhis2.org/demo/api/trackedEntities/bVkFYAvoUCP"
            },
            {
                "id": "UinS6TQnkUi",
                "created": "2014-04-14T11:54:19.781+0000",
                "name": "Borehole / well",
                "lastUpdated": "2014-04-14T11:54:19.781+0000",
                "href": "https://apps.dhis2.org/demo/api/trackedEntities/UinS6TQnkUi"
            },
            // ...
            {
                "id": "cyl5vuJ5ETQ",
                "name": "Person",
                "href": "https://apps.dhis2.org/demo/api/trackedEntities/cyl5vuJ5ETQ"
            }
        ]
    }

And tracked entity attributes from
https://apps.dhis2.org/demo/api/trackedEntityAttributes?format=json&ou=jmIPBj66vD6

.. code-block:: javascript

    {
        "pager": {
            "page": 1,
            "pageCount": 1,
            "total": 27
        },
        "trackedEntityAttributes": [
            {
                "id": "AMpUYgxuCaE",
                "created": "2014-01-09T18:12:46.547+0000",
                "name": "Address",
                "lastUpdated": "2014-07-18T15:13:34.752+0000",
                "href": "https://apps.dhis2.org/demo/api/trackedEntityAttributes/AMpUYgxuCaE"
            },
            {
                "id": "spFvx9FndA4",
                "created": "2014-01-09T18:12:46.582+0000",
                "name": "Age",
                "lastUpdated": "2014-07-18T15:13:34.749+0000",
                "href": "https://apps.dhis2.org/demo/api/trackedEntityAttributes/spFvx9FndA4"
            },
            // ...
            {
                "id": "n9nUvfpTsxQ",
                "created": "2014-03-26T12:33:10.320+0000",
                "name": "Zip code",
                "lastUpdated": "2014-07-18T15:13:34.712+0000",
                "code": "Zip code",
                "href": "https://apps.dhis2.org/demo/api/trackedEntityAttributes/n9nUvfpTsxQ"
            }
        ]
    }


A list of tracked entity instances works slightly differently. Instead
of a list of dictionaries, the data is structured like a spreadsheet,
with a list of column headers, followed by a list of rows. Here is a
list of tracked entity instances from
`https://apps.dhis2.org/demo/api/trackedEntityInstances
    ?format=json
    &ou=jmIPBj66vD6
    &ouMode=DESCENDANT
    &attribute=kyIzQsj96BD
    &attribute=NDXw0cluzSw
<https://apps.dhis2.org/demo/api/trackedEntityInstances?format=json&ou=jmIPBj66vD6&ouMode=DESCENDANTS&attribute=kyIzQsj96BD&attribute=NDXw0cluzSw>`_

.. code-block:: javascript

    {
        "headers": [
            {
                "name": "instance",
                "column": "Instance",
                "type": "java.lang.String",
                "hidden": false,
                "meta": false
            },
            {
                "name": "created",
                "column": "Created",
                "type": "java.lang.String",
                "hidden": false,
                "meta": false
            },
            {
                "name": "lastupdated",
                "column": "Last updated",
                "type": "java.lang.String",
                "hidden": false,
                "meta": false
            },
            {
                "name": "ou",
                "column": "Org unit",
                "type": "java.lang.String",
                "hidden": false,
                "meta": false
            },
            {
                "name": "te",
                "column": "Tracked entity",
                "type": "java.lang.String",
                "hidden": false,
                "meta": false
            },
            {
                "name": "kyIzQsj96BD",
                "column": "Company",
                "type": "java.lang.String",
                "hidden": false,
                "meta": false
            },
            {
                "name": "NDXw0cluzSw",
                "column": "Email",
                "type": "java.lang.String",
                "hidden": false,
                "meta": false
            }
        ],
        "metaData": {
            "pager": {
                "page": 1,
                "total": 4067,
                "pageSize": 50,
                "pageCount": 82
            },
            "names": {
                "cyl5vuJ5ETQ": "Person"
            }
        },
        "height": 50,
        "width": 7,
        "rows": [
            [
                "yyrQRtUEO62",
                "2014-03-26 15:40:12.905",
                "2014-03-28 12:27:49.148",
                "Gtnbmf4LkOz",
                "cyl5vuJ5ETQ",
                "Desmonds Formal Wear",
                "LidyaIdris@gustr.com"
            ],
            [
                "LiPJwPjkfpo",
                "2014-03-26 15:40:12.93",
                "2014-03-28 12:27:49.175",
                "fGp4OcovQpa",
                "cyl5vuJ5ETQ",
                "Pantry Food Stores",
                "GenetGebre@superrito.com"
            ],
            // ...
            [
                "FIa4Zu8eNcv",
                "2014-03-26 15:40:27.732",
                "2014-03-28 12:27:58.52",
                "Zr7pgiajIo9",
                "cyl5vuJ5ETQ",
                "Montana's Cookhouse",
                "TekleAlem@einrot.com"
            ]
        ]
    }

A few useful things to note here:
* The ID column of the tracked entity instances is not named "ID" or
  "id"; it's named "Identity"
* Column names of user-defined tracked entity attributes, in this case
  "Company" and "Email" are ID numbers.

The CommCareHQ DHIS2 API client compiles this data into a list of
dictionaries, and uses the "column" attribute (i.e. human-readable name)
for dictionary keys. An alternative approach might be to key the
dictionary with name-column tuples, e.g. `('NDXw0cluzSw', 'Email')`, but
that seems less readable, and more complex than necessary.

You can find more information in the `Web API chapter`_ of the
`DHIS2 Developer Manual`_.


.. _Web API chapter: https://www.dhis2.org/doc/snapshot/en/developer/html/ch01.html
.. _DHIS2 Developer Manual: https://www.dhis2.org/doc/snapshot/en/developer/html/dhis2_developer_manual.html


Conventions and Assumptions
---------------------------

We assume the following data is available in CommCare and DHIS2.


Setting up the CommCareHQ app
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Participating CommCare users need the following custom user property:

* dhis2_organization_unit_id: The organisation unit ID where the user is
  working. (In DHIS2 this can be a country, region or facility)

Required CommCare case attributes:

* dhis2_organization_unit_id: The organisation unit ID of the owner of the
  case.
* external_id: The DHIS2 tracked entity instance ID of the child.
  This will be imported from DHIS2, and doesn't need to be populated by
  the app.

Instead of creating an attribute for the DHIS2 tracked entity instance
ID, the DHIS2 API client uses `external_id`. This is indexed, and allows
us to fetch cases by their DHIS2 ID efficiently.

The Growth Monitoring forms that are used to populate child_gmp cases
must include:

* height
* weight
* mobile-calculated BMI
* age at time of visit
* hidden value "dhis2_te_inst_id" whose value is taken from the case's
  external_id
* hidden value "dhis2_processed" to indicate that the form has been sent
  to DHIS2 as an event

The application needs a lookup table named `dhis2_org_unit` (or as specified
in custom.dhis2.const.ORG_UNIT_FIXTURES, but note that this value applies
system-wide) to store DHIS2 organisation units. The lookup table must have
three fields:

1. id
2. name
3. parent_id


.. _setting_up_dhis2:
Setting up DHIS2
^^^^^^^^^^^^^^^^

DHIS2 tracked entities:

* Child

Tracked entity attributes of Child:

* height
* weight
* BMI
* age at time of visit
* CCHQ Case ID: Used to refer to the corresponding CommCareHQ case. This
  will be populated with a hexadecimal UUID.

DHIS2 needs the following two projects for CommCareHQ child_gmp cases /
DHIS2 Child tracked entity instances to be enrolled in:

1. "Paediatric Nutrition Assessment"
2. "Underlying Risk Assessment"


Development
-----------

A DHIS2 instance for development can be installed and run very easily.
Download the `DHIS 2 Live package`_, unzip it, and run the executable. It will
start the service locally on port 8082, and open a browser tab to the login
screen.

Credentials are "admin" / "district".

Create some organisation units, a tracked entity, some attributes and some
projects according to :ref:`setting_up_dhis2`.

You can get to the API at http://localhost:8082/api/resources.json


.. _DHIS 2 Live package: https://www.dhis2.org/downloads
