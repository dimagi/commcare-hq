def user_may_view_file_upload(domain, couch_user, case_upload_record):
    return (
        # Safely assumes that domain admins are not location-restricted
        couch_user.is_domain_admin(domain) or
        couch_user.user_id == case_upload_record.couch_user_id
    )


def user_may_update_comment(couch_user, case_upload_record):
    return case_upload_record.couch_user_id == couch_user.user_id
