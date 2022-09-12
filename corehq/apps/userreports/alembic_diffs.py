from functools import partial

import attr
from alembic.migration import MigrationContext


def get_migration_context(connection, table_names=None):
    opts = {'compare_type': True}
    if table_names:
        opts['include_name'] = partial(include_name, table_names)
        opts['include_object'] = partial(include_object, table_names)
    return MigrationContext.configure(connection, opts=opts)


def include_name(tables_to_include, name, type_, parent_names):
    """Checks if the object should be included. This is called prior
    to object reflection and is only called for existing database objects"""
    return _include_table(tables_to_include, type_, name)


def include_object(tables_to_include, object, name, type_, reflected, compare_to):
    """Checks if the object should be included. This runs after reflection and will
    also be called with new objects that are only in the metadata"""
    return _include_table(tables_to_include, type_, name)


def _include_table(tables_to_include, type_, name):
    if type_ == "table":
        return name in tables_to_include
    return True


def get_tables_to_rebuild(diffs):
    return {diff.table_name for diff in diffs if diff.type in DiffTypes.TYPES_FOR_REBUILD}


def reformat_alembic_diffs(raw_diffs):
    """
    See: http://alembic.readthedocs.io/en/latest/api/autogenerate.html
    :param raw_diffs: from alembic
    :return: list of ``SimpleDiff`` tuples
    """
    diffs = []

    def _simplify_diff(raw_diff):
        type_ = raw_diff[0]
        if type_ in DiffTypes.TABLE_TYPES:
            diffs.append(
                SimpleDiff(type_, raw_diff[1].name, None, raw_diff)
            )
        elif type_ in DiffTypes.CONSTRAINT_TYPES:
            any_column = list(raw_diff[1].columns.values())[0]
            table_name = any_column.table.name
            diffs.append(
                SimpleDiff(type_, table_name, raw_diff[1].name, raw_diff)
            )
        elif type_ in DiffTypes.MODIFY_TYPES:
            diffs.append(
                SimpleDiff(type_, raw_diff[2], raw_diff[3], raw_diff)
            )
        elif type_ == DiffTypes.ADD_COLUMN and raw_diff[3].nullable:
            diffs.append(
                SimpleDiff(DiffTypes.ADD_NULLABLE_COLUMN, raw_diff[2], raw_diff[3].name, raw_diff)
            )
        elif type_ in DiffTypes.COLUMN_TYPES:
            diffs.append(
                SimpleDiff(type_, raw_diff[2], raw_diff[3].name, raw_diff)
            )
        elif type_ in DiffTypes.INDEX_TYPES:
            diffs.append(SimpleDiff(type_, diff[1].table.name, diff[1].name, raw_diff))
        else:
            diffs.append(SimpleDiff(type_, None, None, None))

    for diff in raw_diffs:
        if isinstance(diff, list):
            for d in diff:
                _simplify_diff(d)
        else:
            _simplify_diff(diff)

    return diffs


class DiffTypes(object):
    ADD_TABLE = 'add_table'
    REMOVE_TABLE = 'remove_table'
    TABLE_TYPES = (ADD_TABLE, REMOVE_TABLE)

    ADD_COLUMN = 'add_column'
    REMOVE_COLUMN = 'remove_column'
    COLUMN_TYPES = (ADD_COLUMN, REMOVE_COLUMN)

    MODIFY_NULLABLE = 'modify_nullable'
    MODIFY_TYPE = 'modify_type'
    MODIFY_DEFAULT = 'modify_default'
    MODIFY_TYPES = (MODIFY_TYPE, MODIFY_DEFAULT, MODIFY_NULLABLE)

    ADD_CONSTRAINT = 'add_constraint'
    REMOVE_CONSTRAINT = 'remove_constraint'

    ADD_INDEX = 'add_index'
    REMOVE_INDEX = 'remove_index'
    INDEX_TYPES = (ADD_INDEX, REMOVE_INDEX)

    ADD_NULLABLE_COLUMN = 'add_nullable_column'
    MIGRATEABLE_TYPES = (ADD_NULLABLE_COLUMN,) + INDEX_TYPES

    CONSTRAINT_TYPES = (ADD_CONSTRAINT, REMOVE_CONSTRAINT) + INDEX_TYPES

    ALL = TABLE_TYPES + COLUMN_TYPES + MODIFY_TYPES + CONSTRAINT_TYPES

    TYPES_FOR_REBUILD = TABLE_TYPES + COLUMN_TYPES + (MODIFY_TYPE, MODIFY_NULLABLE)
    TYPES_FOR_MIGRATION = INDEX_TYPES + (ADD_NULLABLE_COLUMN,)


@attr.s(frozen=True)
class SimpleDiff(object):
    type = attr.ib()
    table_name = attr.ib()
    item_name = attr.ib()
    raw = attr.ib(cmp=False)

    def to_dict(self):
        return {
            'type': self.type,
            'item_name': self.item_name
        }

    @property
    def column(self):
        return self._item(3, DiffTypes.COLUMN_TYPES + (DiffTypes.ADD_NULLABLE_COLUMN,))

    @property
    def index(self):
        return self._item(1, DiffTypes.INDEX_TYPES)

    @property
    def constraint(self):
        return self._item(1, DiffTypes.CONSTRAINT_TYPES)

    def _item(self, index, supported_types):
        if self.type not in supported_types:
            raise NotImplementedError
        return self.raw[index]
