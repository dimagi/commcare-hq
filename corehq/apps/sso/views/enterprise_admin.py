from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy

from corehq.apps.enterprise.views import BaseEnterpriseAdminView
from corehq.apps.sso.models import IdentityProvider
from corehq.toggles import ENTERPRISE_SSO


@method_decorator(ENTERPRISE_SSO.required_decorator(), name='dispatch')
class ManageSSOEnterpriseView(BaseEnterpriseAdminView):
    page_title = ugettext_lazy("Manage Single Sign-On")
    urlname = 'manage_sso'
    template_name = 'sso/enterprise_admin/manage_sso.html'

    @property
    def page_context(self):
        return {
            'identity_providers': IdentityProvider.objects.filter(
                owner=self.request.account, is_editable=True
            ).all(),
            'account': self.request.account,
        }
