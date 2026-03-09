import re

from sqlalchemy import Boolean, Column, Date, DateTime, Index, Numeric, Table, Text

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.userreports.util import get_table_name

PROJECT_DB_TABLE_PREFIX = 'projectdb_'


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


def build_table_for_case_type(metadata, domain, case_type, properties=None):
    """Build a SQLAlchemy Table for a case type with fixed case columns.

    :param metadata: SQLAlchemy MetaData instance
    :param domain: CommCare project domain
    :param case_type: case type name
    :param properties: list of (name, data_type) tuples for dynamic columns
    :returns: SQLAlchemy Table
    """
    table_name = get_project_db_table_name(domain, case_type)
    property_columns = _build_property_columns(properties or [])
    table = Table(
        table_name,
        metadata,
        Column('case_id', Text, primary_key=True),
        Column('owner_id', Text, nullable=False),
        Column('case_name', Text),
        Column('opened_on', DateTime(timezone=True)),
        Column('closed_on', DateTime(timezone=True)),
        Column('modified_on', DateTime(timezone=True)),
        Column('closed', Boolean),
        Column('external_id', Text),
        Column('server_modified_on', DateTime(timezone=True)),
        *property_columns,
    )
    Index(f'ix_{table_name}_owner_id', table.c['owner_id'])
    Index(f'ix_{table_name}_modified_on', table.c['modified_on'])
    return table


def get_project_db_table_name(domain, case_type):
    """Generate a PostgreSQL table name for a project DB case type table.

    Uses the same hashing/truncation strategy as UCR tables to ensure
    names are unique, deterministic, and within Postgres's 63-char limit.
    """
    return get_table_name(
        domain, case_type, max_length=63, prefix=PROJECT_DB_TABLE_PREFIX,
    )


# --- Private helpers ---

# Maps data types that get an additional typed column to their
# (SQLAlchemy type, column name suffix) pairs.
# These keys must match CaseProperty.DataType enum values
# from corehq/apps/data_dictionary/models.py.
_TYPED_COLUMN_EXTRAS = {
    'date': (Date, '_date'),
    'number': (Numeric, '_numeric'),
}

_VALID_NAME_RE = re.compile(r'^[a-zA-Z0-9_-]+$')


def _validate_name(name, label):
    """Reject names containing characters other than alphanumeric, underscores, and hyphens."""
    if not _VALID_NAME_RE.match(name):
        raise ValueError(
            f"Invalid {label} name {name!r}: "
            "only alphanumeric characters, underscores, and hyphens are allowed"
        )


def _build_property_columns(properties):
    """Build Column objects for dynamic case properties.

    Every property gets a raw Text column named ``prop_<name>``.
    ``date`` and ``number`` properties get an additional typed column.
    """
    columns = []
    for name, data_type in properties:
        _validate_name(name, 'property')
        col_name = f'prop_{name}'
        columns.append(Column(col_name, Text))
        if data_type in _TYPED_COLUMN_EXTRAS:
            sa_type, suffix = _TYPED_COLUMN_EXTRAS[data_type]
            columns.append(Column(f'{col_name}{suffix}', sa_type))
    return columns
