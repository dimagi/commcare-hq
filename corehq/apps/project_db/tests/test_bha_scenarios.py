"""Test data setup for BHA case search scenarios.

Creates project DB tables and populates them with representative data
from the BHA (Behavioral Health Administration) use cases documented in
``scratchpad/case-search-endpoints/sample_table_sql.md``.

Case types: client, alias, service, clinic, unit, capacity, referral.

Queries are not implemented yet — these tests verify that representative
data populates correctly and will serve as the foundation for query tests.
"""
from django.test import TestCase

import sqlalchemy

from corehq.apps.data_dictionary.tests.utils import setup_data_dictionary
from corehq.apps.project_db.populate import upsert_case
from corehq.apps.project_db.schema import (
    build_tables_for_domain,
    create_tables,
    get_project_db_engine,
)

DOMAIN = 'test-bha-scenarios'


# -- Data dictionary definitions --

CASE_TYPE_DEFINITIONS = {
    'client': [
        ('first_name', 'plain'),
        ('middle_name', 'plain'),
        ('last_name', 'plain'),
        ('dob', 'date'),
        ('social_security_number', 'plain'),
        ('medicaid_id', 'plain'),
        ('central_registry', 'plain'),
        ('current_status', 'plain'),
        ('consent_collected', 'plain'),
        ('age', 'number'),
        ('age_range', 'plain'),
        ('gender', 'plain'),
        ('type_of_care', 'plain'),
        ('client_id', 'plain'),
        ('closed', 'plain'),
        ('case_type', 'plain'),
    ],
    'alias': [
        ('first_name', 'plain'),
        ('last_name', 'plain'),
        ('dob', 'date'),
        ('medicaid_id', 'plain'),
        ('social_security_number', 'plain'),
    ],
    'service': [
        ('admission_date', 'date'),
        ('discharge_date', 'date'),
        ('clinic_case_id', 'plain'),
        ('current_status', 'plain'),
    ],
    'clinic': [
        ('display_name', 'plain'),
        ('insurance', 'plain'),
        ('phone_referrals', 'plain'),
        ('map_coordinates', 'plain'),
        ('address_full', 'plain'),
        ('mental_health_settings', 'plain'),
        ('residential_services', 'plain'),
        ('language_services', 'plain'),
        ('accessibility', 'plain'),
        ('exclude_from_ccs', 'plain'),
        ('site_closed', 'plain'),
        ('site_closed_date', 'date'),
    ],
    'unit': [],  # case_name is a fixed column, no dynamic properties needed
    'capacity': [
        ('unit_case_ids', 'plain'),
        ('age_served', 'plain'),
        ('gender_served', 'plain'),
        ('open_beds', 'number'),
        ('date_opened', 'date'),
        ('current_status', 'plain'),
        ('community_served', 'plain'),
        ('view_more_info_smartlink_bed_tracker', 'plain'),
    ],
    'referral': [
        ('referring_clinic_case_id', 'plain'),
        ('destination_clinic_case_id', 'plain'),
        ('client_type_of_care_display', 'plain'),
        ('client_reason_for_seeking_care', 'plain'),
        ('client_level_of_care_needed', 'plain'),
        ('referral_date', 'date'),
        ('referral_ts', 'plain'),
        ('current_status', 'plain'),
        ('referrer_name', 'plain'),
        ('send_to_destination_clinic', 'plain'),
        ('date_opened', 'date'),
    ],
}


# -- Case data --
# Keys use the ``prop.<name>`` namespace for dynamic properties.
# ``parent_id`` is a fixed column populated via case indices in production,
# but here we set it directly since we're bypassing CommCareCase objects.

