# Proof-of-concept endpoints to see how ProjectDB works as a case search backend.
from django.utils.translation import gettext as _

from sqlalchemy import Text, bindparam, text

from corehq.apps.case_search.exceptions import CaseSearchUserError
from corehq.form_processor.models import CommCareCase

from .table_ddl import CaseTable, DomainSchema, get_project_db_engine

RESULT_LIMIT = 1500


def static_endpoint(query_fn):
    """Run ``query_fn(table, criteria)`` against the project DB and returns CommCareCases."""
    def _run(helper, config):
        domain = helper.domain
        case_type = config.case_types[0]
        table = CaseTable(domain, case_type).reflect()
        if table is None:
            raise CaseSearchUserError(_("No ProjectDB table for case type '{}'").format(case_type))
        query = query_fn(table, config.criteria)

        engine = get_project_db_engine()
        with engine.begin() as conn:
            DomainSchema(domain).set_local_search_path(conn)
            rows = conn.execute(query).fetchall()

        return _rows_to_cases(rows, table, domain, case_type)

    return _run


def _rows_to_cases(rows, table, domain, case_type):
    prop_columns = [col for col in table.columns if col.name.startswith('prop__')]
    return [
        CommCareCase(
            case_id=row['case_id'],
            domain=domain,
            type=case_type,
            name=row['case_name'],
            owner_id=row['owner_id'],
            opened_on=row['opened_on'],
            closed_on=row['closed_on'],
            closed=row['closed'],
            modified_on=row['modified_on'],
            server_modified_on=row['server_modified_on'],
            external_id=row['external_id'],
            # The column comment has the raw, untruncated property name
            case_json={col.comment: row[col.name] for col in prop_columns
                       if row[col.name]},
        ) for row in rows
    ]


@static_endpoint
def all_cases_of_type(table, criteria):
    query = table.select().limit(RESULT_LIMIT)

    for criterion in criteria:
        column = (table.columns.get(criterion.key, None)
                  or table.columns.get(f'prop__{criterion.key}', None))
        if not column:
            raise CaseSearchUserError(_("Unknown column '{}'").format(criterion.key))
        if not isinstance(column.type, Text):
            raise CaseSearchUserError(_("Column '{}' is not a text column").format(criterion.key))
        query = query.where(column == criterion.value)

    return query


@static_endpoint
def incoming_referrals(table, criteria):
    """Referrals arriving at the user's clinics (see incoming-referrals.sql)."""
    values = {c.key: c.value for c in criteria}
    params = {name: values.get(name) for name in INCOMING_REFERRALS_PARAMS}
    # These bind against array/IN constructs and must be lists
    params['user_clinic_ids'] = _as_list(params['user_clinic_ids']) or []
    params['statuses'] = _as_list(params['statuses'])
    # bindparams() binds values into a new clause, leaving the module-level
    # statement untouched for reuse
    return INCOMING_REFERRALS_SQL.bindparams(**params)


INCOMING_REFERRALS_PARAMS = [
    'user_clinic_ids', 'statuses', 'received_from', 'received_to',
    'gender', 'age', 'type_of_care', 'client_id',
]

INCOMING_REFERRALS_SQL = text(f'''
    SELECT ref.*
    FROM referral ref
    WHERE
        ref.prop__send_to_destination_clinic <> 'no'
        AND ref.prop__destination_clinic_case_id IN :user_clinic_ids
        AND (:statuses::text[] IS NULL OR ref.prop__current_status = ANY(:statuses))
        AND (:received_from::date IS NULL OR ref.opened_on >= :received_from)
        AND (:received_to::date IS NULL
             OR ref.opened_on < (:received_to::date + INTERVAL '1 day'))
        AND (:gender::text IS NULL OR ref.prop__client_gender_display = :gender)
        AND (:age::text IS NULL OR ref.prop__client_age = :age)
        AND (:type_of_care::text IS NULL
             OR ref.prop__client_type_of_care_display = :type_of_care)
        AND (:client_id::text IS NULL OR ref.prop__client_id = :client_id)
    ORDER BY ref.opened_on DESC
    LIMIT {RESULT_LIMIT}
''').bindparams(bindparam('user_clinic_ids', expanding=True))


@static_endpoint
def search_and_admit(table, criteria):
    """Central-registry client lookup for admission (see search-and-admit.sql)."""
    values = {c.key: c.value for c in criteria}
    params = {name: values.get(name) for name in SEARCH_AND_ADMIT_PARAMS}
    return SEARCH_AND_ADMIT_SQL.bindparams(**params)


SEARCH_AND_ADMIT_PARAMS = [
    'include_nonconsented', 'middle_name', 'ssn', 'medicaid_id',
    'client_case_id', 'dob', 'first_name', 'last_name',
]

