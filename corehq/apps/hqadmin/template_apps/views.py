from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy

from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqadmin.views.utils import BaseAdminSectionView
from corehq.apps.hqwebapp.decorators import use_bootstrap5


@method_decorator(require_superuser, name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
class ManageTemplateAppsView(BaseAdminSectionView):
    urlname = 'manage_template_apps'
    page_title = gettext_lazy('Manage Template Apps')
    template_name = 'hqadmin/template_apps/manage_template_apps.html'