CLINICS = [
    {
        'case_id': 'clinic-001',
        'owner_id': 'system',
        'case_name': 'Sunrise Recovery Center',
        'prop.display_name': 'Sunrise Recovery Center',
        'prop.insurance': 'medicaid medicare private',
        'prop.phone_referrals': '555-0101',
        'prop.map_coordinates': '39.2904 -76.6122',
        'prop.address_full': '100 Recovery Way, Baltimore, MD 21201',
        'prop.mental_health_settings': 'outpatient 72_hour_treatment_and_evaluation',
        'prop.residential_services': 'residential_detox',
        'prop.language_services': 'spanish interpreter',
        'prop.accessibility': 'wheelchair_accessible',
        'prop.exclude_from_ccs': 'no',
        'prop.site_closed': 'no',
    },
    {
        'case_id': 'clinic-002',
        'owner_id': 'system',
        'case_name': 'Harbor Health Clinic',
        'prop.display_name': 'Harbor Health Clinic',
        'prop.insurance': 'medicaid',
        'prop.phone_referrals': '555-0102',
        'prop.map_coordinates': '39.2800 -76.6000',
        'prop.address_full': '200 Harbor Blvd, Baltimore, MD 21230',
        'prop.mental_health_settings': 'outpatient',
        'prop.residential_services': '',
        'prop.language_services': 'spanish',
        'prop.accessibility': '',
        'prop.exclude_from_ccs': 'no',
        'prop.site_closed': 'no',
    },
    {
        'case_id': 'clinic-003',
        'owner_id': 'system',
        'case_name': 'Westside Wellness (Closed)',
        'prop.display_name': 'Westside Wellness',
        'prop.insurance': 'medicaid private',
        'prop.phone_referrals': '555-0103',
        'prop.map_coordinates': '39.3000 -76.6500',
        'prop.address_full': '300 West St, Baltimore, MD 21223',
        'prop.mental_health_settings': '',
        'prop.residential_services': 'residential_rehab',
        'prop.language_services': '',
        'prop.accessibility': 'wheelchair_accessible',
        'prop.exclude_from_ccs': 'no',
        'prop.site_closed': 'yes',
        'prop.site_closed_date': '2026-02-15',
    },
]

UNITS = [
    {
        'case_id': 'unit-001',
        'owner_id': 'system',
        'case_name': 'Adult Detox Ward',
        'parent_id': 'clinic-001',
    },
    {
        'case_id': 'unit-002',
        'owner_id': 'system',
        'case_name': 'Adolescent Wing',
        'parent_id': 'clinic-001',
    },
    {
        'case_id': 'unit-003',
        'owner_id': 'system',
        'case_name': 'Outpatient Suite A',
        'parent_id': 'clinic-002',
    },
    {
        'case_id': 'unit-004',
        'owner_id': 'system',
        'case_name': 'Outpatient Suite B',
        'parent_id': 'clinic-002',
    },
]

