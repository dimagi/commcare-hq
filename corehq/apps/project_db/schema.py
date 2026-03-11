import re

import sqlalchemy
from sqlalchemy import Boolean, Column, Date, DateTime, Index, Numeric, Table, Text

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.userreports.util import get_table_name

PROJECT_DB_TABLE_PREFIX = 'projectdb_'

# Columns present on every project DB table, in order.
# Each entry is (name, type, column_kwargs).
FIXED_COLUMNS = (
    ('case_id', Text, {'primary_key': True}),
    ('owner_id', Text, {'nullable': False}),
    ('case_name', Text, {}),
    ('opened_on', DateTime(timezone=True), {}),
    ('closed_on', DateTime(timezone=True), {}),
    ('modified_on', DateTime(timezone=True), {}),
    ('closed', Boolean, {}),
    ('external_id', Text, {}),
    ('server_modified_on', DateTime(timezone=True), {}),
    ('parent_id', Text, {}),
    ('host_id', Text, {}),
)

FIXED_COLUMN_NAMES = frozenset(name for name, _, _ in FIXED_COLUMNS)


def get_case_table_schema(domain, case_type):
    """Construct a SQLAlchemy ``Table`` schema by reflection

    This inspects the DB to get the schema for a case type table in the ProjectDB
    """
    from corehq.apps.project_db.table_manager import get_project_db_engine

    table_name = get_project_db_table_name(domain, case_type)
    engine = get_project_db_engine()
    metadata = sqlalchemy.MetaData()
    try:
        return Table(table_name, metadata, autoload_with=engine)
    except sqlalchemy.exc.NoSuchTableError:
        return None


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
    fixed_columns = [Column(name, col_type, **kwargs)
                     for name, col_type, kwargs in FIXED_COLUMNS]
    table = Table(
        table_name,
        metadata,
        *fixed_columns,
        *property_columns,
    )
    Index(f'ix_{table_name}_owner_id', table.c['owner_id'])
    Index(f'ix_{table_name}_modified_on', table.c['modified_on'])
    Index(f'ix_{table_name}_parent_id', table.c['parent_id'])
    Index(f'ix_{table_name}_host_id', table.c['host_id'])
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
SEP = '__'

_TYPED_COLUMN_EXTRAS = {
    'date': (Date, 'date'),
    'number': (Numeric, 'numeric'),
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

    Every property gets a raw Text column named ``prop__<name>``.
    ``date`` and ``number`` properties get an additional typed column.
    """
    columns = []
    for name, data_type in properties:
        _validate_name(name, 'property')
        col_name = f'prop{SEP}{name}'
        columns.append(Column(col_name, Text))
        if data_type in _TYPED_COLUMN_EXTRAS:
            sa_type, suffix = _TYPED_COLUMN_EXTRAS[data_type]
            columns.append(Column(f'{col_name}{SEP}{suffix}', sa_type))
    return columns
