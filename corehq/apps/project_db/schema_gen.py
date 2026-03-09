from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.project_db.schema import build_table_for_case_type


def build_tables_for_domain(metadata, domain, relationships_by_type=None):
    """Build SQLAlchemy Tables for all active case types in a domain.

    Reads the data dictionary (CaseType and CaseProperty models) and
    produces a corresponding SQLAlchemy Table for each non-deprecated
    case type.

    :param metadata: SQLAlchemy MetaData instance
    :param domain: CommCare project domain
    :param relationships_by_type: optional dict mapping case type name
        to a list of (identifier, referenced_case_type) tuples
    :returns: dict mapping case type name to SQLAlchemy Table
    """
    if relationships_by_type is None:
        relationships_by_type = {}

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
        relationships = relationships_by_type.get(case_type.name, [])
        tables[case_type.name] = build_table_for_case_type(
            metadata, domain, case_type.name,
            properties=properties,
            relationships=relationships,
        )

    return tables
