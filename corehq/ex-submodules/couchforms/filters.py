'''
Out of the box filters you can use to filter your exports
'''

def instances(doc):
    """
    Only return XFormInstances, not duplicates or errors
    """
    return doc["doc_type"] == "XFormInstance"

def duplicates(doc):
    """
    Only return Duplicates
    """
    return doc["doc_type"] == "XFormDuplicate"
 
def problem_forms(doc):
    """
    Return non-XFormInstances (duplicates, errors, etc.)
    """
    return doc["doc_type"] != "XFormInstance"