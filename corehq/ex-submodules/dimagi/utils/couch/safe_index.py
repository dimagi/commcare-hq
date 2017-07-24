def safe_index(object, keys):
    """Safely index a document, returning None if the value isn't found."""
    if len(keys) == 1:
        # first check dict lookups, in case of conflicting property names
        # with methods (e.g. case/update --> a dict's update method when
        # it should be the case block's update block.
        try:
            if keys[0] in object:  
                return object[keys[0]]
        except Exception:
            return getattr(object, keys[0], None)
    else:
        return safe_index(safe_index(object, [keys[0]]), keys[1:])