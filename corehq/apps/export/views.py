from datetime import datetime
from couchdbkit import ResourceNotFound
from django.contrib import messages
from django.core.exceptions import SuspiciousOperation
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponseBadRequest, Http404
from django.utils.decorators import method_decorator
import json
from corehq.apps.export.custom_export_helpers import CustomExportHelper
from corehq.apps.export.exceptions import ExportNotFound, ExportAppException
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.standard.export import ExcelExportReport, CaseExportReport
from corehq.apps.settings.views import BaseProjectDataView
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from couchexport.models import SavedExportSchema, ExportSchema
from couchexport.schema import build_latest_schema
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from dimagi.utils.logging import notify_exception
from dimagi.utils.parsing import json_format_date
from dimagi.utils.web import json_response

require_form_export_permission = require_permission(
    Permissions.view_report,
    'corehq.apps.reports.standard.export.ExcelExportReport',
    login_decorator=None
)


class BaseExportView(BaseProjectDataView):
    template_name = 'export/customize_export.html'
    export_type = None
    is_async = True

    @property
    def parent_pages(self):
        return [{
            'title': self.report_class.name,
            'url': self.export_home_url,
        }]

    @method_decorator(require_form_export_permission)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseExportView, self).dispatch(request, *args, **kwargs)

    @property
    def export_helper(self):
        raise NotImplementedError("You must implement export_helper!")

    @property
    def export_home_url(self):
        return self.report_class.get_url(domain=self.domain)

    @property
    @memoized
    def report_class(self):
        try:
            return {
                'form': ExcelExportReport,
                'case': CaseExportReport
            }[self.export_type]
        except KeyError:
            raise SuspiciousOperation

    @property
    def page_context(self):
        return self.export_helper.get_context()

    def commit(self, request):
        raise NotImplementedError('Subclasses must implement a commit method.')

    def post(self, request, *args, **kwargs):
        try:
            self.commit(request)
        except Exception, e:
            if self.is_async:
                # todo: this can probably be removed as soon as
                # http://manage.dimagi.com/default.asp?157713 is resolved
                notify_exception(request, 'problem saving an export! {}'.format(str(e)))
                response = json_response({
                    'error': str(e) or type(e).__name__
                })
                response.status_code = 500
                return response
            elif isinstance(e, ExportAppException):
                return HttpResponseRedirect(request.META['HTTP_REFERER'])
            else:
                raise
        else:
            if self.is_async:
                return json_response({
                    'redirect': self.export_home_url,
                })
            return HttpResponseRedirect(self.export_home_url)


class BaseCreateCustomExportView(BaseExportView):
    # this view likely needs a lot more cleanup. will leave that for a later time...

    @property
    @memoized
    def export_helper(self):
        return CustomExportHelper.make(self.request, self.export_type, domain=self.domain)

    def commit(self, request):
        self.export_helper.update_custom_export()
        messages.success(request, _("Custom export created!"))

    def get(self, request, *args, **kwargs):
        # just copying what was in the old django view here. don't want to mess too much with exports just yet.
        try:
            export_tag = [self.domain, json.loads(request.GET.get("export_tag", "null") or "null")]
        except ValueError:
            return HttpResponseBadRequest()

        schema = build_latest_schema(export_tag)

        if not schema and self.export_helper.export_type == "form":
            schema = create_basic_form_checkpoint(export_tag)

        if request.GET.get('minimal', False):
            messages.warning(request,
                _("Warning you are using minimal mode, some things may not be functional"))

        if schema:
            app_id = request.GET.get('app_id')
            self.export_helper.custom_export = self.export_helper.ExportSchemaClass.default(
                schema=schema,
                name="%s: %s" % (
                    xmlns_to_name(self.domain, export_tag[1], app_id=app_id)
                        if self.export_helper.export_type == "form" else export_tag[1],
                    json_format_date(datetime.utcnow())
                ),
                type=self.export_helper.export_type
            )
            if self.export_helper.export_type in ['form', 'case']:
                self.export_helper.custom_export.app_id = app_id
            if self.export_helper.export_type == 'form':
                self.export_helper.custom_export.update_question_schema()

            return super(BaseCreateCustomExportView, self).get(request, *args, **kwargs)

        messages.warning(request, _("<strong>No data found for that form "
                                    "(%s).</strong> Submit some data before creating an export!") %
                         xmlns_to_name(self.domain, export_tag[1], app_id=None), extra_tags="html")
        return HttpResponseRedirect(ExcelExportReport.get_url(domain=self.domain))


class CreateCustomFormExportView(BaseCreateCustomExportView):
    urlname = 'custom_export_form'
    page_title = ugettext_lazy("Create Custom Form Export")
    export_type = 'form'


class CreateCustomCaseExportView(BaseCreateCustomExportView):
    urlname = 'custom_export_case'
    page_title = ugettext_lazy("Create Custom Case Export")
    export_type = 'case'


class BaseModifyCustomExportView(BaseExportView):

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.export_id])

    @property
    def export_id(self):
        return self.kwargs.get('export_id')

    @property
    @memoized
    def export_helper(self):
        try:
            return CustomExportHelper.make(self.request, self.export_type, self.domain, self.export_id)
        except ResourceNotFound:
            raise Http404()


class BaseEditCustomExportView(BaseModifyCustomExportView):

    def commit(self, request):
        self.export_helper.update_custom_export()
        messages.success(request, _("Custom export saved!"))


class EditCustomFormExportView(BaseEditCustomExportView):
    urlname = 'edit_custom_export_form'
    page_title = ugettext_noop("Edit Form Custom Export")
    export_type = 'form'


class EditCustomCaseExportView(BaseEditCustomExportView):
    urlname = 'edit_custom_export_case'
    page_title = ugettext_noop("Edit Case Custom Export")
    export_type = 'case'


class DeleteCustomExportView(BaseModifyCustomExportView):
    urlname = 'delete_custom_export'
    http_method_names = ['post']
    is_async = False

    def commit(self, request):
        try:
            saved_export = SavedExportSchema.get(self.export_id)
        except ResourceNotFound:
            raise ExportNotFound()
        self.export_type = saved_export.type
        saved_export.delete()
        messages.success(request, _("Custom export was deleted."))


BASIC_FORM_SCHEMA = {
    "doc_type": "string",
    "domain": "string",
    "xmlns": "string",
    "form": {
        "@xmlns": "string",
        "@uiVersion": "string",
        "@name": "string",
        "#type": "string",
        "meta": {
            "@xmlns": "string",
            "username": "string",
            "instanceID": "string",
            "userID": "string",
            "timeEnd": "string",
            "appVersion": {
                "@xmlns": "string",
                "#text": "string"
            },
            "timeStart": "string",
            "deviceID": "string"
        },
        "@version": "string"
    },
    "partial_submission": "string",
    "_rev": "string",
    "#export_tag": [
       "string"
    ],
    "received_on": "string",
    "app_id": "string",
    "last_sync_token": "string",
    "submit_ip": "string",
    "computed_": {
    },
    "openrosa_headers": {
       "HTTP_DATE": "string",
       "HTTP_ACCEPT_LANGUAGE": "string",
       "HTTP_X_OPENROSA_VERSION": "string"
    },
    "date_header": "string",
    "path": "string",
    "computed_modified_on_": "string",
    "_id": "string"
}


def create_basic_form_checkpoint(index):
    checkpoint = ExportSchema(
        schema=BASIC_FORM_SCHEMA,
        timestamp=datetime(1970, 1, 1),
        index=index,
    )
    checkpoint.save()
    return checkpoint
