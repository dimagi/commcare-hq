import json
from couchdbkit import ResourceNotFound
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.contrib import messages
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.web import json_response
from django.views.decorators.http import require_POST
from django.utils.translation import ugettext as _, ugettext_noop
from django.core.urlresolvers import reverse
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.commtrack.views import BaseCommTrackManageView
from corehq.apps.products.models import SQLProduct
from corehq.apps.programs.models import Program
from corehq.apps.programs.forms import ProgramForm


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
    template_name = 'programs/manage/programs.html'
    page_title = ugettext_noop("Programs")


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
    page_title = ugettext_noop("New Program")
    template_name = 'programs/manage/program.html'

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
    page_title = ugettext_noop("Edit Program")

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
            'data_list': {
                'page': self.page,
                'limit': self.limit,
                'total': self.program.get_products_count(),
            },
            'pagination_limit_options': range(self.DEFAULT_LIMIT, 51, self.DEFAULT_LIMIT),
            'form': self.new_program_form,
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
