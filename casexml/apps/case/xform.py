"""
Work on cases based on XForms. In our world XForms are special couch documents.
"""
import logging

from couchdbkit.resource import ResourceNotFound
from dimagi.utils.chunked import chunked
from casexml.apps.case.exceptions import IllegalCaseId, NoDomainProvided
from casexml.apps.case import settings
from dimagi.utils.couch.database import iter_docs

from casexml.apps.case import const
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xml.parser import case_update_from_block


class CaseDbCache(object):
    """
    A temp object we use to keep a cache of in-memory cases around
    so we can get the latest updates even if they haven't been saved
    to the database. Also provides some type checking safety.
    """
    def __init__(self, domain=None, strip_history=False):
        self.cache = {}
        self.domain = domain
        self.strip_history = strip_history

    def validate_doc(self, doc):
        # some forms recycle case ids as other ids (like xform ids)
        # disallow that hard.
        if self.domain and doc.domain != self.domain:
            raise IllegalCaseId("Bad case id")

        if doc.doc_type == 'CommCareCase-Deleted':
            raise IllegalCaseId("Case [%s] is deleted " % doc.get_id)

        if doc.doc_type != 'CommCareCase':
            raise IllegalCaseId(
                "Bad case doc type! "
                "This usually means you are using a bad value for case_id."
            )

    def get(self, case_id):
        if case_id in self.cache:
            return self.cache[case_id]

        try: 
            case_doc = CommCareCase.get(case_id, strip_history=self.strip_history)
        except ResourceNotFound:
            return None

        self.validate_doc(case_doc)
        self.cache[case_id] = case_doc
        return case_doc
        
    def set(self, case_id, case):
        self.cache[case_id] = case
        
    def doc_exist(self, case_id):
        return case_id in self.cache or CommCareCase.get_db().doc_exist(case_id)

    def in_cache(self, case_id):
        return case_id in self.cache

    def populate(self, case_ids):

        def _iter_raw_cases(case_ids):
            if self.strip_history:
                for ids in chunked(case_ids, 100):
                    for row in CommCareCase.get_db().view("case/get_lite", keys=ids, include_docs=False):
                        yield row['value']
            else:
                for raw_case in iter_docs(CommCareCase.get_db(), case_ids):
                    yield raw_case

        for raw_case in  _iter_raw_cases(case_ids):
            case = CommCareCase.wrap(raw_case)
            self.set(case._id, case)



def get_and_check_xform_domain(xform):
    try:
        domain = xform.domain
    except AttributeError:
        domain = None

    if not domain and settings.CASEXML_FORCE_DOMAIN_CHECK:
        raise NoDomainProvided()

    return domain


def get_or_update_cases(xform):
    """
    Given an xform document, update any case blocks found within it,
    returning a dictionary mapping the case ids affected to the
    couch case document objects
    """
    case_blocks = extract_case_blocks(xform)

    domain = get_and_check_xform_domain(xform)

    case_db = CaseDbCache(domain=domain)
    for case_block in case_blocks:
        case_doc = _get_or_update_model(case_block, xform, case_db)
        if case_doc:
            case_doc.xform_ids.append(xform.get_id)
            case_db.set(case_doc.case_id, case_doc)
        else:
            logging.error(
                "XForm %s had a case block that wasn't able to create a case! "
                "This usually means it had a missing ID" % xform.get_id
            )
    
    # once we've gotten through everything, validate all indices
    def _validate_indices(case):
        if case.indices:
            for index in case.indices:
                if not case_db.doc_exist(index.referenced_id):
                    raise Exception(
                        ("Submitted index against an unknown case id: %s. "
                         "This is not allowed. Most likely your case "
                         "database is corrupt and you should restore your "
                         "phone directly from the server.") % index.referenced_id)
    [_validate_indices(case) for case in case_db.cache.values()]
    return case_db.cache


def _get_or_update_model(case_block, xform, case_db):
    """
    Gets or updates an existing case, based on a block of data in a 
    submitted form.  Doesn't save anything.
    """
    
    case_update = case_update_from_block(case_block)
    case = case_db.get(case_update.id)
    
    if case is None:
        case = CommCareCase.from_case_update(case_update, xform)
        return case
    else:
        case.update_from_case_update(case_update, xform)
        return case


def is_excluded(doc):
    # exclude anything matching a certain set of conditions from case processing.
    # as of today, the only things that meet these requirements are device logs.
    device_report_xmlns = "http://code.javarosa.org/devicereport"
    try: 
        return (hasattr(doc, "xmlns") and doc.xmlns == device_report_xmlns) or \
               ("@xmlns" in doc and doc["@xmlns"] == device_report_xmlns)
    except TypeError:
        # wasn't iterable, don't exclude
        return False


def extract_case_blocks(doc):
    """
    Extract all case blocks from a document, returning an array of dictionaries
    with the data in each case. 
    """
    if doc is None or is_excluded(doc):
        return []
    
    block_list = []
    if isinstance(doc, list):
        for item in doc:
            block_list.extend(extract_case_blocks(item))
    else:
        try:
            items = doc.items()
        except AttributeError:
            # if not dict-like
            return []
        else:
            for key, value in items:
                if const.CASE_TAG == key:
                    # we explicitly don't support nested cases yet, so no need
                    # to check further
                    # BUT, it could be a list
                    if isinstance(value, list):
                        for item in value:
                            block_list.append(item)
                    else:
                        block_list.append(value)
                else:
                    # recursive call
                    block_list.extend(extract_case_blocks(value))
    
    # filter out anything without a case id property
    def _has_case_id(case_block):
        return (const.CASE_TAG_ID in case_block or
                const.CASE_ATTR_ID in case_block)
    return [block for block in block_list if _has_case_id(block)]


def cases_referenced_by_xform(xform):
    """
    JSON repr of XFormInstance -> [CommCareCase]
    """
    def extract_case_id(case_block):
        return (case_block.get(const.CASE_TAG_ID) or
                case_block.get(const.CASE_ATTR_ID))

    case_ids = [extract_case_id(case_block)
                for case_block in extract_case_blocks(xform)]

    cases = [CommCareCase.wrap(doc)
             for doc in iter_docs(CommCareCase.get_db(), case_ids)]

    domain = get_and_check_xform_domain(xform)
    if domain:
        for case in cases:
            assert case.domain == domain

    return cases