CAPACITIES = [
    {
        'case_id': 'cap-001',
        'owner_id': 'system',
        'parent_id': 'clinic-001',
        'prop.unit_case_ids': 'unit-001',
        'prop.age_served': 'adults',
        'prop.gender_served': 'male',
        'prop.open_beds': '3',
        'prop.date_opened': '2024-06-01',
        'prop.current_status': 'active',
        'prop.community_served': 'general veterans',
        'prop.view_more_info_smartlink_bed_tracker': 'https://example.com/beds/cap-001',
    },
    {
        'case_id': 'cap-002',
        'owner_id': 'system',
        'parent_id': 'clinic-001',
        'prop.unit_case_ids': 'unit-001',
        'prop.age_served': 'adults',
        'prop.gender_served': 'female',
        'prop.open_beds': '0',
        'prop.date_opened': '2024-06-01',
        'prop.current_status': 'active',
        'prop.community_served': 'general',
        'prop.view_more_info_smartlink_bed_tracker': 'https://example.com/beds/cap-002',
    },
    {
        'case_id': 'cap-003',
        'owner_id': 'system',
        'parent_id': 'clinic-001',
        'prop.unit_case_ids': 'unit-002',
        'prop.age_served': 'adolescents',
        'prop.gender_served': 'no_gender_restrictions',
        'prop.open_beds': '5',
        'prop.date_opened': '2024-09-15',
        'prop.current_status': 'active',
        'prop.community_served': 'general',
        'prop.view_more_info_smartlink_bed_tracker': 'https://example.com/beds/cap-003',
    },
    {
        'case_id': 'cap-004',
        'owner_id': 'system',
        'parent_id': 'clinic-002',
        'prop.unit_case_ids': 'unit-003',
        'prop.age_served': 'adults',
        'prop.gender_served': 'no_gender_restrictions',
        'prop.open_beds': '2',
        'prop.date_opened': '2025-01-10',
        'prop.current_status': 'active',
        'prop.community_served': 'general referred_from_court-judicial_system',
        'prop.view_more_info_smartlink_bed_tracker': 'https://example.com/beds/cap-004',
    },
    {
        'case_id': 'cap-005',
        'owner_id': 'system',
        'parent_id': 'clinic-002',
        'prop.unit_case_ids': 'unit-004',
        'prop.age_served': 'adults',
        'prop.gender_served': 'male',
        'prop.open_beds': '1',
        'prop.date_opened': '2020-01-01',  # sentinel null value
        'prop.current_status': 'active',
        'prop.community_served': 'veterans',
        'prop.view_more_info_smartlink_bed_tracker': 'https://example.com/beds/cap-005',
    },
    {
        'case_id': 'cap-006',
        'owner_id': 'system',
        'parent_id': 'clinic-001',
        'prop.unit_case_ids': 'unit-001',
        'prop.age_served': 'adults',
        'prop.gender_served': 'male',
        'prop.open_beds': '0',
        'prop.date_opened': '2024-06-01',
        'prop.current_status': 'closed',
        'prop.community_served': 'general',
        'prop.view_more_info_smartlink_bed_tracker': '',
    },
]

CLIENTS = [
    {   # Active registry client with aliases and services
        'case_id': 'client-001',
        'owner_id': 'owner-1',
        'case_name': 'Maria Garcia',
        'prop.first_name': 'Maria',
        'prop.middle_name': 'Elena',
        'prop.last_name': 'Garcia',
        'prop.dob': '1985-03-15',
        'prop.social_security_number': '111-22-3333',
        'prop.medicaid_id': 'MED-001',
        'prop.central_registry': 'yes',
        'prop.current_status': 'active',
        'prop.consent_collected': 'yes',
        'prop.age': '41',
        'prop.age_range': 'adults',
        'prop.gender': 'female',
        'prop.type_of_care': 'substance_use',
        'prop.client_id': 'CL000001',
        'prop.closed': 'no',
        'prop.case_type': 'client',
    },
    {   # Active registry client, no aliases
        'case_id': 'client-002',
        'owner_id': 'owner-1',
        'case_name': 'James Wilson',
        'prop.first_name': 'James',
        'prop.middle_name': 'Robert',
        'prop.last_name': 'Wilson',
        'prop.dob': '1990-07-22',
        'prop.social_security_number': '444-55-6666',
        'prop.medicaid_id': 'MED-002',
        'prop.central_registry': 'yes',
        'prop.current_status': 'active',
        'prop.consent_collected': 'yes',
        'prop.age': '35',
        'prop.age_range': 'adults',
        'prop.gender': 'male',
        'prop.type_of_care': 'mental_health',
        'prop.client_id': 'CL000002',
        'prop.closed': 'no',
        'prop.case_type': 'client',
    },
    {   # Pending client (should be excluded from Search and Admit)
        'case_id': 'client-003',
        'owner_id': 'owner-2',
        'case_name': 'Sarah Johnson',
        'prop.first_name': 'Sarah',
        'prop.middle_name': '',
        'prop.last_name': 'Johnson',
        'prop.dob': '1978-11-05',
        'prop.social_security_number': '777-88-9999',
        'prop.medicaid_id': 'MED-003',
        'prop.central_registry': 'yes',
        'prop.current_status': 'pending',
        'prop.consent_collected': 'no',
        'prop.age': '47',
        'prop.age_range': 'adults',
        'prop.gender': 'female',
        'prop.type_of_care': 'substance_use',
        'prop.client_id': 'CL000003',
        'prop.closed': 'no',
        'prop.case_type': 'client',
    },
    {   # Non-registry client (should be excluded from registry searches)
        'case_id': 'client-004',
        'owner_id': 'owner-2',
        'case_name': 'David Kim',
        'prop.first_name': 'David',
        'prop.middle_name': 'Lee',
        'prop.last_name': 'Kim',
        'prop.dob': '2005-01-30',
        'prop.social_security_number': '222-33-4444',
        'prop.medicaid_id': '',
        'prop.central_registry': 'no',
        'prop.current_status': 'active',
        'prop.consent_collected': 'yes',
        'prop.age': '21',
        'prop.age_range': 'adults',
        'prop.gender': 'male',
        'prop.type_of_care': 'mental_health',
        'prop.client_id': 'CL000004',
        'prop.closed': 'no',
        'prop.case_type': 'client',
    },
    {   # Closed client (for referral filtering)
        'case_id': 'client-005',
        'owner_id': 'owner-1',
        'case_name': 'Lisa Brown',
        'prop.first_name': 'Lisa',
        'prop.middle_name': 'Marie',
        'prop.last_name': 'Brown',
        'prop.dob': '1995-09-12',
        'prop.social_security_number': '555-66-7777',
        'prop.medicaid_id': 'MED-005',
        'prop.central_registry': 'no',
        'prop.current_status': 'active',
        'prop.consent_collected': 'yes',
        'prop.age': '30',
        'prop.age_range': 'adults',
        'prop.gender': 'female',
        'prop.type_of_care': 'substance_use',
        'prop.client_id': 'CL000005',
        'prop.closed': 'yes',
        'prop.case_type': 'client',
    },
]

