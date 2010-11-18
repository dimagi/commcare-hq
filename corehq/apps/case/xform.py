from corehq.apps.case import const

"""
Work on cases based on XForms. In our world XForms are special couch documents.
"""
from corehq.apps.case.models import CommCareCase
from couchdbkit.schema.properties_proxy import SchemaProperty

def get_or_update_cases(xformdoc):
    """
    Given an xform document, update any case blocks found within it,
    returning a dicitonary mapping the case ids affected to the
    couch case document objects
    """
    case_blocks = extract_case_blocks(xformdoc)
    cases_touched = {}
    for case_block in case_blocks:
        case_doc = get_or_update_model(case_block)
        cases_touched[case_doc.case_id] = case_doc
    return cases_touched


def get_or_update_model(case_block):
    """
    Gets or updates an existing case, based on a block of data in a 
    submitted form.  Doesn't save anything.
    """
    if const.CASE_ACTION_CREATE in case_block:
        case_doc = CommCareCase.from_doc(case_block)
        return case_doc
    else:
        case_id = case_block[const.CASE_TAG_ID]
        case_doc = CommCareCase.get_by_case_id(case_id)
        case_doc.update_from_block(case_block)
        return case_doc
        
    
def extract_case_blocks(doc):
    """
    Extract all case blocks from a document, returning an array of dictionaries
    with the data in each case. 
    """
    if doc is None: return []  
    block_list = []
    try: 
        for key, value in doc.items():
            if const.CASE_TAG == key:
                # we explicitly don't support nested cases yet, so no need
                # to check further
                block_list.append(value) 
            else:
                # recursive call
                block_list.extend(extract_case_blocks(value))
    except AttributeError :
        # whoops, this wasn't a dictionary, an expected outcome in the recursive
        # case.  Fall back to base case
        return []
    
    return block_list