from casexml.apps.case import const

"""
Work on cases based on XForms. In our world XForms are special couch documents.
"""
from casexml.apps.case.models import CommCareCase
from couchdbkit.schema.properties_proxy import SchemaProperty
import logging
from couchdbkit.resource import ResourceNotFound
from casexml.apps.case.xml.parser import case_update_from_block

class CaseDbCache(object):
    """
    A temp object we use to keep a cache of in-memory cases around
    so we can get the latest updates even if they haven't been saved
    to the database. Also provides some type checking safety.
    """
    def __init__(self):
        self.cache = {}
        
    def get(self, case_id):
        if case_id in self.cache:
            return self.cache[case_id]
        try: 
            case_doc = CommCareCase.get(case_id)
            # some forms recycle case ids as other ids (like xform ids)
            # disallow that hard.
            if case_doc.doc_type != "CommCareCase":
                raise Exception("Bad case doc type! This usually means you are using a bad value for case_id.")
            return case_doc
        except ResourceNotFound:
            return None
        
    def set(self, case_id, case):
        self.cache[case_id] = case
        
    def doc_exist(self, case_id):
        return case_id in self.cache or CommCareCase.get_db().doc_exist(case_id)
        
def get_or_update_cases(xformdoc):
    """
    Given an xform document, update any case blocks found within it,
    returning a dicitonary mapping the case ids affected to the
    couch case document objects
    """
    case_blocks = extract_case_blocks(xformdoc)
    case_db = CaseDbCache()
    for case_block in case_blocks:
        case_doc = _get_or_update_model(case_block, xformdoc, case_db)
        if case_doc:
            case_doc.xform_ids.append(xformdoc.get_id)
            case_db.set(case_doc.case_id, case_doc)
        else:
            logging.error("Xform %s had a case block that wasn't able to create a case! This usually means it had a missing ID" % xformdoc.get_id)
    
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

def _get_or_update_model(case_block, xformdoc, case_dbcache):
    """
    Gets or updates an existing case, based on a block of data in a 
    submitted form.  Doesn't save anything.
    """
    
    case_update = case_update_from_block(case_block)
    case_doc = case_dbcache.get(case_update.id)
    
    if case_doc == None:
        case_doc = CommCareCase.from_case_update(case_update, xformdoc)
        return case_doc
    else:
        case_doc.update_from_case_update(case_update, xformdoc)
        return case_doc
        
def is_excluded(doc):
    # exclude anything matching a certain set of conditions from case processing.
    # as of today, the only things that meet these requirements are device logs.
    device_report_xmlns = "http://code.javarosa.org/devicereport"
    try: 
        return (hasattr(doc, "xmlns") and doc.xmlns == device_report_xmlns) or \
               ("@xmlns" in doc and doc["@xmlns"] == device_report_xmlns)
    except TypeError:
        return False # wasn't iterable, don't exclude

def extract_case_blocks(doc):
    """
    Extract all case blocks from a document, returning an array of dictionaries
    with the data in each case. 
    """
    if doc is None or is_excluded(doc): return []
    
    block_list = []
    if isinstance(doc, list):
        for item in doc: 
            block_list.extend(extract_case_blocks(item))
    else:
        try: 
            for key, value in doc.items():
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
        except AttributeError:
            # whoops, this wasn't a list or dictionary, 
            # an expected outcome in the recursive case.
            # Fall back to base case.
            return []
    
    # filter out anything without a case id property
    def _has_case_id(case_block):
        return const.CASE_TAG_ID in case_block or \
               "@%s" % const.CASE_TAG_ID in case_block
    return [block for block in block_list if _has_case_id(block)]