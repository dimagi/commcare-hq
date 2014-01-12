


def form_matches_users(form, users):
    try:
        return form['form']['meta']['userID'] in users
    except KeyError:
        return False

def is_commconnect_form(form):
    """
    Checks if something is a commconnect form, by manually inspecting the deviceID property
    """
    return form.get('form', {}).get('meta', {}).get('deviceID', None) == 'commconnect'
