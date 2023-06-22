from datetime import datetime
from dimagi.utils.parsing import json_format_datetime
from corehq.apps.case_search.const import SPECIAL_CASE_PROPERTIES
from corehq.apps.data_dictionary.util import is_case_type_deprecated


def serialize_case(case):
    """Serializes a case for the V0.6 Case API"""
    return {
        "domain": case.domain,
        "case_id": case.case_id,
        "case_type": case.type,
        "case_name": case.name,
        "external_id": case.external_id,
        "owner_id": case.owner_id,
        "date_opened": _isoformat(case.opened_on),
        "last_modified": _isoformat(case.modified_on),
        "server_last_modified": _isoformat(case.server_modified_on),
        # This is used for cases that were just created, which haven't yet been indexed
        # Providing this maintains compatibility with the es response
        "indexed_on": _isoformat(datetime.utcnow()),
        "closed": case.closed,
        "date_closed": _isoformat(case.closed_on),
        "properties": dict(case.dynamic_case_properties()),
        "indices": {
            index.identifier: {
                "case_id": index.referenced_id,
                "case_type": index.referenced_type,
                "relationship": index.relationship,
            }
            for index in case.indices if not index.is_deleted
        }
    }


def _isoformat(value):
    return json_format_datetime(value) if value else None


def serialize_es_case(case_doc):
    """Serializes a CaseSearch result for the V0.6 Case API"""
    return {
        "domain": case_doc['domain'],
        "case_id": case_doc['_id'],
        "case_type": case_doc['type'],
        "case_name": case_doc['name'],
        "external_id": case_doc['external_id'],
        "owner_id": case_doc['owner_id'],
        "date_opened": case_doc['opened_on'],
        "last_modified": case_doc['modified_on'],
        "server_last_modified": case_doc['server_modified_on'],
        "indexed_on": case_doc['@indexed_on'],
        "closed": case_doc['closed'],
        "date_closed": case_doc['closed_on'],
        "is_deprecated": is_case_type_deprecated(case_doc['domain'], case_doc['type']),
        "properties": {
            prop['key']: prop['value']
            for prop in case_doc['case_properties']
            if prop['key'] not in SPECIAL_CASE_PROPERTIES
        },
        "indices": {
            index['identifier']: {
                "case_id": index['referenced_id'],
                "case_type": index['referenced_type'],
                "relationship": index['relationship'],
            }
            for index in case_doc['indices']
        },
    }


class UserError(Exception):
    pass


class SubmissionError(Exception):
    def __init__(self, msg, form_id):
        self.form_id = form_id
        super().__init__(msg)
