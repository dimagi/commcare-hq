from django.conf import settings

def show_adm_nav(domain, request):
    enabled_projects = settings.ADM_ENABLED_PROJECTS if hasattr(settings, 'ADM_ENABLED_PROJECTS') else []
    return domain and\
           (hasattr(request, 'project') and not request.project.is_snapshot) and\
           (request.couch_user.can_view_reports() or request.couch_user.get_viewable_reports()) and\
           domain in enabled_projects


def standard_start_end_key(key, datespan=None):
    startkey_suffix = [datespan.startdate_param_utc] if datespan else []
    endkey_suffix = [datespan.enddate_param_utc] if datespan else [{}]
    return dict(
        startkey=key+startkey_suffix,
        endkey=key+endkey_suffix
    )
