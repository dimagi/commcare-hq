import json

from django.contrib import messages
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop
from django.views.decorators.http import require_POST

from couchdbkit import ResourceNotFound
from memoized import memoized

from dimagi.utils.web import json_response

from corehq.apps.commtrack.views import BaseCommTrackManageView
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.products.models import SQLProduct
from corehq.apps.programs.forms import ProgramForm
from corehq.apps.programs.models import Program


@require_POST
@domain_admin_required
def delete_program(request, domain, prog_id):
    program = Program.get(prog_id)
    program.delete()
    return json_response({
        'success': True,
        'message': _("Program '{program_name}' has successfully been deleted.").format(
            program_name=program.name,
        )
    })


class ProgramListView(BaseCommTrackManageView):
    urlname = 'commtrack_program_list'
    template_name = 'programs/manage/bootstrap3/programs.html'
    page_title = gettext_noop("Programs")

    @property
    def page_context(self):
        return {
            'program_product_options': {
                'total': 10,
                'start_page': 1,
                'limit': 10,
                'list_url': reverse('commtrack_program_fetch', args=[self.domain]),
            }
        }


class FetchProgramListView(ProgramListView):
    urlname = 'commtrack_program_fetch'

    @property
    def program_data(self):
        data = []
        programs = Program.by_domain(self.domain)
        for p in programs:
            info = p._doc
            info['is_default'] = info.pop('default')
            info['edit_url'] = reverse('commtrack_program_edit', kwargs={'domain': self.domain, 'prog_id': p._id})
            info['delete_url'] = reverse('delete_program', kwargs={'domain': self.domain, 'prog_id': p._id})
            data.append(info)
        return data

    def get(self, request, *args, **kwargs):
        return HttpResponse(json.dumps({
            'success': True,
            'data_list': self.program_data,
        }), 'text/json')


class NewProgramView(BaseCommTrackManageView):
    urlname = 'commtrack_program_new'
    page_title = gettext_noop("New Program")
    template_name = 'programs/manage/bootstrap3/program.html'

    @property
    @memoized
    def program(self):
        return Program(domain=self.domain)

    @property
    def parent_pages(self):
        return [{
            'title': ProgramListView.page_title,
            'url': reverse(ProgramListView.urlname, args=[self.domain]),
        }]

    @property
    @memoized
    def new_program_form(self):
        if self.request.method == 'POST':
            return ProgramForm(self.program, self.request.POST)
        return ProgramForm(self.program)

    @property
    def page_context(self):
        return {
            'program': self.program,
            'form': self.new_program_form,
        }

    def post(self, request, *args, **kwargs):
        if self.new_program_form.is_valid():
            self.new_program_form.save()
            messages.success(request, _("Program saved!"))
            return HttpResponseRedirect(reverse(ProgramListView.urlname, args=[self.domain]))
        return self.get(request, *args, **kwargs)


class EditProgramView(NewProgramView):
    urlname = 'commtrack_program_edit'
    page_title = gettext_noop("Edit Program")

    DEFAULT_LIMIT = 10

    @property
    def page(self):
        return self.request.GET.get('page', 1)

    @property
    def limit(self):
        return self.request.GET.get('limit', self.DEFAULT_LIMIT)

    @property
    def page_context(self):
        return {
            'program': self.program,
            'has_data_list': True,
            'pagination_limit_options': list(range(self.DEFAULT_LIMIT, 51, self.DEFAULT_LIMIT)),
            'form': self.new_program_form,
            'program_product_options': {
                'total': self.program.get_products_count(),
                'start_page': self.page,
                'limit': self.limit,
                'list_url': reverse('commtrack_product_for_program_fetch',
                                    args=[self.domain, self.program.get_id]),
            },
        }

    @property
    def program_id(self):
        try:
            return self.kwargs['prog_id']
        except KeyError:
            raise Http404()

    @property
    @memoized
    def program(self):
        try:
            return Program.get(self.program_id)
        except ResourceNotFound:
            raise Http404()

    @property
    def page_name(self):
        return _("Edit %s") % self.program.name

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.program_id])


class FetchProductForProgramListView(EditProgramView):
    urlname = 'commtrack_product_for_program_fetch'

    def get_product_data(self):
        start = (int(self.page) - 1) * int(self.limit)
        end = start + int(self.limit)
        queryset = SQLProduct.objects.filter(domain=self.domain,
                                             program_id=self.program_id)
        for product in queryset[start:end]:
            yield {
                'name': product.name,
                'code': product.code,
                'description': product.description,
                'unit': product.units,
            }

    def get(self, request, *args, **kwargs):
        return HttpResponse(json.dumps({
            'success': True,
            'current_page': self.page,
            'data_list': list(self.get_product_data()),
        }), 'text/json')
