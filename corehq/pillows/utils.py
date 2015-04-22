

DELETED_DOC_TYPES = {
    'CommCareCase': [
        'CommCareCase-Deleted',
    ],
    'XFormInstance': [
        'XFormInstance-Deleted',
        'XFormArchived',
        # perhaps surprisingly - 'XFormDeprecated' is not a deletion, since it has that
        # type from its creation. The new form gets saved on top of the form being deprecated
        # which should work out fine for the way this is intended to be used
    ],
}


def get_deleted_doc_types(doc_type):
    """
    Return a list of doc types that represent deletions of this type. This is useful for
    things like pillows that need to catch a deletion and do something to remove
    the data from a report/index.
    """
    return DELETED_DOC_TYPES.get(doc_type, [])
