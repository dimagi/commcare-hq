from urlparse import urlparse
from datetime import datetime
import logging
import json
import os
import re
import sys
import traceback
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import cache
from django.core.cache import InvalidCacheBackendError
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.views import login as django_login
from django.contrib.auth.views import logout as django_logout
from django.http import HttpResponseRedirect, HttpResponse, Http404,\
    HttpResponseServerError, HttpResponseNotFound, HttpResponseBadRequest,\
    HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.generic import TemplateView
from couchdbkit import ResourceNotFound
from django.utils.translation import ugettext as _, ugettext_noop
from django.core.urlresolvers import reverse
from django.core.mail.message import EmailMessage
from django.template import loader
from django.template.context import RequestContext
from restkit import Resource

from corehq.apps.accounting.models import Subscription
from corehq.apps.domain.decorators import require_superuser, login_and_domain_required
from corehq.apps.domain.utils import normalize_domain_name, get_domain_from_url
from corehq.apps.dropbox.decorators import require_dropbox_session
from corehq.apps.dropbox.models import DropboxUploadHelper
from corehq.apps.dropbox.views import DROPBOX_ACCESS_TOKEN
from corehq.apps.dropbox.exceptions import DropboxUploadAlreadyInProgress
from corehq.apps.hqwebapp.encoders import LazyEncoder
from corehq.apps.hqwebapp.forms import EmailAuthenticationForm, CloudCareAuthenticationForm
from corehq.apps.receiverwrapper.models import Repeater
from corehq.apps.reports.util import is_mobile_worker_with_report_access
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import format_username
from corehq.apps.hqwebapp.doc_info import get_doc_info
from corehq.util.cache_utils import ExponentialBackoff
from corehq.util.context_processors import get_domain_type
from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.logging import notify_exception, notify_js_exception
from dimagi.utils.web import get_url_base, json_response, get_site_domain
from corehq.apps.domain.models import Domain
from couchforms.models import XFormInstance
from soil import heartbeat, DownloadBase
from soil import views as soil_views


def pg_check():
    """check django db"""
    try:
        a_user = User.objects.all()[:1].get()
    except:
        a_user = None
    return (a_user is not None, None)


def couch_check():
    """check couch"""

    #in reality when things go wrong with couch and postgres (as of this
    # writing) - it's far from graceful, so this will # likely never be
    # reached because another exception will fire first - but for
    # completeness  sake, this check is done  here to verify our calls will
    # work, and if other error handling allows the request to get this far.

    try:
        xforms = XFormInstance.view('reports_forms/all_forms', limit=1).all()
    except:
        xforms = None
    return (isinstance(xforms, list), None)


def celery_check():
    try:
        from celery import Celery
        from django.conf import settings
        app = Celery()
        app.config_from_object(settings)
        i = app.control.inspect()
        ping = i.ping()
        if not ping:
            chk = (False, 'No running Celery workers were found.')
        else:
            chk = (True, None)
    except IOError as e:
        chk = (False, "Error connecting to the backend: " + str(e))
    except ImportError as e:
        chk = (False, str(e))

    return chk


def hb_check():
    celery_monitoring = getattr(settings, 'CELERY_FLOWER_URL', None)
    if celery_monitoring:
        try:
            cresource = Resource(celery_monitoring, timeout=3)
            t = cresource.get("api/workers").body_string()
            all_workers = json.loads(t)
            bad_workers = []
            for hostname, w in all_workers.items():
                if not w['status']:
                    bad_workers.append('* {} celery worker down'.format(hostname))
            if bad_workers:
                return (False, '\n'.join(bad_workers))
            else:
                hb = heartbeat.is_alive()
        except:
            hb = False
    else:
        try:
            hb = heartbeat.is_alive()
        except:
            hb = False
    return (hb, None)


def redis_check():
    try:
        redis = cache.get_cache('redis')
        result = redis.set('serverup_check_key', 'test')
    except (InvalidCacheBackendError, ValueError):
        result = True  # redis not in use, ignore
    except:
        result = False
    return (result, None)


