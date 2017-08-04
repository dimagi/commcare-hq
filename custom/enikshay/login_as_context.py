def get_enikshay_login_as_context(user):
    return {
        'district': None,
        'usertype_display': get_usertype_display(user.user_data.get('usertype')),
    }


def get_usertype_display(usertype):
    return {
        'pac': 'AYUSH / Other Provider',
        'pcp': 'MBBS Provider',
        'pcc-chemist': 'Chemist',
        'plc': 'Lab',
        'ps-fieldstaff': 'Field Staff',
    }.get(usertype, usertype)
