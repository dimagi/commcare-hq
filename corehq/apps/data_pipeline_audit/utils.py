from __future__ import absolute_import
from __future__ import unicode_literals
from collections import Counter

DOC_TYPE_MAPPING = {
    'xforminstance': 'XFormInstance',
    'submissionerrorlog': 'SubmissionErrorLog',
    'xformduplicate': 'XFormDuplicate',
    'xformerror': 'XFormError',
    'xformarchived': 'XFormArchived',
    'xformdeprecated': 'XFormDeprecated',
}


def map_counter_doc_types(counter):
    """Map lower cased doc_types from ES to CamelCased doc types"""
    return Counter({
        DOC_TYPE_MAPPING.get(es_doc_type, es_doc_type): count
        for es_doc_type, count in counter.items()
    })