def server_error(request, template_name='500.html'):
    """
    500 error handler.
    """

    domain = get_domain_from_url(request.path) or ''


    # hat tip: http://www.arthurkoziel.com/2009/01/15/passing-mediaurl-djangos-500-error-view/
    t = loader.get_template(template_name)
    type, exc, tb = sys.exc_info()
    return HttpResponseServerError(t.render(RequestContext(request,
        {'MEDIA_URL': settings.MEDIA_URL,
         'STATIC_URL': settings.STATIC_URL,
         'domain': domain,
         '500traceback': ''.join(traceback.format_tb(tb)),
        })))


def not_found(request, template_name='404.html'):
    """
    404 error handler.
    """
    t = loader.get_template(template_name)
    return HttpResponseNotFound(t.render(RequestContext(request,
        {'MEDIA_URL': settings.MEDIA_URL,
         'STATIC_URL': settings.STATIC_URL
        })))


def redirect_to_default(req, domain=None):
    if not req.user.is_authenticated():
        if domain != None:
            url = reverse('domain_login', args=[domain])
        else:
            if settings.ENABLE_PRELOGIN_SITE:
                try:
                    from corehq.apps.prelogin.views import HomePublicView
                    url = reverse(HomePublicView.urlname)
                except ImportError:
                    # this happens when the prelogin app is not included.
                    url = reverse('landing_page')
            else:
                url = reverse('landing_page')
    else:
        if domain:
            domain = normalize_domain_name(domain)
            domains = [Domain.get_by_name(domain)]
        else:
            domains = Domain.active_for_user(req.user)
        if 0 == len(domains) and not req.user.is_superuser:
            return redirect('registration_domain', domain_type=get_domain_type(None, req))
        elif 1 == len(domains):
            if domains[0]:
                domain = domains[0].name

                if (req.couch_user.is_commcare_user()
                    and not is_mobile_worker_with_report_access(
                        req.couch_user, domain)):
                    url = reverse("cloudcare_main", args=[domain, ""])
                else:
                    from corehq.apps.dashboard.views import dashboard_default
                    return dashboard_default(req, domain)

            else:
                raise Http404
        else:
            url = settings.DOMAIN_SELECT_URL
    return HttpResponseRedirect(url)


def landing_page(req, template_name="home.html"):
    # this view, and the one below, is overridden because
    # we need to set the base template to use somewhere
    # somewhere that the login page can access it.
    if req.user.is_authenticated():
        return HttpResponseRedirect(reverse('homepage'))
    req.base_template = settings.BASE_TEMPLATE
    return django_login(req, template_name=template_name, authentication_form=EmailAuthenticationForm)


def yui_crossdomain(req):
    x_domain = """<?xml version="1.0"?>
<!DOCTYPE cross-domain-policy SYSTEM "http://www.macromedia.com/xml/dtds/cross-domain-policy.dtd">
<cross-domain-policy>
    <allow-access-from domain="yui.yahooapis.com"/>
    <allow-access-from domain="%s"/>
    <site-control permitted-cross-domain-policies="master-only"/>
</cross-domain-policy>""" % get_site_domain()
    return HttpResponse(x_domain, content_type="application/xml")


@login_required()
def password_change(req):
    user_to_edit = User.objects.get(id=req.user.id)
    if req.method == 'POST':
        password_form = AdminPasswordChangeForm(user_to_edit, req.POST)
        if password_form.is_valid():
            password_form.save()
            return HttpResponseRedirect('/')
    else:
        password_form = AdminPasswordChangeForm(user_to_edit)
    template_name = "password_change.html"
    return render(req, template_name, {"form": password_form})


def server_up(req):
    '''
    Hit serverup.txt to check any of the below item with always_check: True
    Hit serverup.txt?celery (or heartbeat) to check a specific service
    View that just returns "success", which can be hooked into server monitoring tools like: pingdom
    '''


    checkers = {
        "heartbeat": {
            "always_check": False,
            "message": "* celery heartbeat is down",
            "check_func": hb_check
        },
        "celery": {
            "always_check": False,
            "message": "* celery is down",
            "check_func": celery_check
        },
        "postgres": {
            "always_check": True,
            "message": "* postgres has issues",
            "check_func": pg_check
        },
        "couch": {
            "always_check": True,
            "message": "* couch has issues",
            "check_func": couch_check
        },
        "redis": {
            "always_check": True,
            "message": "* redis has issues",
            "check_func": redis_check
        },
    }

    failed = False
    message = ['Problems with HQ (%s):' % os.uname()[1]]
    for check, check_info in checkers.items():
        if check_info['always_check'] or req.GET.get(check, None) is not None:
            check_results, custom_msg = check_info['check_func']()
            if not check_results:
                failed = True
                if custom_msg:
                    message.append(custom_msg)
                else:
                    message.append(check_info['message'])
    if failed:
        return HttpResponse('<br>'.join(message), status=500)
    else:
        return HttpResponse("success")

