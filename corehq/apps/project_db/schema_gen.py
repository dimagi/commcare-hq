from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.project_db.schema import build_table_for_case_type


def build_tables_for_domain(metadata, domain):
    """Build SQLAlchemy Tables for all active case types in a domain.

    Reads the data dictionary (CaseType and CaseProperty models) and
    produces a corresponding SQLAlchemy Table for each non-deprecated
    case type.

    :param metadata: SQLAlchemy MetaData instance
    :param domain: CommCare project domain
    :returns: dict mapping case type name to SQLAlchemy Table
    """
    case_types = CaseType.objects.filter(
        domain=domain, is_deprecated=False,
    )

    tables = {}
    for case_type in case_types:
        properties = list(
            CaseProperty.objects.filter(
                case_type=case_type, deprecated=False,
            ).values_list('name', 'data_type')
        )
        tables[case_type.name] = build_table_for_case_type(
            metadata, domain, case_type.name,
            properties=properties,
        )

    return tables
