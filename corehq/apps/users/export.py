def export_users(users, workbook, mimic_upload=False):
    data_prefix = 'data: ' if mimic_upload else 'd.'
    user_keys = ('user_id', 'username', 'is_active', 'name', 'groups')
    user_rows = []
    fields = set()
    for user in users:
        user_row = {}
        for key in user_keys:
            if key == 'username':
                user_row[key] = user.raw_username
            elif key == 'name':
                user_row[key] = user.full_name
            elif key == 'groups':
                user_row[key] = ", ".join(user.get_group_ids())
            else:
                user_row[key] = getattr(user, key)
        for key in user.user_data:
            user_row["%s%s" % (data_prefix, key)] = user.user_data[key]
        user_rows.append(user_row)
        fields.update(user_row.keys())
    workbook.open("Users", list(user_keys) + sorted(fields - set(user_keys)))
    for user_row in user_rows:
        workbook.write_row('Users', user_row)