def no_permissions(request, redirect_to=None, template_name="403.html"):
    """
    403 error handler.
    """
    t = loader.get_template(template_name)
    return HttpResponseForbidden(t.render(RequestContext(request,
        {'MEDIA_URL': settings.MEDIA_URL,
         'STATIC_URL': settings.STATIC_URL
        })))


def csrf_failure(request, reason=None, template_name="csrf_failure.html"):
    t = loader.get_template(template_name)
    return HttpResponseForbidden(
        t.render(RequestContext(
            request,
            {'MEDIA_URL': settings.MEDIA_URL,
             'STATIC_URL': settings.STATIC_URL
             })))


def _login(req, domain_name, template_name):

    if req.user.is_authenticated() and req.method != "POST":
        redirect_to = req.REQUEST.get('next', '')
        if redirect_to:
            return HttpResponseRedirect(redirect_to)
        if not domain_name:
            return HttpResponseRedirect(reverse('homepage'))
        else:
            return HttpResponseRedirect(reverse('domain_homepage', args=[domain_name]))

    if req.method == 'POST' and domain_name and '@' not in req.POST.get('username', '@'):
        req.POST._mutable = True
        req.POST['username'] = format_username(req.POST['username'], domain_name)
        req.POST._mutable = False

    req.base_template = settings.BASE_TEMPLATE

    context = {}
    if domain_name:
        domain = Domain.get_by_name(domain_name)
        context.update({
            'domain': domain_name,
            'hr_name': domain.display_name() if domain else domain_name,
            'next': req.REQUEST.get('next', '/a/%s/' % domain),
        })

    authentication_form = EmailAuthenticationForm if not domain_name else CloudCareAuthenticationForm
    return django_login(req, template_name=template_name,
                        authentication_form=authentication_form,
                        extra_context=context)


def login(req, domain_type='commcare'):
    # this view, and the one below, is overridden because
    # we need to set the base template to use somewhere
    # somewhere that the login page can access it.
    domain = req.REQUEST.get('domain', None)

    from corehq.apps.domain.utils import get_dummy_domain
    # For showing different logos based on CommTrack, CommConnect, CommCare...
    dummy_domain = get_dummy_domain(domain_type)
    req.project = dummy_domain

    return _login(req, domain, "login_and_password/login.html")


def domain_login(req, domain, template_name="login_and_password/login.html"):
    project = Domain.get_by_name(domain)
    if not project:
        raise Http404

    # FYI, the domain context_processor will pick this up and apply the
    # necessary domain contexts:
    req.project = project

    return _login(req, domain, template_name)


def is_mobile_url(url):
    # Minor hack
    return ('reports/custom/mobile' in url)

def logout(req):
    referer = req.META.get('HTTP_REFERER')
    domain = get_domain_from_url(urlparse(referer).path) if referer else None

    # we don't actually do anything with the response here:
    django_logout(req, **{"template_name": settings.BASE_TEMPLATE})

    if referer and domain and is_mobile_url(referer):
        mobile_mainnav_url = reverse('custom_project_report_dispatcher', args=[domain, 'mobile/mainnav'])
        mobile_login_url = reverse('domain_mobile_login', kwargs={'domain': domain})
        return HttpResponseRedirect('%s?next=%s' % (mobile_login_url, mobile_mainnav_url))
    elif referer and domain:
        domain_login_url = reverse('domain_login', kwargs={'domain': domain})
        return HttpResponseRedirect('%s' % domain_login_url)
    else:
        return HttpResponseRedirect(reverse('login'))

@login_and_domain_required
def retrieve_download(req, domain, download_id, template="style/includes/file_download.html"):
    return soil_views.retrieve_download(req, download_id, template)


def dropbox_next_url(request, download_id):
    return request.META.get('HTTP_REFERER', '/')


