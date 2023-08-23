from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop, gettext_lazy
from memoized import memoized

from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.models import cached_property
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.email.forms import InitiateAddEmailBackendForm
from corehq.apps.email.models import SQLEmailSMTPBackend
from corehq.apps.email.util import get_email_backend_classes
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.sms.util import is_superuser_or_contractor


class BaseMessagingSectionView(BaseDomainView):
    section_name = gettext_noop("Messaging")

    @cached_property
    def is_system_admin(self):
        return is_superuser_or_contractor(self.request.couch_user)

    def dispatch(self, request, *args, **kwargs):
        return super(BaseMessagingSectionView, self).dispatch(request, *args, **kwargs)

    @property
    def section_url(self):
        return reverse("email_default", args=[self.domain])


class DomainEmailGatewayListView(CRUDPaginatedViewMixin, BaseMessagingSectionView):
    template_name = "email/gateway_list.html"
    urlname = 'list_domain_email_backends'
    page_title = gettext_noop("Email Connectivity")
    strict_domain_fetching = True

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(DomainEmailGatewayListView, self).dispatch(request, *args, **kwargs)

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    @memoized
    def total(self):
        return SQLEmailSMTPBackend.get_domain_backends(self.domain, count_only=True)

    @property
    def column_names(self):
        return [
            _("Gateway"),
            _("Description"),
            _("Status"),
            _("Actions"),
        ]

    @property
    def page_context(self):
        mappings = SQLEmailSMTPBackend.objects.filter(
            domain=self.domain,
        )
        # extra_backend_mappings = {
        #     mapping.prefix: mapping.backend.name
        #     for mapping in mappings if mapping.prefix != '*'
        # }

        extra_backend_mappings = {}

        context = self.pagination_context
        #context = {}

        context.update({
            'initiate_new_form': InitiateAddEmailBackendForm(
                user=self.request.couch_user,
                domain=self.domain
            ),
            'extra_backend_mappings': extra_backend_mappings,
            'is_system_admin': self.is_system_admin,
        })
        return context

    @property
    def paginated_list(self):
        backends = SQLEmailSMTPBackend.get_domain_backends(
            self.domain,
        )
        default_backend = SQLEmailSMTPBackend.get_domain_default_backend(
            self.domain
        )

        if len(backends) > 0 and not default_backend:
            yield {
                'itemData': {
                    'id': 'nodefault',
                    'name': "Automatic Choose",
                    'status': 'DEFAULT',
                },
                'template': 'gateway-automatic-template',
            }
        elif default_backend:
            yield {
                'itemData': self._fmt_backend_data(default_backend),
                'template': 'gateway-default-template',
            }

        default_backend_id = default_backend.pk if default_backend else None
        for backend in backends:
            if backend.pk != default_backend_id:
                yield {
                    'itemData': self._fmt_backend_data(backend),
                    'template': 'gateway-template',
                }

    def _fmt_backend_data(self, backend):
        is_editable = backend.domain == self.domain
        return {
            'id': backend.pk,
            'name': backend.name,
            'description': backend.description,
            'editUrl': reverse(
                EditDomainEmailGatewayView.urlname,
                args=[self.domain, backend.hq_api_id, backend.pk]
            ) if is_editable else "",
            'canDelete': is_editable,
            'deleteModalId': 'delete_%s' % backend.pk,
        }

    def _get_backend_from_item_id(self, item_id):
        try:
            item_id = int(item_id)
            backend = SQLEmailSMTPBackend.load(item_id)
            return item_id, backend
        except (SQLEmailSMTPBackend.DoesNotExist, TypeError, ValueError):
            raise Http404()

    def get_deleted_item_data(self, item_id):
        item_id, backend = self._get_backend_from_item_id(item_id)

        if backend.domain != self.domain:
            raise Http404()

        backend.delete()

        return {
            'itemData': self._fmt_backend_data(backend),
            'template': 'gateway-deleted-template',
        }

    def refresh_item(self, item_id):
        item_id, backend = self._get_backend_from_item_id(item_id)

        if not backend.domain_is_authorized(self.domain):
            raise Http404()

        domain_default_backend = SQLEmailSMTPBackend.get_domain_default_backend(
            self.domain,
            id_only=False
        )

        if domain_default_backend and domain_default_backend.id == item_id:
            SQLEmailSMTPBackend.unset_domain_default_backend(backend)
        else:
            SQLEmailSMTPBackend.set_to_domain_default_backend(domain_default_backend, backend)

    @property
    def allowed_actions(self):
        actions = super(DomainEmailGatewayListView, self).allowed_actions
        return actions + ['new_backend']

    def post(self, request, *args, **kwargs):
        if self.action == 'new_backend':
            hq_api_id = request.POST['hq_api_id']
            return HttpResponseRedirect(reverse(AddDomainEmailGatewayView.urlname, args=[self.domain, hq_api_id]))
        return self.paginate_crud_response


