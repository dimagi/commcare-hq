import re

from sqlalchemy import Boolean, Column, Date, DateTime, Index, Numeric, Table, Text

from corehq.apps.userreports.util import get_table_name

_VALID_NAME_RE = re.compile(r'^[a-zA-Z0-9_-]+$')

PROJECT_DB_TABLE_PREFIX = 'projectdb_'


def get_project_db_table_name(domain, case_type):
    """Generate a PostgreSQL table name for a project DB case type table.

    Uses the same hashing/truncation strategy as UCR tables to ensure
    names are unique, deterministic, and within Postgres's 63-char limit.
    """
    return get_table_name(
        domain, case_type, max_length=63, prefix=PROJECT_DB_TABLE_PREFIX,
    )


def build_table_for_case_type(metadata, domain, case_type,
                              properties=None, relationships=None):
    """Build a SQLAlchemy Table for a case type with fixed case columns.

    :param metadata: SQLAlchemy MetaData instance
    :param domain: CommCare project domain
    :param case_type: case type name
    :param properties: list of (name, data_type) tuples for dynamic columns
    :param relationships: list of (identifier, referenced_case_type) tuples
    :returns: SQLAlchemy Table
    """
    table_name = get_project_db_table_name(domain, case_type)
    property_columns = _build_property_columns(properties or [])
    relationship_columns = _build_relationship_columns(relationships or [])
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
        *relationship_columns,
    )
    Index(f'ix_{table_name}_owner_id', table.c['owner_id'])
    Index(f'ix_{table_name}_modified_on', table.c['modified_on'])
    for identifier, _case_type in (relationships or []):
        col_name = f'idx_{identifier}'
        Index(f'ix_{table_name}_{col_name}', table.c[col_name])
    return table


# Maps data types that get an additional typed column to their
# (SQLAlchemy type, column name suffix) pairs.
# These keys must match CaseProperty.DataType enum values
# from corehq/apps/data_dictionary/models.py.
_TYPED_COLUMN_EXTRAS = {
    'date': (Date, '_date'),
    'number': (Numeric, '_numeric'),
}


def _validate_name(name, label):
    """Reject names containing characters other than alphanumeric, underscores, and hyphens."""
    if not _VALID_NAME_RE.match(name):
        raise ValueError(
            f"Invalid {label} name {name!r}: "
            "only alphanumeric characters, underscores, and hyphens are allowed"
        )


def _build_relationship_columns(relationships):
    """Build Column objects for case relationship indices.

    Each relationship gets a Text column named ``idx_<identifier>``.
    No ForeignKey constraints are added because the async change feed
    does not guarantee write order across case types.
    """
    for identifier, _ct in relationships:
        _validate_name(identifier, 'relationship')
    return [Column(f'idx_{identifier}', Text) for identifier, _ct in relationships]


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
