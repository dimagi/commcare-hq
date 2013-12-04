


def form_matches_users(form, users):
    try:
        return form['form']['meta']['userID'] in users
    except KeyError:
        return False
