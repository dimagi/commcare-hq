"""
System properties are top level, schema'd properties on CommCareCase that are
made available to the user in interactions with the case search elasticsearch
index.

These are stored along with dynamic case properties in the case search index to
be easily searchable, then removed when pulling the case source from ES.
"""
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class _SystemProperty:
    key: str  # The user-facing property name
    system_name: str  # The CommCareCase field name
    is_datetime: bool = False
    _es_field_name: str = None  # Path to use for ES logic, if not system_name
    _value_getter: Callable = None

    def get_value(self, doc):
        if self._value_getter:
            return self._value_getter(doc)
        return doc.get(self.system_name)

    @property
    def es_field_name(self):
        return self._es_field_name or self.system_name


SPECIAL_CASE_PROPERTIES_MAP = {prop.key: prop for prop in [
    _SystemProperty(
        key='@case_id',
        system_name='_id',
    ),
    _SystemProperty(
        key='@case_type',
        system_name='type',
        _es_field_name='type.exact',
    ),
    _SystemProperty(
        key='@owner_id',
        system_name='owner_id',
    ),
    _SystemProperty(
        key='@status',
        system_name='closed',
        _value_getter=lambda doc: 'closed' if doc.get('closed') else 'open',
    ),
    _SystemProperty(
        key='name',
        system_name='name',
        _es_field_name='name.exact',
    ),
    _SystemProperty(
        key='case_name',
        system_name='name',
        _es_field_name='name.exact',
    ),
    _SystemProperty(
        key='external_id',
        system_name='external_id',
        _value_getter=lambda doc: doc.get('external_id', ''),
    ),
    _SystemProperty(
        key='date_opened',
        system_name='opened_on',
        is_datetime=True,
    ),
    _SystemProperty(
        key='closed_on',
        system_name='closed_on',
        is_datetime=True,
    ),
    _SystemProperty(
        key='last_modified',
        system_name='modified_on',
        is_datetime=True,
    ),
]}
