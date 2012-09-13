from django.conf import settings

def show_adm_nav(domain, request):
    enabled_projects = []
    if hasattr(settings, 'ADM_ENABLED_PROJECTS'):
        enabled_projects = settings.ADM_ENABLED_PROJECTS
    return request.couch_user.is_superuser or (domain in enabled_projects)