@login_required
@require_dropbox_session(next_url=dropbox_next_url)
def dropbox_upload(request, download_id):
    download = DownloadBase.get(download_id)
    if download is None:
        logging.error("Download file request for expired/nonexistent file requested")
        raise Http404
    else:
        filename = download.get_filename()
        # Hack to get target filename from content disposition
        match = re.search('filename="([^"]*)"', download.content_disposition)
        dest = match.group(1) if match else 'download.txt'

        try:
            uploader = DropboxUploadHelper.create(
                request.session.get(DROPBOX_ACCESS_TOKEN),
                src=filename,
                dest=dest,
                download_id=download_id,
                user=request.user,
            )
        except DropboxUploadAlreadyInProgress:
            uploader = DropboxUploadHelper.objects.get(download_id=download_id)
            messages.warning(
                request,
                u'The file is in the process of being synced to dropbox! It is {0:.2f}% '
                'complete.'.format(uploader.progress * 100)
            )
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))

        uploader.upload()

        messages.success(
            request,
            _(u"Apps/{app}/{dest} is queued to sync to dropbox! You will receive an email when it"
                " completes.".format(app=settings.DROPBOX_APP_NAME, dest=dest))
        )

    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))


@require_superuser
def debug_notify(request):
    try:
        0 / 0
    except ZeroDivisionError:
        notify_exception(request,
            "If you want to achieve a 500-style email-out but don't want the user to see a 500, use notify_exception(request[, message])")
    return HttpResponse("Email should have been sent")


@require_POST
def jserror(request):
    stack = request.POST.get('stack', None)
    message = request.POST.get('message', None)
    if stack:
        cache_key = ' '.join(map(lambda l: l.strip(), stack.split('\n'))[:3])
    else:
        cache_key = message

    count = ExponentialBackoff.increment(cache_key)
    if not ExponentialBackoff.should_backoff(cache_key):
        notify_js_exception(
            request,
            message=message,
            details={
                'filename': request.POST.get('filename', None),
                'line': request.POST.get('line', None),
                'page': request.POST.get('page', None),
                'agent': request.META.get('HTTP_USER_AGENT', None),
                'js_stack': stack,
                'count': count,
            }
        )

    return HttpResponse('')


@login_required()
@require_POST
def bug_report(req):
    report = dict([(key, req.POST.get(key, '')) for key in (
        'subject',
        'username',
        'domain',
        'url',
        'message',
        'app_id',
        'cc',
        'email',
        '500traceback',
    )])

    report['user_agent'] = req.META['HTTP_USER_AGENT']
    report['datetime'] = datetime.utcnow()

    try:
        couch_user = CouchUser.get_by_username(report['username'])
        full_name = couch_user.full_name
        if couch_user.is_commcare_user():
            email = report['email']
        else:
            email = couch_user.get_email()
    except Exception:
        full_name = None
        email = report['email']
    report['full_name'] = full_name
    report['email'] = email or report['username']

    matching_subscriptions = Subscription.objects.filter(
        is_active=True,
        subscriber__domain=report['domain'],
    )

    if len(matching_subscriptions) >= 1:
        report['software_plan'] = matching_subscriptions[0].plan_version
    else:
        report['software_plan'] = u'domain has no active subscription'

    subject = u'{subject} ({domain})'.format(**report)
    message = (
        u"username: {username}\n"
        u"full name: {full_name}\n"
        u"domain: {domain}\n"
        u"software plan: {software_plan}\n"
        u"url: {url}\n"
        u"datetime: {datetime}\n"
        u"User Agent: {user_agent}\n"
        u"Message:\n\n"
        u"{message}\n"
        ).format(**report)
    cc = report['cc'].strip().split(",")
    cc = filter(None, cc)

    if full_name and not any([c in full_name for c in '<>"']):
        reply_to = u'"{full_name}" <{email}>'.format(**report)
    else:
        reply_to = report['email']

    # if the person looks like a commcare user, fogbugz can't reply
    # to their email, so just use the default
    if settings.HQ_ACCOUNT_ROOT in reply_to:
        reply_to = settings.SERVER_EMAIL

    if req.POST.get('five-hundred-report'):
        extra_message = ("This messge was reported from a 500 error page! "
                         "Please fix this ASAP (as if you wouldn't anyway)...")
        traceback_info = "Traceback of this 500: \n%s" % report['500traceback']
        message = "%s \n\n %s \n\n %s" % (message, extra_message, traceback_info)

    email = EmailMessage(
        subject=subject,
        body=message,
        to=settings.BUG_REPORT_RECIPIENTS,
        headers={'Reply-To': reply_to},
        cc=cc
    )

    uploaded_file = req.FILES.get('report_issue')
    if uploaded_file:
        filename = uploaded_file.name
        content = uploaded_file.read()
        email.attach(filename=filename, content=content)

    # only fake the from email if it's an @dimagi.com account
    if re.search('@dimagi\.com$', report['username']):
        email.from_email = report['username']
    else:
        email.from_email = settings.CCHQ_BUG_REPORT_EMAIL

    email.send(fail_silently=False)

    if req.POST.get('five-hundred-report'):
        messages.success(req,
            "Your CommCare HQ Issue Report has been sent. We are working quickly to resolve this problem.")
        return HttpResponseRedirect(reverse('homepage'))

    return HttpResponse()