ALIASES = [
    {   # Maria Garcia's maiden name
        'case_id': 'alias-001',
        'owner_id': 'owner-1',
        'parent_id': 'client-001',
        'prop.first_name': 'Maria',
        'prop.last_name': 'Rodriguez',
        'prop.dob': '1985-03-15',
        'prop.medicaid_id': '',
        'prop.social_security_number': '111-22-3333',
    },
    {   # Maria Garcia's nickname
        'case_id': 'alias-002',
        'owner_id': 'owner-1',
        'parent_id': 'client-001',
        'prop.first_name': 'Mari',
        'prop.last_name': 'Garcia',
        'prop.dob': '1985-03-15',
        'prop.medicaid_id': 'MED-001',
        'prop.social_security_number': '',
    },
    {   # James Wilson's former name
        'case_id': 'alias-003',
        'owner_id': 'owner-1',
        'parent_id': 'client-002',
        'prop.first_name': 'Jimmy',
        'prop.last_name': 'Wilson',
        'prop.dob': '1990-07-22',
        'prop.medicaid_id': 'MED-002-OLD',
        'prop.social_security_number': '444-55-6666',
    },
    {   # James Wilson with transposed DOB digits
        'case_id': 'alias-004',
        'owner_id': 'owner-1',
        'parent_id': 'client-002',
        'prop.first_name': 'James',
        'prop.last_name': 'Wilson',
        'prop.dob': '1990-07-22',
        'prop.medicaid_id': '',
        'prop.social_security_number': '444-55-6666',
    },
]

SERVICES = [
    {   # Maria at clinic-001, active
        'case_id': 'svc-001',
        'owner_id': 'owner-1',
        'parent_id': 'client-001',
        'prop.admission_date': '2025-06-01',
        'prop.discharge_date': '',
        'prop.clinic_case_id': 'clinic-001',
        'prop.current_status': 'active',
    },
    {   # Maria at clinic-002, discharged
        'case_id': 'svc-002',
        'owner_id': 'owner-1',
        'parent_id': 'client-001',
        'prop.admission_date': '2024-01-15',
        'prop.discharge_date': '2024-09-30',
        'prop.clinic_case_id': 'clinic-002',
        'prop.current_status': 'discharged',
    },
    {   # James at clinic-001, active
        'case_id': 'svc-003',
        'owner_id': 'owner-1',
        'parent_id': 'client-002',
        'prop.admission_date': '2025-09-01',
        'prop.discharge_date': '',
        'prop.clinic_case_id': 'clinic-001',
        'prop.current_status': 'active',
    },
    {   # David at clinic-002, active (non-registry client)
        'case_id': 'svc-004',
        'owner_id': 'owner-2',
        'parent_id': 'client-004',
        'prop.admission_date': '2026-01-10',
        'prop.discharge_date': '',
        'prop.clinic_case_id': 'clinic-002',
        'prop.current_status': 'active',
    },
]

