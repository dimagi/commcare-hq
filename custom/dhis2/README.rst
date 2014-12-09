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