def render_static(request, template):
    """
    Takes an html file and renders it Commcare HQ's styling
    """
    return render(request, "style/bootstrap2/blank.html", {'tmpl': template})


def eula(request):
    return render_static(request, "eula.html")

def cda(request):
    return render_static(request, "cda.html")

def apache_license(request):
    return render_static(request, "apache_license.html")

def bsd_license(request):
    return render_static(request, "bsd_license.html")


def product_agreement(request):
    return render_static(request, "product_agreement.html")


def unsubscribe(request, user_id):
    # todo in the future we should not require a user to be logged in to unsubscribe.
    from django.contrib import messages
    from corehq.apps.settings.views import MyAccountSettingsView
    messages.info(request,
                  _('Check "Opt out of emails about new features '
                    'and other CommCare updates" in your account '
                    'settings and then click "Update Information" '
                    'if you do not want to receive future emails '
                    'from us.'))
    return HttpResponseRedirect(reverse(MyAccountSettingsView.urlname))


class BasePageView(TemplateView):
    urlname = None  # name of the view used in urls
    page_title = None  # what shows up in the <title>
    template_name = 'style/bootstrap2/base_page.html'

    @property
    def page_name(self):
        """
        This is what is visible to the user.
        page_title is what shows up in <title> tags.
        """
        return self.page_title

    @property
    def page_url(self):
        raise NotImplementedError()

    @property
    def parent_pages(self):
        """
        Specify parent pages as a list of
        [{
            'title': <name>,
            'url: <url>,
        }]
        """
        return []

    @property
    def main_context(self):
        """
        The shared context for rendering this page.
        """
        return {
            'current_page': {
                'page_name': self.page_name,
                'title': self.page_title,
                'url': self.page_url,
                'parents': self.parent_pages,
            },
        }

    @property
    def page_context(self):
        """
        The Context for the settings page
        """
        return {}

    def get_context_data(self, **kwargs):
        context = super(BasePageView, self).get_context_data(**kwargs)
        context.update(self.main_context)
        context.update(self.page_context)
        return context

    def render_to_response(self, context, **response_kwargs):
        """
        Returns a response with a template rendered with the given context.
        """
        return render(self.request, self.template_name, context)


class BaseSectionPageView(BasePageView):
    section_name = ""
    template_name = "style/bootstrap2/base_section.html"

    @property
    def section_url(self):
        raise NotImplementedError

    @property
    def main_context(self):
        context = super(BaseSectionPageView, self).main_context
        context.update({
            'section': {
                'page_name': self.section_name,
                'url': self.section_url,
            }
        })
        return context


class PaginatedItemException(Exception):
    pass