class AddDomainEmailGatewayView(BaseMessagingSectionView):
    urlname = 'add_domain_gateway'
    template_name = 'email/add_gateway.html'
    page_title = gettext_lazy("Add Email Gateway")

    @property
    @memoized
    def backend(self):
        return self.backend_class(
            domain=self.domain,
            hq_api_id=self.backend_class.get_api_id()
        )

    @property
    @memoized
    def hq_api_id(self):
        return self.kwargs.get('hq_api_id')

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.hq_api_id])

    @property
    def page_context(self):
        return {
            'form': self.backend_form,
            'button_text': self.button_text,
        }

    @property
    def button_text(self):
        return _(f"Create {self.backend_class.get_generic_name()} Gateway")

    @property
    @memoized
    def backend_class(self):
        backend_classes = get_email_backend_classes()
        try:
            return backend_classes[self.hq_api_id]
        except KeyError:
            raise Http404()

    @property
    @memoized
    def backend_form(self):
        form_class = self.backend_class.get_form_class()
        if self.request.method == 'POST':
            return form_class(
                self.request.POST,
                button_text=self.button_text,
                domain=self.domain,
                backend_id=None
            )
        return form_class(
            button_text=self.button_text,
            domain=self.domain,
            backend_id=None
        )

    @property
    def parent_pages(self):
        return [{
            'title': DomainEmailGatewayListView.page_title,
            'url': reverse(DomainEmailGatewayListView.urlname, args=[self.domain]),
        }]

    def redirect_to_gateway_list(self):
        return HttpResponseRedirect(reverse(DomainEmailGatewayListView.urlname, args=[self.domain]))

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        result = super(AddDomainEmailGatewayView, self).dispatch(request, *args, **kwargs)
        return result

    def post(self, request, *args, **kwargs):
        if self.backend_form.is_valid():
            self.backend.name = self.backend_form.cleaned_data.get('name')
            self.backend.display_name = self.backend_form.cleaned_data.get('display_name')
            self.backend.description = self.backend_form.cleaned_data.get('description')

            self.backend.username = self.backend_form.cleaned_data.get('username')
            self.backend.password = self.backend_form.cleaned_data.get('password')
            self.backend.server = self.backend_form.cleaned_data.get('server')
            self.backend.port = self.backend_form.cleaned_data.get('port')

            extra_fields = {}
            for key, value in self.backend_form.cleaned_data.items():
                if key in self.backend.get_available_extra_fields():
                    extra_fields[key] = value
            self.backend.set_extra_fields(**extra_fields)

            self.backend.save()
            return self.redirect_to_gateway_list()
        return self.get(request, *args, **kwargs)


class EditDomainEmailGatewayView(AddDomainEmailGatewayView):
    urlname = 'edit_domain_gateway'
    page_title = gettext_lazy("Edit Email Gateway")

    @property
    def backend_id(self):
        return self.kwargs['backend_id']

    @property
    @memoized
    def backend(self):
        try:
            backend = self.backend_class.objects.get(pk=self.backend_id)
        except Exception:
            raise Http404()
        if (backend.domain != self.domain
            or backend.hq_api_id != self.backend_class.get_api_id()
        ):
            raise Http404()
        return backend

    @property
    @memoized
    def backend_form(self):
        form_class = self.backend_class.get_form_class()
        initial = {
            'name': self.backend.name,
            'display_name': self.backend.display_name,
            'description': self.backend.description,
            'username': self.backend.username,
            'password': self.backend.password,
            'server': self.backend.server,
            'port': self.backend.port,
        }
        initial.update(self.backend.get_extra_fields())

        if self.request.method == 'POST':
            return form_class(
                self.request.POST,
                initial=initial,
                button_text=self.button_text,
                domain=self.domain,
                backend_id=self.backend.pk
            )
        return form_class(
            initial=initial,
            button_text=self.button_text,
            domain=self.domain,
            backend_id=self.backend.pk
        )

    @property
    def page_name(self):
        return _("Edit %s Gateway") % self.backend_class.get_generic_name()

    @property
    def button_text(self):
        return _("Update %s Gateway") % self.backend_class.get_generic_name()

    @property
    def page_url(self):
        return reverse(self.urlname, kwargs=self.kwargs)
