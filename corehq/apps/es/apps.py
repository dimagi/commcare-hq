"""
AppES
-----
"""
from __future__ import absolute_import
from __future__ import unicode_literals
from .es_query import HQESQuery
from . import filters
from . import queries


class AppES(HQESQuery):
    index = 'apps'

    @property
    def builtin_filters(self):
        return [
            is_build,
            is_released,
            created_from_template,
            uses_case_sharing,
            cloudcare_enabled,
            app_id,
        ] + super(AppES, self).builtin_filters


def build_comment(comment):
    return queries.search_string_query(comment, ['build_comment'])


def version(version):
    return filters.term('version', version)


def is_build(build=True):
    filter = filters.empty('copy_of')
    if build:
        return filters.NOT(filter)
    return filter


def is_released(released=True):
    return filters.term('is_released', released)


def created_from_template(from_template=True):
    filter = filters.empty('created_from_template')
    if from_template:
        return filters.NOT(filter)
    return filter


def uses_case_sharing(case_sharing=True):
    return filters.term('case_sharing', case_sharing)


def cloudcare_enabled(cloudcare_enabled):
    return filters.term('cloudcare_enabled', cloudcare_enabled)


def app_id(app_id):
    return filters.term('copy_of', app_id)
