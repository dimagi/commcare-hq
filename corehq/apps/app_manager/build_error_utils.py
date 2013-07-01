def get_module_info(module):
    return {
        'id': module.id,
        'name': module.name,
    }


def get_case_errors(module, needs_case_type, needs_case_detail,
                    needs_referral_detail=False):

    module_info = get_module_info(module)

    if needs_case_type and not module.case_type:
        yield {
            'type': 'no case type',
            'module': module_info,
        }

    if needs_case_detail and not module.get_detail('case_short').columns:
        yield {
            'type': 'no case detail',
            'module': module_info,
        }

    if needs_referral_detail and not module.get_detail('ref_short').columns:
        yield {
            'type': 'no ref detail',
            'module': module_info,
        }