SEARCH_AND_ADMIT_SQL = text(f'''
    SELECT client.*
    FROM client
    WHERE
        client.prop__central_registry = 'yes'
        AND client.prop__current_status <> 'pending'
        AND (:include_nonconsented = 'yes' OR client.prop__consent_collected = 'yes')
        AND (:middle_name::text IS NULL
             OR client.prop__middle_name ILIKE :middle_name)
        AND (:ssn::text IS NULL
             OR client.prop__social_security_number = :ssn
             OR EXISTS (SELECT 1 FROM alias a
                        WHERE a.parent_id = client.case_id
                          AND a.closed = false
                          AND a.prop__social_security_number = :ssn))
        AND (:medicaid_id::text IS NULL
             OR client.prop__medicaid_id = :medicaid_id
             OR EXISTS (SELECT 1 FROM alias a
                        WHERE a.parent_id = client.case_id
                          AND a.closed = false
                          AND a.prop__medicaid_id = :medicaid_id))
        AND (:client_case_id::text IS NULL
             OR client.case_id = :client_case_id)
        AND (:dob::text IS NULL
             OR client.prop__dob = :dob
             OR EXISTS (SELECT 1 FROM alias a
                        WHERE a.parent_id = client.case_id
                          AND a.closed = false
                          AND a.prop__dob = :dob))
        AND (:first_name::text IS NULL
             OR similarity(client.prop__first_name, :first_name) >= 0.3
             OR dmetaphone(client.prop__first_name) = dmetaphone(:first_name)
             OR EXISTS (SELECT 1 FROM alias a
                        WHERE a.parent_id = client.case_id
                          AND a.closed = false
                          AND (similarity(a.prop__first_name, :first_name) >= 0.3
                               OR dmetaphone(a.prop__first_name) = dmetaphone(:first_name))))
        AND (:last_name::text IS NULL
             OR similarity(client.prop__last_name, :last_name) >= 0.3
             OR dmetaphone(client.prop__last_name) = dmetaphone(:last_name)
             OR EXISTS (SELECT 1 FROM alias a
                        WHERE a.parent_id = client.case_id
                          AND a.closed = false
                          AND (similarity(a.prop__last_name, :last_name) >= 0.3
                               OR dmetaphone(a.prop__last_name) = dmetaphone(:last_name))))
    ORDER BY client.prop__last_name, client.prop__first_name
    LIMIT {RESULT_LIMIT}
''')


@static_endpoint
def search_beds(table, criteria):
    """Bed/capacity search across clinics (see search-beds.sql)."""
    values = {c.key: c.value for c in criteria}
    params = {name: values.get(name) for name in SEARCH_BEDS_PARAMS}
    # These bind against text[] array operators and must be lists
    params['counties'] = _as_list(params['counties'])
    params['populations'] = _as_list(params['populations'])
    return SEARCH_BEDS_SQL.bindparams(**params)


SEARCH_BEDS_PARAMS = [
    'category', 'gender', 'community', 'insurance', 'language',
    'accessibility', 'involuntary', 'justice', 'accepts_referrals',
    'counties', 'lat', 'lon', 'radius_m', 'only_open_beds', 'populations',
]

SEARCH_BEDS_SQL = text(f'''
    SELECT cap.*
    FROM capacity cap
    JOIN clinic
        ON cap.prop__clinic_case_id = clinic.case_id
        AND clinic.closed = false
        AND clinic.prop__exclude_from_ccs <> 'yes'
        AND (clinic.prop__site_closed <> 'yes'
             OR NULLIF(clinic.prop__site_closed_date, '')::date >= CURRENT_DATE - INTERVAL '30 day')
        AND (
            (:category = 'both'
             AND clinic.prop__mental_health_settings <> ''
             AND clinic.prop__residential_services <> '')
         OR (:category = 'mental_health' AND clinic.prop__mental_health_settings <> '')
         OR (:category = 'substance_use' AND clinic.prop__residential_services <> '')
         OR (:category IS NULL
             AND (clinic.prop__mental_health_settings <> ''
                  OR clinic.prop__residential_services <> ''))
        )
        AND (:gender IS NULL
             OR clinic.prop__gender_served LIKE '%' || :gender || '%'
             OR clinic.prop__gender_served LIKE '%no_gender_restrictions%')
        AND (:community IS NULL
             OR clinic.prop__community_served LIKE '%' || :community || '%')
        AND (:insurance IS NULL
             OR clinic.prop__insurance LIKE '%' || :insurance || '%')
        AND (:language IS NULL
             OR clinic.prop__language_services LIKE '%' || :language || '%')
        AND (:accessibility IS NULL
             OR clinic.prop__accessibility LIKE '%' || :accessibility || '%')
        AND (:involuntary IS NULL
             OR clinic.prop__mental_health_settings LIKE '%72_hour_treatment_and_evaluation%')
        AND (:justice IS NULL
             OR clinic.prop__community_served LIKE '%referred_from_court-judicial_system%')
        AND (:accepts_referrals IS NULL
             OR clinic.prop__accepts_commcare_referrals = 'yes')
        AND (:counties::text[] IS NULL
             OR clinic.select_prop__county && :counties::text[])
        AND (:lat::float8 IS NULL OR :lon::float8 IS NULL OR :radius_m::float8 IS NULL
             OR earth_distance(clinic.gps_prop__map_coordinates,
                               ll_to_earth(:lat, :lon)) <= :radius_m)
    WHERE
        cap.prop__current_status <> 'closed'
        AND (:only_open_beds IS NULL OR cap.number_prop__open_beds > 0)
        AND (:populations::text[] IS NULL
             OR cap.select_prop__unit_population_served @> :populations::text[])
    ORDER BY clinic.prop__case_name ASC
    LIMIT {RESULT_LIMIT}
''')


def _as_list(value):
    if value is None:
        return None
    return value if isinstance(value, list) else [value]


STATIC_ENDPOINTS = {
    # name: function
    # These have to be ints, so picking an arbitrarily high number for now
    1_000_000: ('All Cases Of Type', all_cases_of_type),
    1_000_001: ('Incoming Referrals', incoming_referrals),
    1_000_002: ('Search and Admit', search_and_admit),
    1_000_003: ('Search Beds', search_beds),
}
