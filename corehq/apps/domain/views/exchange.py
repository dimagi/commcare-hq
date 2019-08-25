import datetime
import logging
import json
import io

import dateutil
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.urls import reverse
from django.http import Http404
from django.shortcuts import redirect
from django.contrib import messages
from PIL import Image
from django.utils.translation import ugettext as _, ugettext_lazy

from corehq.apps.linked_domain.dbaccessors import is_linked_domain
from corehq.apps.hqwebapp.decorators import use_jquery_ui
from corehq.apps.fixtures.models import FixtureDataType
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.forms import (
    SnapshotSettingsForm,
    SnapshotApplicationForm,
    SnapshotFixtureForm,
)
from corehq.apps.domain.models import Domain
from corehq.apps.domain.views.settings import BaseProjectSettingsView, BaseAdminProjectSettingsView
from memoized import memoized
from dimagi.utils.web import get_ip, get_site_domain

from corehq.apps.hqwebapp.tasks import send_html_email_async


def _publish_snapshot(request, domain, published_snapshot=None):
    snapshots = domain.snapshots()
    for snapshot in snapshots:
        if snapshot.published:
            snapshot.published = False
            if not published_snapshot or snapshot.name != published_snapshot.name:
                snapshot.save()
    if published_snapshot:
        if published_snapshot.copied_from.name != domain.name:
            messages.error(request, "Invalid snapshot")
            return False

        # cda stuff. In order to publish a snapshot, a user must have agreed to this
        published_snapshot.cda.signed = True
        published_snapshot.cda.date = datetime.datetime.utcnow()
        published_snapshot.cda.type = 'Content Distribution Agreement'
        if request.couch_user:
            published_snapshot.cda.user_id = request.couch_user.get_id
        published_snapshot.cda.user_ip = get_ip(request)

        published_snapshot.published = True
        published_snapshot.save()
        _notification_email_on_publish(domain, published_snapshot, request.couch_user)
    return True


def _notification_email_on_publish(domain, snapshot, published_by):
    params = {"domain": domain, "snapshot": snapshot,
              "published_by": published_by, "url_base": get_site_domain()}
    text_content = render_to_string(
        "domain/email/published_app_notification.txt", params)
    html_content = render_to_string(
        "domain/email/published_app_notification.html", params)
    recipients = settings.EXCHANGE_NOTIFICATION_RECIPIENTS
    subject = "New App on Exchange: %s" % snapshot.title
    try:
        for recipient in recipients:
            send_html_email_async.delay(subject, recipient, html_content,
                                        text_content=text_content,
                                        email_from=settings.DEFAULT_FROM_EMAIL)
    except Exception:
        logging.warning("Can't send notification email, "
                        "but the message was:\n%s" % text_content)


@domain_admin_required
def set_published_snapshot(request, domain, snapshot_name=''):
    domain = request.project
    if request.method == 'POST':
        if snapshot_name != '':
            published_snapshot = Domain.get_by_name(snapshot_name)
            _publish_snapshot(request, domain, published_snapshot=published_snapshot)
        else:
            _publish_snapshot(request, domain)
    return redirect('domain_snapshot_settings', domain.name)


class ExchangeSnapshotsView(BaseAdminProjectSettingsView):
    template_name = 'domain/snapshot_settings.html'
    urlname = 'domain_snapshot_settings'
    page_title = ugettext_lazy("CommCare Exchange")

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        if is_linked_domain(request.domain):
            raise Http404()
        return super(BaseProjectSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'project': self.domain_object,
            'snapshots': list(self.domain_object.snapshots()),
            'published_snapshot': self.domain_object.published_snapshot(),
        }


