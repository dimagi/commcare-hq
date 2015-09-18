def get_select_chain(app, module, include_self=True):
        select_chain = [module] if include_self else []
        current_module = module
        while hasattr(current_module, 'parent_select') and current_module.parent_select.active:
            current_module = app.get_module_by_unique_id(
                current_module.parent_select.module_id
            )
            select_chain.append(current_module)
        return select_chain

def get_select_chain_meta(app, module):
    """
        return list of dicts containing datum IDs and case types
        [
           {'session_var': 'parent_parent_id', ... },
           {'session_var': 'parent_id', ...}
           {'session_var': 'child_id', ...},
        ]
    """
    if not (module and module.module_type == 'basic'):
        return []

    select_chain = get_select_chain(app, module)
    return [
        {
            'session_var': ('parent_' * i or 'case_') + 'id',
            'case_type': mod.case_type,
            'module': mod,
            'index': i
        }
        for i, mod in reversed(list(enumerate(select_chain)))
    ]
