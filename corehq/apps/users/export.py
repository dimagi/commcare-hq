def export_users(users, workbook):
    user_keys = ('user_id', 'username', )
    workbook.open("User", user_keys)
    for user in users:
        user_row = {}
        for key in user_keys:
            if key == 'username':
                user_row[key] = user.raw_username
            else:
                user_row[key] = getattr(user, key)
        workbook.write_row('User', user_row)