class CreateNewExchangeSnapshotView(BaseAdminProjectSettingsView):
    template_name = 'domain/create_snapshot.html'
    urlname = 'domain_create_snapshot'
    page_title = ugettext_lazy("Publish New Version")
    strict_domain_fetching = True

    @method_decorator(domain_admin_required)
    @use_jquery_ui
    def dispatch(self, request, *args, **kwargs):
        return super(BaseProjectSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    def parent_pages(self):
        return [{
            'title': ExchangeSnapshotsView.page_title,
            'url': reverse(ExchangeSnapshotsView.urlname, args=[self.domain]),
        }]

    @property
    def page_context(self):
        app_forms = self.app_forms
        fixture_forms = self.fixture_forms
        context = {
            'form': self.snapshot_settings_form,
            'app_forms': app_forms,
            'app_ids': [app.id for app, form in app_forms],
            'fixture_forms': fixture_forms,
            'fixture_ids': [data.id for data, form in fixture_forms],
            'can_publish_as_org': self.can_publish_as_org,
        }
        if self.published_snapshot:
            context.update({
                'published_as_org': self.published_snapshot.publisher == 'organization',
                'author': self.published_snapshot.author,
            })
        elif self.request.method == 'POST':
            context.update({
                'published_as_org': self.request.POST.get('publisher', '') == 'organization',
                'author': self.request.POST.get('author', '')
            })
        return context

    @property
    def can_publish_as_org(self):
        return False

    @property
    @memoized
    def snapshots(self):
        return list(self.domain_object.snapshots())

    @property
    @memoized
    def published_snapshot(self):
        return self.snapshots[0] if self.snapshots else self.domain_object

    @property
    @memoized
    def published_apps(self):
        published_apps = {}
        if self.published_snapshot:
            for app in self.published_snapshot.full_applications():
                if self.domain_object == self.published_snapshot:
                    base_app_id = app.copy_of
                else:
                    base_app_id = app.copied_from.copy_of
                if base_app_id:
                    published_apps[base_app_id] = app
        return published_apps

    @property
    def app_forms(self):
        app_forms = []
        for app in self.domain_object.applications():
            if self.request.method == 'POST':
                app_forms.append((app, SnapshotApplicationForm(self.request.POST, prefix=app.id)))
            elif self.published_snapshot and app.copy_of in self.published_apps:
                original = self.published_apps[app.copy_of]
                app_forms.append((app, SnapshotApplicationForm(initial={
                    'publish': True,
                    'name': original.name,
                    'description': original.description,
                    'deployment_date': original.deployment_date,
                    'user_type': original.user_type,
                    'attribution_notes': original.attribution_notes,
                    'phone_model': original.phone_model,

                }, prefix=app.id)))
            else:
                app_forms.append((app,
                                  SnapshotApplicationForm(
                                      initial={
                                          'publish': (self.published_snapshot is None
                                                      or self.published_snapshot == self.domain_object)
                                      }, prefix=app.id)))
        return app_forms

    @property
    @memoized
    def published_fixtures(self):
        return [f.copy_from for f in FixtureDataType.by_domain(self.published_snapshot._id)]

    @property
    def fixture_forms(self):
        fixture_forms = []
        for fixture in FixtureDataType.by_domain(self.domain_object.name):
            fixture.id = fixture._id
            if self.request.method == 'POST':
                fixture_forms.append((fixture,
                    SnapshotFixtureForm(self.request.POST, prefix=fixture._id)))
            else:
                fixture_forms.append((fixture,
                                  SnapshotFixtureForm(
                                      initial={
                                          'publish': (self.published_snapshot == self.domain_object
                                                      or fixture._id in self.published_fixtures)
                                      }, prefix=fixture._id)))

        return fixture_forms

    @property
    @memoized
    def snapshot_settings_form(self):
        if self.request.method == 'POST':
            form = SnapshotSettingsForm(self.request.POST,
                                        self.request.FILES,
                                        domain=self.domain_object,
                                        is_superuser=self.request.user.is_superuser)
            return form

        proj = self.published_snapshot if self.published_snapshot else self.domain_object
        initial = {
            'case_sharing': json.dumps(proj.case_sharing),
            'publish_on_submit': True,
            'share_multimedia': self.published_snapshot.multimedia_included if self.published_snapshot else True,
        }
        init_attribs = ['default_timezone', 'project_type', 'license']
        if self.published_snapshot:
            init_attribs.extend(['title', 'description', 'short_description'])
            if self.published_snapshot.yt_id:
                initial['video'] = 'http://www.youtube.com/watch?v=%s' % self.published_snapshot.yt_id
        for attr in init_attribs:
            initial[attr] = getattr(proj, attr)

        return SnapshotSettingsForm(initial=initial,
                                    domain=self.domain_object,
                                    is_superuser=self.request.user.is_superuser)

    @property
    @memoized
    def has_published_apps(self):
        for app in self.domain_object.applications():
            if self.request.POST.get("%s-publish" % app.id, False):
                return True
        messages.error(self.request, _("Cannot publish a project without applications to CommCare Exchange"))
        return False

    @property
    def has_signed_eula(self):
        eula_signed = self.request.couch_user.is_eula_signed()
        if not eula_signed:
            messages.error(self.request, _("You must agree to our terms of service "
                                           "to publish a project to Exchange"))
        return eula_signed

    @property
    def has_valid_form(self):
        is_valid = self.snapshot_settings_form.is_valid()
        if not is_valid:
            messages.error(self.request, _("There are some problems with your form. "
                                           "Please address these issues and try again."))
        return is_valid

    def post(self, request, *args, **kwargs):
        if self.has_published_apps and self.has_signed_eula and self.has_valid_form:
            new_license = request.POST['license']
            if request.POST.get('share_multimedia', False):
                app_ids = self.snapshot_settings_form._get_apps_to_publish()
                media = self.domain_object.all_media(from_apps=app_ids)
                for m_file in media:
                    if self.domain not in m_file.shared_by:
                        m_file.shared_by.append(self.domain)

                    # set the license of every multimedia file that doesn't yet have a license set
                    if not m_file.license:
                        m_file.update_or_add_license(self.domain, type=new_license, should_save=False)

                    m_file.save()

            if not request.POST.get('share_reminders', False):
                share_reminders = False
            else:
                share_reminders = True

            copy_by_id = set()
            for k in request.POST:
                if k.endswith("-publish"):
                    copy_by_id.add(k[:-len("-publish")])

            old = self.domain_object.published_snapshot()
            new_domain = self.domain_object.save_snapshot(
                share_reminders=share_reminders, copy_by_id=copy_by_id)
            new_domain.license = new_license
            new_domain.description = request.POST['description']
            new_domain.short_description = request.POST['short_description']
            new_domain.project_type = request.POST['project_type']
            new_domain.title = request.POST['title']
            new_domain.multimedia_included = request.POST.get('share_multimedia', '') == 'on'
            new_domain.publisher = request.POST.get('publisher', None) or 'user'
            if request.POST.get('video'):
                new_domain.yt_id = self.snapshot_settings_form.cleaned_data['video']

            new_domain.author = request.POST.get('author', None)

            new_domain.is_approved = False
            new_domain.is_starter_app = request.POST.get('is_starter_app', '') == 'on'
            publish_on_submit = request.POST.get('publish_on_submit', "no") == "yes"

            image = self.snapshot_settings_form.cleaned_data['image']
            if image:
                new_domain.image_path = image.name
                new_domain.image_type = image.content_type
            elif request.POST.get('old_image', False):
                new_domain.image_path = old.image_path
                new_domain.image_type = old.image_type

            documentation_file = self.snapshot_settings_form.cleaned_data['documentation_file']
            if documentation_file:
                new_domain.documentation_file_path = documentation_file.name
                new_domain.documentation_file_type = documentation_file.content_type
            elif request.POST.get('old_documentation_file', False):
                new_domain.documentation_file_path = old.documentation_file_path
                new_domain.documentation_file_type = old.documentation_file_type

            if publish_on_submit:
                new_domain.save()
                _publish_snapshot(request, self.domain_object, published_snapshot=new_domain)
            else:
                new_domain.published = False
                new_domain.save()

            if image:
                im = Image.open(image)
                out = io.BytesIO()
                im.thumbnail((200, 200), Image.ANTIALIAS)
                im.save(out, new_domain.image_type.split('/')[-1])
                new_domain.put_attachment(content=out.getvalue(), name=image.name)
            elif request.POST.get('old_image', False):
                new_domain.put_attachment(content=old.fetch_attachment(old.image_path), name=new_domain.image_path)

            if documentation_file:
                new_domain.put_attachment(content=documentation_file, name=documentation_file.name)
            elif request.POST.get('old_documentation_file', False):
                new_domain.put_attachment(content=old.fetch_attachment(old.documentation_file_path),
                                          name=new_domain.documentation_file_path)

            for application in new_domain.full_applications():
                # Note that application is a build. If the original app has a build then application.copied_from
                # will be a build and application.copied_from.copy_of will be the original app ID, otherwise
                # application.copied_from will be the original app. (FB 190587) See also self.published_apps()
                original_id = application.copied_from.copy_of if application.copied_from.copy_of \
                    else application.copied_from._id
                name_field = "%s-name" % original_id
                if name_field not in request.POST:
                    continue

                application.name = request.POST[name_field]
                application.description = request.POST["%s-description" % original_id]
                date_picked = request.POST["%s-deployment_date" % original_id]
                try:
                    date_picked = dateutil.parser.parse(date_picked)
                    if date_picked.year > 2009:
                        application.deployment_date = date_picked
                except Exception:
                    pass
                application.phone_model = request.POST["%s-phone_model" % original_id]
                application.attribution_notes = request.POST["%s-attribution_notes" % original_id]
                application.user_type = request.POST["%s-user_type" % original_id]

                if not new_domain.multimedia_included:
                    application.multimedia_map = {}
                application.save()

            for fixture in FixtureDataType.by_domain(new_domain.name):
                old_id = FixtureDataType.by_domain_tag(self.domain_object.name,
                                                       fixture.tag).first()._id
                fixture.description = request.POST["%s-description" % old_id]
                fixture.save()

            messages.success(request, (_("Created a new version of your app. This version will be posted to "
                                         "CommCare Exchange pending approval by admins.") if publish_on_submit
                                       else _("Created a new version of your app.")))
            return redirect(ExchangeSnapshotsView.urlname, self.domain)
        return self.get(request, *args, **kwargs)
