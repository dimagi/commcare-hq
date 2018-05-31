from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import itertools
import six.moves.html_parser
import json
import socket
import uuid
from io import StringIO
from collections import defaultdict, namedtuple, OrderedDict, Counter
from datetime import timedelta, date, datetime

import dateutil
from couchdbkit import ResourceNotFound
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.core import management, cache
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import mail_admins
from django.http import (
    HttpResponseRedirect,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
    JsonResponse,
    StreamingHttpResponse,
)
from django.http.response import Http404
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import ugettext as _, ugettext_lazy
from django.views.decorators.http import require_POST
from django.views.generic import FormView, TemplateView, View
from lxml import etree
from lxml.builder import E
from restkit import Resource
from restkit.errors import Unauthorized

from casexml.apps.case.models import CommCareCase
from casexml.apps.phone.xml import SYNC_XMLNS
from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS
from corehq.apps.app_manager.models import ApplicationBase
from corehq.apps.callcenter.indicator_sets import CallCenterIndicators
from corehq.apps.callcenter.utils import CallCenterCase
from corehq.apps.data_analytics.admin import MALTRowAdmin
from corehq.apps.data_analytics.const import GIR_FIELDS
from corehq.apps.data_analytics.models import MALTRow, GIRRow
from corehq.apps.domain.auth import basicauth
from corehq.apps.domain.decorators import (
    require_superuser, require_superuser_or_contractor,
    login_or_basic, domain_admin_required,
    check_lockout)
from corehq.apps.domain.models import Domain
from corehq.apps.es import filters
from corehq.apps.es.domains import DomainES
from corehq.apps.hqadmin.reporting.exceptions import HistoTypeNotFoundException
from corehq.apps.hqadmin.service_checks import run_checks
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.apps.locations.models import SQLLocation
from corehq.apps.ota.views import get_restore_response, get_restore_params
from corehq.apps.hqwebapp.decorators import use_datatables, use_jquery_ui, \
    use_nvd3_v3
from corehq.apps.users.models import CommCareUser, WebUser, CouchUser
from corehq.apps.users.util import format_username
from corehq.elastic import parse_args_for_es, run_query, ES_META
from corehq.form_processor.backends.couch.dbaccessors import CaseAccessorCouch
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.exceptions import XFormNotFound, CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL
from corehq.form_processor.serializers import XFormInstanceSQLRawDocSerializer, \
    CommCareCaseSQLRawDocSerializer
from corehq.toggles import any_toggle_enabled, SUPPORT
from corehq.util import reverse
from corehq.util.couchdb_management import couch_config
from corehq.util.supervisord.api import (
    PillowtopSupervisorApi,
    SupervisorException,
    all_pillows_supervisor_status,
    pillow_supervisor_status
)
from corehq.util.timer import TimingContext
from couchforms.models import XFormInstance
from couchforms.openrosa_response import RESPONSE_XMLNS
from dimagi.utils.couch.database import get_db, is_bigcouch
from dimagi.utils.csv import UnicodeWriter
from dimagi.utils.dates import add_months
from dimagi.utils.decorators.datespan import datespan_in_request
from memoized import memoized
from dimagi.utils.django.email import send_HTML_email
from dimagi.utils.django.management import export_as_csv_action
from dimagi.utils.parsing import json_format_date
from dimagi.utils.web import json_response
from corehq.apps.hqadmin.tasks import send_mass_emails
from pillowtop.exceptions import PillowNotFoundError
from pillowtop.utils import get_all_pillows_json, get_pillow_json, get_pillow_config_by_name
from corehq.apps.hqadmin import service_checks, escheck
from corehq.apps.hqadmin.forms import (
    AuthenticateAsForm, BrokenBuildsForm, EmailForm, SuperuserManagementForm,
    ReprocessMessagingCaseUpdatesForm,
    DisableTwoFactorForm, DisableUserForm)
from corehq.apps.hqadmin.history import get_recent_changes, download_changes
from corehq.apps.hqadmin.models import HqDeploy
from corehq.apps.hqadmin.reporting.reports import get_project_spaces, get_stats_data, HISTO_TYPE_TO_FUNC
from corehq.apps.hqadmin.utils import get_celery_stats
import six
from six.moves import filter


@require_superuser
def default(request):
    return HttpResponseRedirect(reverse('admin_report_dispatcher', args=('domains',)))


def get_hqadmin_base_context(request):
    return {
        "domain": None,
    }


class BaseAdminSectionView(BaseSectionPageView):
    section_name = ugettext_lazy("Admin Reports")

    @property
    def section_url(self):
        return reverse('default_admin_report')

    @property
    def page_url(self):
        return reverse(self.urlname)
