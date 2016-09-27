

def user_can_view_reports(project, couch_user):
    return bool(
        project
        and not project.is_snapshot
        and (couch_user.can_view_some_reports(project.name))
    )