REFERRALS = [
    {   # Open referral to clinic-001
        'case_id': 'ref-001',
        'owner_id': 'owner-1',
        'parent_id': 'client-001',
        'prop.referring_clinic_case_id': 'clinic-002',
        'prop.destination_clinic_case_id': 'clinic-001',
        'prop.client_type_of_care_display': 'Substance Use',
        'prop.client_reason_for_seeking_care': 'Relapse after discharge',
        'prop.client_level_of_care_needed': 'residential',
        'prop.referral_date': '2025-05-20',
        'prop.referral_ts': '2025-05-20T14:30:00Z',
        'prop.current_status': 'open',
        'prop.referrer_name': 'Dr. Chen',
        'prop.send_to_destination_clinic': 'yes',
        'prop.date_opened': '2025-05-20',
    },
    {   # Info requested referral to clinic-001
        'case_id': 'ref-002',
        'owner_id': 'owner-1',
        'parent_id': 'client-002',
        'prop.referring_clinic_case_id': 'clinic-002',
        'prop.destination_clinic_case_id': 'clinic-001',
        'prop.client_type_of_care_display': 'Mental Health',
        'prop.client_reason_for_seeking_care': 'Anxiety and depression',
        'prop.client_level_of_care_needed': 'outpatient',
        'prop.referral_date': '2025-08-10',
        'prop.referral_ts': '2025-08-10T09:15:00Z',
        'prop.current_status': 'info_requested',
        'prop.referrer_name': 'Dr. Patel',
        'prop.send_to_destination_clinic': 'yes',
        'prop.date_opened': '2025-08-10',
    },
    {   # Accepted referral to clinic-002 (should be excluded from default filter)
        'case_id': 'ref-003',
        'owner_id': 'owner-2',
        'parent_id': 'client-004',
        'prop.referring_clinic_case_id': 'clinic-001',
        'prop.destination_clinic_case_id': 'clinic-002',
        'prop.client_type_of_care_display': 'Mental Health',
        'prop.client_reason_for_seeking_care': 'Initial evaluation',
        'prop.client_level_of_care_needed': 'outpatient',
        'prop.referral_date': '2025-12-01',
        'prop.referral_ts': '2025-12-01T11:00:00Z',
        'prop.current_status': 'accepted',
        'prop.referrer_name': 'Dr. Adams',
        'prop.send_to_destination_clinic': 'yes',
        'prop.date_opened': '2025-12-01',
    },
    {   # Off-platform referral (send_to_destination_clinic = 'no')
        'case_id': 'ref-004',
        'owner_id': 'owner-1',
        'parent_id': 'client-005',
        'prop.referring_clinic_case_id': 'clinic-001',
        'prop.destination_clinic_case_id': 'clinic-003',
        'prop.client_type_of_care_display': 'Substance Use',
        'prop.client_reason_for_seeking_care': 'Transfer request',
        'prop.client_level_of_care_needed': 'residential',
        'prop.referral_date': '2026-01-05',
        'prop.referral_ts': '2026-01-05T16:45:00Z',
        'prop.current_status': 'open',
        'prop.referrer_name': 'Case Manager Jones',
        'prop.send_to_destination_clinic': 'no',
        'prop.date_opened': '2026-01-05',
    },
]


