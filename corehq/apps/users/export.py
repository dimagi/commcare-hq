def export_users(users, workbook):
    user_keys = ('user_id', 'username', )
    user_rows = []
    fields = set()
    for user in users:
        user_row = {}
        for key in user_keys:
            if key == 'username':
                user_row[key] = user.raw_username
            else:
                user_row[key] = getattr(user, key)
        for key in user.user_data:
            user_row["d.%s" % key] = user.user_data[key]
        user_rows.append(user_row)
        fields.update(user_row.keys())
    workbook.open("User", list(user_keys) + sorted(fields - set(user_keys)))
    for user_row in user_rows:
        workbook.write_row('User', user_row)