

def sort_with_id_list(object_list, id_list, id_property):
    """Sort object list in the same order as given list of ids

    SQL does not necessarily return the rows in any particular order so
    we need to order them ourselves.

    NOTE: this does not return the sorted list. It sorts `object_list`
    in place using Python's built-in `list.sort`.
    """
    def key(obj):
        return index_map[getattr(obj, id_property)]

    index_map = {id_: index for index, id_ in enumerate(id_list)}
    object_list.sort(key=key)