class TestBHAScenarios(TestCase):
    """Populate project DB with data similar to that seen in a real project"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = get_project_db_engine()
        for case_type, prop_list in CASE_TYPE_DEFINITIONS.items():
            setup_data_dictionary(DOMAIN, case_type, prop_list=prop_list)

        metadata = sqlalchemy.MetaData()
        cls.tables = build_tables_for_domain(metadata, DOMAIN)
        create_tables(cls.engine, metadata)

        for case_type, cases in [
            ('clinic', CLINICS),
            ('unit', UNITS),
            ('capacity', CAPACITIES),
            ('client', CLIENTS),
            ('alias', ALIASES),
            ('service', SERVICES),
            ('referral', REFERRALS),
        ]:
            table = cls.tables[case_type]
            with cls.engine.begin() as conn:
                for case_data in cases:
                    upsert_case(conn, table, case_data)

    @classmethod
    def tearDownClass(cls):
        schemas = {t.schema for t in cls.tables.values()}
        with cls.engine.begin() as conn:
            for schema in schemas:
                conn.execute(sqlalchemy.text(
                    f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'
                ))
        super().tearDownClass()

    def _select_all(self, case_type):
        table = self.tables[case_type]
        with self.engine.begin() as conn:
            rows = conn.execute(table.select()).fetchall()
        return [dict(row) for row in rows]

    def _select_by_id(self, case_type, case_id):
        table = self.tables[case_type]
        with self.engine.begin() as conn:
            row = conn.execute(
                table.select().where(table.c.case_id == case_id)
            ).fetchone()
        return dict(row) if row else None

    def _table(self, case_type):
        return self.tables[case_type].name

    def _execute(self, sql):
        from corehq.apps.project_db.schema import get_schema_name
        with self.engine.begin() as conn:
            schema = get_schema_name(DOMAIN)
            conn.execute(sqlalchemy.text(
                f'SET LOCAL search_path TO "{schema}"'
            ))
            return [dict(row) for row in conn.execute(sqlalchemy.text(sql))]

    def test_search_and_admit(self):
        """Search and Admit: find clients in the central registry.

        Fetch all clients who are enrolled in the central registry and
        whose status is not "pending", searching by first name across
        both client and alias records.

        Alias matching uses an EXISTS subquery rather than a JOIN, so
        each client appears exactly once regardless of how many aliases
        they have.

        The base filters are:
        - The client must be in the central registry
        - The client must not have a "pending" status
        - The first name must match on either the client or an alias
        """
        rows = self._execute(f"""
            SELECT
                c.case_name AS client_name
            FROM "{self._table('client')}" c
            WHERE c.prop__central_registry = 'yes'
              AND c.prop__current_status != 'pending'
              AND (
                c.prop__first_name = 'Maria'
                OR EXISTS (
                    SELECT 1 FROM "{self._table('alias')}" a
                    WHERE a.parent_id = c.case_id
                      AND a.prop__first_name = 'Maria'
                )
              )
            ORDER BY c.case_name
        """)

        # Maria Garcia is the only match — one row, no duplicates.
        assert [r['client_name'] for r in rows] == ['Maria Garcia']

    def test_search_my_clients(self):
        """Search My Clients: find clients at a specific clinic.

        Fetch clients who have a service episode at the user's clinic
        and are enrolled in the central registry, along with any alias
        records. Only clients with at least one service record at the
        clinic are included (INNER JOIN on service), but clients without
        aliases are still included (LEFT JOIN on alias).

        The base filters are:
        - The service record must belong to the user's clinic
        - The client must be in the central registry
        """
        rows = self._execute(f"""
            SELECT DISTINCT
                c.case_name            AS client_name,
                s.prop__current_status AS service_status,
                s.prop__admission_date AS admission_date
            FROM "{self._table('client')}" c
            LEFT JOIN "{self._table('alias')}" a ON c.case_id = a.parent_id
            INNER JOIN "{self._table('service')}" s ON c.case_id = s.parent_id
            WHERE s.prop__clinic_case_id = 'clinic-001'
              AND c.prop__central_registry = 'yes'
            ORDER BY c.case_name
        """)

        # Maria and James both have service episodes at clinic-001 and
        # are in the registry. David has a service at clinic-002 only.
        # Sarah has no services. Lisa has no services.
        self.assertCountEqual(
            [r['client_name'] for r in rows],
            ['Maria Garcia', 'James Wilson'],
        )

    def test_search_beds(self):
        """Search Beds: find available capacity at clinics.

        Fetch capacity records (representing bed availability at a
        clinic) joined to their parent clinic for filtering and display.
        Only active capacity records at clinics that are open and not
        excluded from the directory are returned.

        Note: the unit JOIN is omitted here. In production, units are
        linked to capacity records via an array membership check
        (a capacity record stores a list of unit IDs as text), which
        does not map to a simple FK JOIN.

        The base filters are:
        - The capacity record must not be closed
        - The clinic must not be excluded from the directory
        - The clinic must not be closed
        """
        rows = self._execute(f"""
            SELECT
                cap.case_id             AS capacity_case_id,
                c.prop__display_name    AS clinic_name,
                cap.prop__age_served    AS age_served,
                cap.prop__gender_served AS gender_served,
                cap.prop__open_beds     AS open_beds
            FROM "{self._table('capacity')}" cap
            LEFT JOIN "{self._table('clinic')}" c ON cap.parent_id = c.case_id
            WHERE cap.prop__current_status != 'closed'
              AND c.prop__exclude_from_ccs != 'yes'
              AND c.prop__site_closed != 'yes'
            ORDER BY cap.case_id
        """)

        # Capacity cases cap-001 through cap-005 are active at open clinics.
        # cap-006 is closed (status = 'closed'), so it's excluded.
        # No capacities exist at Westside Wellness (Closed)
        assert len(rows) == 5
        self.assertCountEqual(
            [r['clinic_name'] for r in rows],
            ['Sunrise Recovery Center'] * 3 + ['Harbor Health Clinic'] * 2,
        )

    def test_incoming_referrals(self):
        """Incoming Referrals: find referrals sent to the user's clinic.

        Fetch referral records destined for a specific clinic, joined to
        the client record (for demographics) and the referring clinic
        (for display). Only on-platform referrals that are actively
        awaiting a decision are shown by default.

        Referrals without a matched client are still included (LEFT JOIN
        on client). Only referrals with a known referring clinic are
        included (INNER JOIN on clinic).

        The base filters are:
        - The referral must be an on-platform referral (not off-platform)
        - The referral must be destined for the user's clinic
        - The referral status must be "open" or "info_requested"
        """
        rows = self._execute(f"""
            SELECT
                c.case_name                        AS client_name,
                r.prop__current_status             AS referral_status,
                r.prop__referrer_name              AS referrer_name,
                clinic.case_name                   AS referring_clinic_name
            FROM "{self._table('referral')}" r
            LEFT JOIN "{self._table('client')}" c ON r.parent_id = c.case_id
            INNER JOIN "{self._table('clinic')}" clinic
                ON r.prop__referring_clinic_case_id = clinic.case_id
            WHERE r.prop__send_to_destination_clinic != 'no'
              AND r.prop__destination_clinic_case_id = 'clinic-001'
              AND r.prop__current_status IN ('open', 'info_requested')
            ORDER BY c.case_name
        """)

        # Maria's referral (open) and James's referral (info_requested)
        # are both destined for clinic-001. David's referral goes to
        # clinic-002. Lisa's referral is off-platform.
        self.assertCountEqual(
            [r['client_name'] for r in rows],
            ['Maria Garcia', 'James Wilson'],
        )

        # Verify referring clinic is joined correctly
        maria_row = next(r for r in rows if r['client_name'] == 'Maria Garcia')
        assert maria_row['referring_clinic_name'] == 'Harbor Health Clinic'
        james_row = next(r for r in rows if r['client_name'] == 'James Wilson')
        assert james_row['referrer_name'] == 'Dr. Patel'