class CRUDPaginatedViewMixin(object):
    """
    Mix this in with a TemplateView view object.
    For usage tips, see the docs for UI Helpers > Paginated CRUD View.
    """
    DEFAULT_LIMIT = 10

    limit_text = ugettext_noop("items per page")
    empty_notification = ugettext_noop("You have no items.")
    loading_message = ugettext_noop("Loading...")
    deleted_items_header = ugettext_noop("Deleted Items:")
    new_items_header = ugettext_noop("New Items:")

    def _safe_escape(self, expression, default):
        try:
            return expression()
        except ValueError:
            return default

    @property
    def parameters(self):
        """
        Specify GET or POST from a request object.
        """
        raise NotImplementedError("you need to implement get_param_source")

    @property
    @memoized
    def page(self):
        return self._safe_escape(
            lambda: int(self.parameters.get('page', 1)),
            1
        )

    @property
    @memoized
    def limit(self):
        return self._safe_escape(
            lambda: int(self.parameters.get('limit', self.DEFAULT_LIMIT)),
            self.DEFAULT_LIMIT
        )

    @property
    def total(self):
        raise NotImplementedError("You must implement total.")

    @property
    def sort_by(self):
        return self.parameters.GET.get('sortBy', 'abc')

    @property
    def skip(self):
        return (self.page - 1) * self.limit

    @property
    def action(self):
        action = self.parameters.get('action')
        if action not in self.allowed_actions:
            raise Http404()
        return action

    @property
    def column_names(self):
        raise NotImplementedError("you must return a list of column names")

    @property
    def pagination_context(self):
        create_form = self.get_create_form()
        return {
            'pagination': {
                'page': self.page,
                'limit': self.limit,
                'total': self.total,
                'limit_options': range(self.DEFAULT_LIMIT, 51, self.DEFAULT_LIMIT),
                'column_names': self.column_names,
                'num_columns': len(self.column_names),
                'text': {
                    'limit': self.limit_text,
                    'empty': self.empty_notification,
                    'loading': self.loading_message,
                    'deleted_items': self.deleted_items_header,
                    'new_items': self.new_items_header,
                },
                'create_item_form': self.get_create_form_response(create_form) if create_form else None,
            }
        }

    @property
    def allowed_actions(self):
        return [
            'create',
            'update',
            'delete',
            'paginate',
            'refresh',
        ]

    @property
    def paginate_crud_response(self):
        """
        Return this in the post method of your view class.
        """
        response = getattr(self, '%s_response' % self.action)
        return HttpResponse(json.dumps(response, cls=LazyEncoder))

    @property
    def create_response(self):
        create_form = self.get_create_form()
        new_item = None
        if create_form.is_valid():
            new_item = self.get_create_item_data(create_form)
            create_form = self.get_create_form(is_blank=True)
        return {
            'newItem': new_item,
            'form': self.get_create_form_response(create_form)
        }

    @property
    def update_response(self):
        update_form = self.get_update_form()
        updated_item = None
        if update_form.is_valid():
            updated_item = self.get_updated_item_data(update_form)
        return {
            'updatedItem': updated_item,
            'form': self.get_update_form_response(update_form),
        }

    @property
    def refresh_response(self):
        try:
            self.refresh_item(self.item_id)
        except PaginatedItemException as e:
            return {
                'error': _("<strong>Problem Refreshing List:</strong> %s") % e,
            }
        return {
            'success': True,
            'currentPage': self.page,
            'total': self.total,
            'paginatedList': list(self.paginated_list),
        }

    @property
    def delete_response(self):
        try:
            response = self.get_deleted_item_data(self.item_id)
            return {
                'deletedItem': response
            }
        except PaginatedItemException as e:
            return {
                'error': _("<strong>Problem Deleting:</strong> %s") % e,
            }

    @property
    def item_id(self):
        try:
            return self.parameters['itemId']
        except KeyError:
            raise PaginatedItemException(_("The item's ID was not passed to the server."))

    @property
    def paginate_response(self):
        return {
            'success': True,
            'currentPage': self.page,
            'total': self.total,
            'paginatedList': list(self.paginated_list),
        }

    @property
    def paginated_list(self):
        """
        This should return a list (or generator object) of data formatted as follows:
        [
            {
                'itemData': {
                    'id': <id of item>,
                    <json dict of item data for the knockout model to use>
                },
                'template': <knockout template id>
            }
        ]
        """
        raise NotImplementedError("Return a list of data for the request response.")

    def get_create_form(self, is_blank=False):
        """
        This should be a crispy form that creates an item.
        It's not required if you just want a paginated view.
        """
        pass

    def get_create_form_response(self, create_form):
        return render_to_string(
            'style/includes/create_item_form.html', {
                'form': create_form
            }
        )

    def get_update_form(self, initial_data=None):
        raise NotImplementedError("You must return a form object that will update an Item")

    def get_update_form_response(self, update_form):
        return render_to_string(
            'style/bootstrap2/partials/update_item_form.html', {
                'form': update_form
            }
        )

    def refresh_item(self, item_id):
        """
        Process the item that triggered a list refresh here.
        """
        raise NotImplementedError("You must implement refresh_item")

    def get_create_item_data(self, create_form):
        """
        This should return a dict of data for the created item.
        {
            'itemData': {
                'id': <id of item>,
                <json dict of item data for the knockout model to use>
            },
            'template': <knockout template id>
        }
        """
        raise NotImplementedError("You must implement get_new_item_data")

    def get_updated_item_data(self, update_form):
        """
        This should return a dict of data for the updated item.
        {
            'itemData': {
                'id': <id of item>,
                <json dict of item data for the knockout model to use>
            },
            'template': <knockout template id>
        }
        """
        raise NotImplementedError("You must implement get_updated_item_data")

    def get_deleted_item_data(self, item_id):
        """
        This should return a dict of data for the deleted item.
        {
            'itemData': {
                'id': <id of item>,
                <json dict of item data for the knockout model to use>
            },
            'template': <knockout template id>
        }
        """
        raise NotImplementedError("You must implement get_deleted_item_data")

