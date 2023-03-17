"""
AppES
-----
"""
from datetime import datetime

from dimagi.utils.parsing import json_format_datetime

from . import filters, queries
from .client import ElasticDocumentAdapter, create_document_adapter
from .es_query import HQESQuery
from .index.settings import IndexSettingsKey
from .transient_util import get_adapter_mapping


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


class ElasticApp(ElasticDocumentAdapter):

    settings_key = IndexSettingsKey.APPS

    @property
    def mapping(self):
        return get_adapter_mapping(self)

    def from_python(self, app):
        """
        Takes in an ``Application`` object or an app dict
        and applies required transformation to make it suitable for ES.
        The function is replica of ``transform_app_for_es`` with added support for user objects.
        In future all references to  ``transform_app_for_es`` will be replaced by `from_python`

        :param app: an instance of ``Application`` or ``dict`` which is ``Application.to_json()``

        :raises TypeError: if object passes in not instance of ``ApplicationBase``
        """
        from corehq.apps.app_manager.models import ApplicationBase
        from corehq.apps.app_manager.util import get_correct_app_class

        if isinstance(app, dict):
            app_obj = get_correct_app_class(app).wrap(app)
        elif isinstance(app, ApplicationBase):
            app_obj = app
        else:
            raise TypeError(f"Unknown type {type(app)}")
        app_obj['@indexed_on'] = json_format_datetime(datetime.utcnow())
        app_dict = app_obj.to_json()
        return app_dict.pop('_id'), app_dict


app_adapter = create_document_adapter(
    ElasticApp,
    "hqapps_2020-02-26",
    "app",
)


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
