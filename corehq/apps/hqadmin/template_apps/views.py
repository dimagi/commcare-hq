from django.db import IntegrityError, transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views import View

from corehq.apps.app_manager.models import TemplateAppSector
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqadmin.template_apps.forms import TemplateAppSectorForm
from corehq.apps.hqadmin.views.utils import BaseAdminSectionView
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action


@method_decorator(require_superuser, name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
class ManageTemplateAppsView(BaseAdminSectionView):
    urlname = 'manage_template_apps'
    page_title = gettext_lazy('Manage Template Apps')
    template_name = 'hqadmin/template_apps/manage_template_apps.html'


@method_decorator(require_superuser, name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
class TemplateAppSectorsView(HqHtmxActionMixin, View):
    urlname = 'manage_template_app_sectors'

    def get(self, request):
        return self.render_sectors(request)

    @hq_hx_action('post')
    def add_sector(self, request, *args, **kwargs):
        return self.save_sector(request)

    @hq_hx_action('post')
    def rename_sector(self, request, *args, **kwargs):
        sector = get_object_or_404(TemplateAppSector, pk=request.POST.get('sector_id'))
        return self.save_sector(request, sector=sector)

    @hq_hx_action('post')
    def delete_sector(self, request, *args, **kwargs):
        sector = get_object_or_404(TemplateAppSector, pk=request.POST.get('sector_id'))
        sector.delete()
        return self.render_sectors(request, success_message=_("Sector label deleted."))

    def save_sector(self, request, sector=None):
        form = TemplateAppSectorForm(request.POST, instance=sector)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
            except IntegrityError:
                form.add_error('name', _("A sector with this name already exists."))
            else:
                message = _("Sector label saved.") if sector else _("Sector label added.")
                return self.render_sectors(request, success_message=message)
        if sector is None:
            return self.render_sectors(request, add_new_sector_form=form)
        return self.render_sectors(request, rename_sector_form=form, rename_sector_id=sector.pk)

    def render_sectors(
        self,
        request,
        add_new_sector_form=None,
        rename_sector_form=None,
        rename_sector_id=None,
        success_message=None,
    ):
        sectors = TemplateAppSector.objects.annotate(
            template_count=Count('exchange_applications')
        ).order_by('name')
        if add_new_sector_form is None:
            add_new_sector_form = TemplateAppSectorForm()
        if success_message:
            add_new_sector_form.fields['name'].widget.attrs['autofocus'] = True
        return render(request, 'hqadmin/template_apps/sectors/manage_sector_modal_body.html', {
            'sectors': sectors,
            'add_new_sector_form': add_new_sector_form,
            'rename_sector_form': rename_sector_form,
            'rename_sector_id': rename_sector_id,
            'success_message': success_message,
        })