@login_required
def quick_find(request):
    query = request.GET.get('q')
    redirect = request.GET.get('redirect') != 'false'
    if not query:
        return HttpResponseBadRequest('GET param "q" must be provided')

    def deal_with_couch_doc(doc):
        domain = doc.get('domain') or doc.get('domains', [None])[0]
        if request.couch_user.is_superuser or (domain and request.couch_user.is_domain_admin(domain)):
            doc_info = get_doc_info(doc, domain_hint=domain)
        else:
            raise Http404()
        if redirect and doc_info.link:
            messages.info(request, _("We've redirected you to the %s matching your query") % doc_info.type_display)
            return HttpResponseRedirect(doc_info.link)
        elif request.couch_user.is_superuser:
            return HttpResponseRedirect('{}?id={}'.format(reverse('doc_in_es'), doc.get('_id')))
        else:
            return json_response(doc_info)

    try:
        doc = get_db().get(query)
    except ResourceNotFound:
        pass
    else:
        return deal_with_couch_doc(doc)

    try:
        doc = Repeater.get_db().get(query)
    except ResourceNotFound:
        pass
    else:
        return deal_with_couch_doc(doc)

    raise Http404()


def osdd(request, template='osdd.xml'):
    response = render(request, template, {'url_base': get_url_base()})
    response['Content-Type'] = 'application/xml'
    return response

@require_superuser
def maintenance_alerts(request, template='style/bootstrap2/maintenance_alerts.html'):
    from corehq.apps.hqwebapp.models import MaintenanceAlert

    return render(request, template, {
        'alerts': [{
            'created': unicode(alert.created),
            'active': alert.active,
            'html': alert.html,
            'id': alert.id,
        } for alert in MaintenanceAlert.objects.order_by('-created')[:5]]
    })


@require_POST
@require_superuser
def create_alert(request):
    from corehq.apps.hqwebapp.models import MaintenanceAlert
    alert_text = request.POST.get('alert_text')
    MaintenanceAlert(active=False, text=alert_text).save()
    return HttpResponseRedirect(reverse('alerts'))


@require_POST
@require_superuser
def activate_alert(request):
    from corehq.apps.hqwebapp.models import MaintenanceAlert
    ma = MaintenanceAlert.objects.get(id=request.POST.get('alert_id'))
    ma.active = True
    ma.save()
    return HttpResponseRedirect(reverse('alerts'))


@require_POST
@require_superuser
def deactivate_alert(request):
    from corehq.apps.hqwebapp.models import MaintenanceAlert
    ma = MaintenanceAlert.objects.get(id=request.POST.get('alert_id'))
    ma.active = False
    ma.save()
    return HttpResponseRedirect(reverse('alerts'))


class DataTablesAJAXPaginationMixin(object):
    @property
    def echo(self):
        return self.request.GET.get('sEcho')

    @property
    def display_start(self):
        return int(self.request.GET.get('iDisplayStart'))

    @property
    def display_length(self):
        return int(self.request.GET.get('iDisplayLength'))

    @property
    def search_phrase(self):
        return self.request.GET.get('sSearch', '').strip()

    def datatables_ajax_response(self, data, total_records, filtered_records=None):
        return HttpResponse(json.dumps({
            'sEcho': self.echo,
            'aaData': data,
            'iTotalRecords': total_records,
            'iTotalDisplayRecords': filtered_records or total_records,
        }))
