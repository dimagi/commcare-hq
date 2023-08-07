"""
FormES
--------
"""
from copy import copy
from datetime import datetime

from jsonobject.exceptions import BadValueError

from casexml.apps.case.exceptions import PhoneDateValueError
from casexml.apps.case.xml.parser import (
    CaseGenerationException,
    case_update_from_block,
)
from couchforms.geopoint import GeoPoint
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.es.mappings.const import NULL_VALUE

from . import filters
from .client import ElasticDocumentAdapter, create_document_adapter
from .const import (
    HQ_FORMS_INDEX_CANONICAL_NAME,
    HQ_FORMS_INDEX_NAME,
    HQ_FORMS_SECONDARY_INDEX_NAME,
)
from .es_query import HQESQuery
from .index.settings import IndexSettingsKey


class FormES(HQESQuery):
    index = HQ_FORMS_INDEX_CANONICAL_NAME
    default_filters = {
        'is_xform_instance': filters.term("doc_type", "xforminstance"),
        'has_xmlns': filters.exists("xmlns"),
        'has_user': filters.exists("form.meta.userID"),
        'has_domain': filters.exists("domain"),
    }

    @property
    def builtin_filters(self):
        return [
            form_ids,
            xmlns,
            app,
            submitted,
            completed,
            user_id,
            user_type,
            user_ids_handle_unknown,
            updating_cases,
        ] + super(FormES, self).builtin_filters

    def user_aggregation(self):
        return self.terms_aggregation('form.meta.userID', 'user')

    def domain_aggregation(self):
        return self.terms_aggregation('domain.exact', 'domain')

    def only_archived(self):
        """Include only archived forms, which are normally excluded"""
        return (self.remove_default_filter('is_xform_instance')
                .filter(filters.doc_type('xformarchived')))


class ElasticForm(ElasticDocumentAdapter):

    settings_key = IndexSettingsKey.FORMS
    canonical_name = HQ_FORMS_INDEX_CANONICAL_NAME

    @property
    def mapping(self):
        from .mappings.xform_mapping import XFORM_MAPPING
        return XFORM_MAPPING

    @property
    def model_cls(self):
        from corehq.form_processor.models.forms import XFormInstance
        return XFormInstance

    def _from_dict(cls, xform_dict):
        """
        Takes in a xform dict and applies required transformation to make it suitable for ES.

        :param xform: an instance of ``dict`` which is ``XFormInstance.to_json()``
        """
        from casexml.apps.case.xform import extract_case_blocks

        from corehq.apps.receiverwrapper.util import get_app_version_info
        from corehq.pillows.utils import format_form_meta_for_es, get_user_type
        from corehq.pillows.xform import is_valid_date

        # create shallow copy of form object and case objects
        # that will be modified in tranformation
        form = xform_dict['form'] = copy(xform_dict['form'])

        if 'case' in form:
            if isinstance(form['case'], dict):
                form['case'] = copy(form['case'])
            elif isinstance(form['case'], list):
                form['case'] = [copy(case) for case in form['case']]

        user_id = None

        if 'meta' in form:
            form_meta = form['meta'] = copy(form['meta'])
            if not is_valid_date(form_meta.get('timeEnd', None)):
                form_meta['timeEnd'] = None
            if not is_valid_date(form_meta.get('timeStart', None)):
                form_meta['timeStart'] = None

            # Some docs have their @xmlns and #text here
            if isinstance(form_meta.get('appVersion'), dict):
                form_meta = format_form_meta_for_es(form_meta)

            app_version_info = get_app_version_info(
                xform_dict['domain'],
                xform_dict.get('build_id'),
                xform_dict.get('version'),
                form_meta,
            )
            form_meta['commcare_version'] = app_version_info.commcare_version
            form_meta['app_build_version'] = app_version_info.build_version
            user_id = form_meta.get('userID', None)

            try:
                geo_point = GeoPoint.from_string(xform_dict['form']['meta']['location'])
                form_meta['geo_point'] = geo_point.lat_lon
            except (KeyError, BadValueError):
                form_meta['geo_point'] = None
                pass

        xform_dict['user_type'] = get_user_type(user_id)
        xform_dict['inserted_at'] = json_format_datetime(datetime.utcnow())

        try:
            case_blocks = extract_case_blocks(xform_dict)
        except PhoneDateValueError:
            pass
        else:
            for case_dict in case_blocks:
                for date_modified_key in ['date_modified', '@date_modified']:
                    if not is_valid_date(case_dict.get(date_modified_key, None)):
                        if case_dict.get(date_modified_key) == '':
                            case_dict[date_modified_key] = None
                        else:
                            case_dict.pop(date_modified_key, None)

                # convert all mapped dict properties to nulls if they are empty strings
                for object_key in ['index', 'attachment', 'create', 'update']:
                    if object_key in case_dict and not isinstance(case_dict[object_key], dict):
                        case_dict[object_key] = None

            try:
                xform_dict["__retrieved_case_ids"] = list(set(case_update_from_block(cb).id for cb in case_blocks))
            except CaseGenerationException:
                xform_dict["__retrieved_case_ids"] = []

        if 'backend_id' not in xform_dict:
            xform_dict['backend_id'] = 'sql'

        return super()._from_dict(xform_dict)


form_adapter = create_document_adapter(
    ElasticForm,
    HQ_FORMS_INDEX_NAME,
    "xform",
    secondary=HQ_FORMS_SECONDARY_INDEX_NAME,
)


def form_ids(form_ids):
    return filters.term('_id', form_ids)


def xmlns(xmlnss):
    return filters.term('xmlns.exact', xmlnss)


def app(app_ids):
    return filters.term('app_id', app_ids)


def submitted(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('received_on', gt, gte, lt, lte)


def completed(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('form.meta.timeEnd', gt, gte, lt, lte)


def user_id(user_ids):
    if not isinstance(user_ids, (list, set, tuple)):
        user_ids = [user_ids]
    return filters.term(
        'form.meta.userID',
        [x if x is not None else NULL_VALUE for x in user_ids]
    )


def user_type(user_types):
    return filters.term("user_type", user_types)


def user_ids_handle_unknown(user_ids):
    missing_users = None in user_ids

    user_ids = [_f for _f in user_ids if _f]

    if not missing_users:
        user_filter = user_id(user_ids)
    elif user_ids and missing_users:
        user_filter = filters.OR(
            user_id(user_ids),
            filters.missing('form.meta.userID'),
        )
    else:
        user_filter = filters.missing('form.meta.userID')
    return user_filter


def updating_cases(case_ids):
    """return only those forms that have case blocks that touch the cases listed in `case_ids`
    """
    return filters.term("__retrieved_case_ids", case_ids)
