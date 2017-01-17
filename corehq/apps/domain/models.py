from datetime import datetime
from itertools import imap
import time
import uuid

from couchdbkit import PreconditionFailed

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.cachehq.mixins import QuickCachedDocumentMixin
from corehq.apps.domain.exceptions import DomainDeleteException
from corehq.apps.tzmigration.api import set_tz_migration_complete
from corehq.dbaccessors.couchapps.all_docs import \
    get_all_doc_ids_for_domain_grouped_by_db
from corehq.util.soft_assert import soft_assert
from couchforms.analytics import domain_has_submission_in_last_30_days
from dimagi.ext.couchdbkit import (
    Document, StringProperty, BooleanProperty, DateTimeProperty, IntegerProperty,
    DocumentSchema, SchemaProperty, DictProperty,
    StringListProperty, SchemaListProperty, TimeProperty, DecimalProperty
)
from django.core.urlresolvers import reverse
from django.db import models
from django.utils.translation import ugettext_lazy as _
from corehq.apps.appstore.models import SnapshotMixin
from corehq.util.quickcache import quickcache, skippable_quickcache
from dimagi.utils.couch import CriticalSection
from dimagi.utils.couch.database import (
    iter_docs, get_safe_write_kwargs, apply_update, iter_bulk_delete
)
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.hqwebapp.tasks import send_html_email_async
from dimagi.utils.html import format_html
from dimagi.utils.logging import notify_exception
from dimagi.utils.name_to_url import name_to_url
from dimagi.utils.next_available_name import next_available_name
from dimagi.utils.web import get_url_base
from itertools import chain
from langcodes import langs as all_langs
from collections import defaultdict
from importlib import import_module
from corehq import toggles

from .exceptions import InactiveTransferDomainException, NameUnavailableException

from corehq.apps.app_manager.const import AMPLIFIES_NO, AMPLIFIES_NOT_SET, AMPLIFIES_YES

lang_lookup = defaultdict(str)

DATA_DICT = settings.INTERNAL_DATA
AREA_CHOICES = [a["name"] for a in DATA_DICT["area"]]
SUB_AREA_CHOICES = reduce(list.__add__, [a["sub_areas"] for a in DATA_DICT["area"]], [])
DATE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

BUSINESS_UNITS = [
    "DSA",
    "DSI",
    "DWA",
    "INC",
]


for lang in all_langs:
    lang_lookup[lang['three']] = lang['names'][0]  # arbitrarily using the first name if there are multiple
    if lang['two'] != '':
        lang_lookup[lang['two']] = lang['names'][0]


LICENSES = {
    'cc': 'Creative Commons Attribution (CC BY)',
    'cc-sa': 'Creative Commons Attribution, Share Alike (CC BY-SA)',
    'cc-nd': 'Creative Commons Attribution, No Derivatives (CC BY-ND)',
    'cc-nc': 'Creative Commons Attribution, Non-Commercial (CC BY-NC)',
    'cc-nc-sa': 'Creative Commons Attribution, Non-Commercial, and Share Alike (CC BY-NC-SA)',
    'cc-nc-nd': 'Creative Commons Attribution, Non-Commercial, and No Derivatives (CC BY-NC-ND)'
}

LICENSE_LINKS = {
    'cc': 'http://creativecommons.org/licenses/by/4.0',
    'cc-sa': 'http://creativecommons.org/licenses/by-sa/4.0',
    'cc-nd': 'http://creativecommons.org/licenses/by-nd/4.0',
    'cc-nc': 'http://creativecommons.org/licenses/by-nc/4.0',
    'cc-nc-sa': 'http://creativecommons.org/licenses/by-nc-sa/4.0',
    'cc-nc-nd': 'http://creativecommons.org/licenses/by-nc-nd/4.0',
}


def cached_property(method):
    def find_cached(self):
        try:
            return self.cached_properties[method.__name__]
        except KeyError:
            self.cached_properties[method.__name__] = method(self)
            self.save()
            return self.cached_properties[method.__name__]
    return find_cached


class UpdatableSchema():

    def update(self, new_dict):
        for kw in new_dict:
            self[kw] = new_dict[kw]


class Deployment(DocumentSchema, UpdatableSchema):
    city = StringProperty()
    countries = StringListProperty()
    region = StringProperty()  # e.g. US, LAC, SA, Sub-saharn Africa, East Africa, West Africa, Southeast Asia)
    description = StringProperty()
    public = BooleanProperty(default=False)


class CallCenterProperties(DocumentSchema):
    enabled = BooleanProperty(default=False)
    use_fixtures = BooleanProperty(default=True)

    case_owner_id = StringProperty()
    use_user_location_as_owner = BooleanProperty(default=False)
    user_location_ancestor_level = IntegerProperty(default=0)

    case_type = StringProperty()

    def fixtures_are_active(self):
        return self.enabled and self.use_fixtures

    def config_is_valid(self):
        return (self.use_user_location_as_owner or self.case_owner_id) and self.case_type


class LicenseAgreement(DocumentSchema):
    signed = BooleanProperty(default=False)
    type = StringProperty()
    date = DateTimeProperty()
    user_id = StringProperty()
    user_ip = StringProperty()
    version = StringProperty()


class InternalProperties(DocumentSchema, UpdatableSchema):
    """
    Project properties that should only be visible/editable by superusers
    """
    sf_contract_id = StringProperty()
    sf_account_id = StringProperty()
    commcare_edition = StringProperty(
        choices=['', "plus", "community", "standard", "pro", "advanced", "enterprise"],
        default="community"
    )
    initiative = StringListProperty()
    workshop_region = StringProperty()
    project_state = StringProperty(choices=["", "POC", "transition", "at-scale"], default="")
    self_started = BooleanProperty(default=True)
    area = StringProperty()
    sub_area = StringProperty()
    using_adm = BooleanProperty()
    using_call_center = BooleanProperty()
    custom_eula = BooleanProperty()
    can_use_data = BooleanProperty(default=True)
    notes = StringProperty()
    organization_name = StringProperty()
    platform = StringListProperty()
    project_manager = StringProperty()
    phone_model = StringProperty()
    goal_time_period = IntegerProperty()
    goal_followup_rate = DecimalProperty()
    # intentionally different from and commtrack_enabled so that FMs can change
    commtrack_domain = BooleanProperty()
    performance_threshold = IntegerProperty()
    experienced_threshold = IntegerProperty()
    amplifies_workers = StringProperty(
        choices=[AMPLIFIES_YES, AMPLIFIES_NO, AMPLIFIES_NOT_SET],
        default=AMPLIFIES_NOT_SET
    )
    amplifies_project = StringProperty(
        choices=[AMPLIFIES_YES, AMPLIFIES_NO, AMPLIFIES_NOT_SET],
        default=AMPLIFIES_NOT_SET
    )
    business_unit = StringProperty(choices=BUSINESS_UNITS + [""], default="")
    data_access_threshold = IntegerProperty()


class CaseDisplaySettings(DocumentSchema):
    case_details = DictProperty(
        verbose_name="Mapping of case type to definitions of properties "
                     "to display above the fold on case details")
    form_details = DictProperty(
        verbose_name="Mapping of form xmlns to definitions of properties "
                     "to display for individual forms")

    # todo: case list


class DynamicReportConfig(DocumentSchema):
    """configurations of generic/template reports to be set up for this domain"""
    report = StringProperty()  # fully-qualified path to template report class
    name = StringProperty()  # report display name in sidebar
    kwargs = DictProperty()  # arbitrary settings to configure report
    previewers_only = BooleanProperty()


class DynamicReportSet(DocumentSchema):
    """a set of dynamic reports grouped under a section header in the sidebar"""
    section_title = StringProperty()
    reports = SchemaListProperty(DynamicReportConfig)


LOGO_ATTACHMENT = 'logo.png'


class DayTimeWindow(DocumentSchema):
    """
    Defines a window of time in a day of the week.
    Day/time combinations will be interpreted in the domain's timezone.
    """
    # 0 - 6 is Monday - Sunday; -1 means it applies to all days
    day = IntegerProperty()
    # For times, None means there's no lower/upper bound
    start_time = TimeProperty()
    end_time = TimeProperty()


class Domain(QuickCachedDocumentMixin, Document, SnapshotMixin):
    """Domain is the highest level collection of people/stuff
       in the system.  Pretty much everything happens at the
       domain-level, including user membership, permission to
       see data, reports, charts, etc."""

    name = StringProperty()
    is_active = BooleanProperty()
    date_created = DateTimeProperty()
    default_timezone = StringProperty(default=getattr(settings, "TIME_ZONE", "UTC"))
    case_sharing = BooleanProperty(default=False)
    secure_submissions = BooleanProperty(default=False)
    cloudcare_releases = StringProperty(choices=['stars', 'nostars', 'default'], default='default')
    organization = StringProperty()
    hr_name = StringProperty()  # the human-readable name for this project
    project_description = StringProperty()  # Brief description of the project
    creating_user = StringProperty()  # username of the user who created this domain

    # domain metadata
    project_type = StringProperty()  # e.g. MCH, HIV
    customer_type = StringProperty()  # plus, full, etc.
    is_test = StringProperty(choices=["true", "false", "none"], default="none")
    description = StringProperty()
    short_description = StringProperty()
    is_shared = BooleanProperty(default=False)
    commtrack_enabled = BooleanProperty(default=False)
    call_center_config = SchemaProperty(CallCenterProperties)
    has_careplan = BooleanProperty(default=False)
    restrict_superusers = BooleanProperty(default=False)
    allow_domain_requests = BooleanProperty(default=False)
    location_restriction_for_users = BooleanProperty(default=False)
    usercase_enabled = BooleanProperty(default=False)
    hipaa_compliant = BooleanProperty(default=False)
    use_sql_backend = BooleanProperty(default=False)
    first_domain_for_user = BooleanProperty(default=False)

    case_display = SchemaProperty(CaseDisplaySettings)

    # CommConnect settings
    commconnect_enabled = BooleanProperty(default=False)
    survey_management_enabled = BooleanProperty(default=False)
    # Whether or not a case can register via sms
    sms_case_registration_enabled = BooleanProperty(default=False)
    # Case type to apply to cases registered via sms
    sms_case_registration_type = StringProperty()
    # Owner to apply to cases registered via sms
    sms_case_registration_owner_id = StringProperty()
    # Submitting user to apply to cases registered via sms
    sms_case_registration_user_id = StringProperty()
    # Whether or not a mobile worker can register via sms
    sms_mobile_worker_registration_enabled = BooleanProperty(default=False)
    use_default_sms_response = BooleanProperty(default=False)
    default_sms_response = StringProperty()
    chat_message_count_threshold = IntegerProperty()
    custom_chat_template = StringProperty()  # See settings.CUSTOM_CHAT_TEMPLATES
    custom_case_username = StringProperty()  # Case property to use when showing the case's name in a chat window
    # If empty, sms can be sent at any time. Otherwise, only send during
    # these windows of time. SMS_QUEUE_ENABLED must be True in localsettings
    # for this be considered.
    restricted_sms_times = SchemaListProperty(DayTimeWindow)
    # If empty, this is ignored. Otherwise, the framework will make sure
    # that during these days/times, no automated outbound sms will be sent
    # to someone if they have sent in an sms within sms_conversation_length
    # minutes. Outbound sms sent from a user in a chat window, however, will
    # still be sent. This is meant to prevent chat conversations from being
    # interrupted by automated sms reminders.
    # SMS_QUEUE_ENABLED must be True in localsettings for this to be
    # considered.
    sms_conversation_times = SchemaListProperty(DayTimeWindow)
    # In minutes, see above.
    sms_conversation_length = IntegerProperty(default=10)
    # Set to True to prevent survey questions and answers form being seen in
    # SMS chat windows.
    filter_surveys_from_chat = BooleanProperty(default=False)
    # The below option only matters if filter_surveys_from_chat = True.
    # If set to True, invalid survey responses will still be shown in the chat
    # window, while questions and valid responses will be filtered out.
    show_invalid_survey_responses_in_chat = BooleanProperty(default=False)
    # If set to True, if a message is read by anyone it counts as being read by
    # everyone. Set to False so that a message is only counted as being read
    # for a user if only that user has read it.
    count_messages_as_read_by_anyone = BooleanProperty(default=False)
    # Set to True to allow sending sms and all-label surveys to cases whose
    # phone number is duplicated with another contact
    send_to_duplicated_case_numbers = BooleanProperty(default=True)
    enable_registration_welcome_sms_for_case = BooleanProperty(default=False)
    enable_registration_welcome_sms_for_mobile_worker = BooleanProperty(default=False)
    sms_survey_date_format = StringProperty()

    # exchange/domain copying stuff
    is_snapshot = BooleanProperty(default=False)
    is_approved = BooleanProperty(default=False)
    snapshot_time = DateTimeProperty()
    published = BooleanProperty(default=False)
    license = StringProperty(choices=LICENSES, default='cc')
    title = StringProperty()
    cda = SchemaProperty(LicenseAgreement)
    multimedia_included = BooleanProperty(default=True)
    downloads = IntegerProperty(default=0)  # number of downloads for this specific snapshot
    full_downloads = IntegerProperty(default=0)  # number of downloads for all snapshots from this domain
    author = StringProperty()
    phone_model = StringProperty()
    attribution_notes = StringProperty()
    publisher = StringProperty(choices=["organization", "user"], default="user")
    yt_id = StringProperty()
    snapshot_head = BooleanProperty(default=False)

    deployment = SchemaProperty(Deployment)

    image_path = StringProperty()
    image_type = StringProperty()

    cached_properties = DictProperty()

    internal = SchemaProperty(InternalProperties)

    dynamic_reports = SchemaListProperty(DynamicReportSet)

    # extra user specified properties
    tags = StringListProperty()
    area = StringProperty(choices=AREA_CHOICES)
    sub_area = StringProperty(choices=SUB_AREA_CHOICES)
    launch_date = DateTimeProperty

    # to be eliminated from projects and related documents when they are copied for the exchange
    _dirty_fields = ('admin_password', 'admin_password_charset', 'city', 'countries', 'region', 'customer_type')

    last_modified = DateTimeProperty(default=datetime(2015, 1, 1))

    # when turned on, use SECURE_TIMEOUT for sessions of users who are members of this domain
    secure_sessions = BooleanProperty(default=False)

    two_factor_auth = BooleanProperty(default=False)
    strong_mobile_passwords = BooleanProperty(default=False)

    # There is no longer a way to request a report builder trial, so this property should be removed in the near
    # future. (Keeping it for now in case a user has requested a trial and but has not yet been granted it)
    requested_report_builder_trial = StringListProperty()
    requested_report_builder_subscription = StringListProperty()

    @classmethod
    def wrap(cls, data):
        # for domains that still use original_doc
        should_save = False
        if 'original_doc' in data:
            original_doc = data['original_doc']
            del data['original_doc']
            should_save = True
            if original_doc:
                original_doc = Domain.get_by_name(original_doc)
                data['copy_history'] = [original_doc._id]

        # for domains that have a public domain license
        if 'license' in data:
            if data.get("license", None) == "public":
                data["license"] = "cc"
                should_save = True

        if 'slug' in data and data["slug"]:
            data["hr_name"] = data["slug"]
            del data["slug"]

        if 'is_test' in data and isinstance(data["is_test"], bool):
            data["is_test"] = "true" if data["is_test"] else "false"
            should_save = True

        if 'cloudcare_releases' not in data:
            data['cloudcare_releases'] = 'nostars'  # legacy default setting

        # Don't actually remove location_types yet.  We can migrate fully and
        # remove this after everything's hunky-dory in production.  2015-03-06
        if 'location_types' in data:
            data['obsolete_location_types'] = data.pop('location_types')

        self = super(Domain, cls).wrap(data)
        if self.deployment is None:
            self.deployment = Deployment()
        if should_save:
            self.save()
        return self

    def get_default_timezone(self):
        """return a timezone object from self.default_timezone"""
        import pytz
        return pytz.timezone(self.default_timezone)

    @staticmethod
    @quickcache(['name'], timeout=24 * 60 * 60)
    def is_secure_session_required(name):
        domain = Domain.get_by_name(name)
        return domain and domain.secure_sessions

    @staticmethod
    @skippable_quickcache(['couch_user._id', 'is_active'],
                          skip_arg='strict', timeout=5*60, memoize_timeout=10)
    def active_for_couch_user(couch_user, is_active=True, strict=False):
        domain_names = couch_user.get_domains()
        return Domain.view(
            "domain/by_status",
            keys=[[is_active, d] for d in domain_names],
            reduce=False,
            include_docs=True,
            stale=settings.COUCH_STALE_QUERY if not strict else None,
        ).all()

    @staticmethod
    def active_for_user(user, is_active=True, strict=False):
        if isinstance(user, AnonymousUser):
            return []
        from corehq.apps.users.models import CouchUser
        if isinstance(user, CouchUser):
            couch_user = user
        else:
            couch_user = CouchUser.from_django_user(user)
        if couch_user:
            return Domain.active_for_couch_user(
                couch_user, is_active=is_active, strict=strict)
        else:
            return []

    @classmethod
    def field_by_prefix(cls, field, prefix=''):
        # unichr(0xfff8) is something close to the highest character available
        res = cls.view("domain/fields_by_prefix",
                       group=True,
                       startkey=[field, True, prefix],
                       endkey=[field, True, "%s%c" % (prefix, unichr(0xfff8)), {}])
        vals = [(d['value'], d['key'][2]) for d in res]
        vals.sort(reverse=True)
        return [(v[1], v[0]) for v in vals]

    def add(self, model_instance, is_active=True):
        """
        Add something to this domain, through the generic relation.
        Returns the created membership object
        """
        # Add membership info to Couch
        couch_user = model_instance.get_profile().get_couch_user()
        couch_user.add_domain_membership(self.name)
        couch_user.save()

    def applications(self):
        return get_brief_apps_in_domain(self.name)

    def full_applications(self, include_builds=True):
        from corehq.apps.app_manager.util import get_correct_app_class
        from corehq.apps.app_manager.models import Application

        def wrap_application(a):
            return get_correct_app_class(a['doc']).wrap(a['doc'])

        if include_builds:
            startkey = [self.name]
            endkey = [self.name, {}]
        else:
            startkey = [self.name, None]
            endkey = [self.name, None, {}]

        return Application.get_db().view('app_manager/applications',
            startkey=startkey,
            endkey=endkey,
            include_docs=True,
            wrapper=wrap_application).all()

    @cached_property
    def versions(self):
        apps = self.applications()
        return list(set(a.application_version for a in apps))

    @cached_property
    def has_case_management(self):
        for app in self.full_applications():
            if app.doc_type == 'Application':
                if app.has_case_management():
                    return True
        return False

    @cached_property
    def has_media(self):
        for app in self.full_applications():
            if app.doc_type == 'Application' and app.has_media():
                return True
        return False

    @property
    def use_cloudcare_releases(self):
        return self.cloudcare_releases != 'nostars'

    def all_users(self):
        from corehq.apps.users.models import CouchUser
        return CouchUser.by_domain(self.name)

    def recent_submissions(self):
        return domain_has_submission_in_last_30_days(self.name)

    @cached_property
    def languages(self):
        apps = self.applications()
        return set(chain.from_iterable([a.langs for a in apps]))

    def readable_languages(self):
        return ', '.join(lang_lookup[lang] or lang for lang in self.languages())

    def __unicode__(self):
        return self.name

    @classmethod
    @skippable_quickcache(['name'], skip_arg='strict', timeout=30*60)
    def get_by_name(cls, name, strict=False):
        if not name:
            # get_by_name should never be called with name as None (or '', etc)
            # I fixed the code in such a way that if I raise a ValueError
            # all tests pass and basic pages load,
            # but in order not to break anything in the wild,
            # I'm opting to notify by email if/when this happens
            # but fall back to the previous behavior of returning None
            if settings.DEBUG:
                raise ValueError('%r is not a valid domain name' % name)
            else:
                _assert = soft_assert(notify_admins=True, exponential_backoff=False)
                _assert(False, '%r is not a valid domain name' % name)
                return None

        def _get_by_name(stale=False):
            extra_args = {'stale': settings.COUCH_STALE_QUERY} if stale else {}
            result = cls.view("domain/domains", key=name, reduce=False, include_docs=True, **extra_args).first()
            if not isinstance(result, Domain):
                # A stale view may return a result with no doc if the doc has just been deleted.
                # In this case couchdbkit just returns the raw view result as a dict
                return None
            else:
                return result

        domain = _get_by_name(stale=(not strict))
        if domain is None and not strict:
            # on the off chance this is a brand new domain, try with strict
            domain = _get_by_name(stale=False)
        return domain

    @classmethod
    def get_or_create_with_name(cls, name, is_active=False, secure_submissions=True, use_sql_backend=False):
        result = cls.view("domain/domains", key=name, reduce=False, include_docs=True).first()
        if result:
            return result
        else:
            new_domain = Domain(
                name=name,
                is_active=is_active,
                date_created=datetime.utcnow(),
                secure_submissions=secure_submissions,
                use_sql_backend=use_sql_backend,
            )
            new_domain.save(**get_safe_write_kwargs())
            return new_domain

    @classmethod
    def generate_name(cls, hr_name, max_length=25):
        '''
        Generate a URL-friendly name based on a given human-readable name.
        Normalizes given name, then looks for conflicting domains, addressing
        conflicts by adding "-1", "-2", etc. May return None if it fails to
        generate a new, unique name. Throws exception if it can't figure out
        a name, which shouldn't happen unless max_length is absurdly short.
        '''
        from corehq.apps.domain.utils import get_domain_url_slug
        name = get_domain_url_slug(hr_name, max_length=max_length)
        if not name:
            raise NameUnavailableException
        if Domain.get_by_name(name):
            prefix = name
            while len(prefix):
                name = next_available_name(prefix, Domain.get_names_by_prefix(prefix + '-'))
                if Domain.get_by_name(name):
                    # should never happen
                    raise NameUnavailableException
                if len(name) <= max_length:
                    return name
                prefix = prefix[:-1]
            raise NameUnavailableException

        return name

    @classmethod
    def get_all(cls, include_docs=True):
        domains = Domain.view("domain/not_snapshots", include_docs=False).all()
        if not include_docs:
            return domains
        else:
            return imap(cls.wrap, iter_docs(cls.get_db(), [d['id'] for d in domains]))

    @classmethod
    def get_all_names(cls):
        return [d['key'] for d in cls.get_all(include_docs=False)]

    @classmethod
    def get_all_ids(cls):
        return [d['id'] for d in cls.get_all(include_docs=False)]

    @classmethod
    def get_names_by_prefix(cls, prefix):
        return [d['key'] for d in Domain.view(
            "domain/domains",
            startkey=prefix,
            endkey=prefix + u"zzz",
            reduce=False,
            include_docs=False
        ).all()]

    def case_sharing_included(self):
        return self.case_sharing or reduce(lambda x, y: x or y, [getattr(app, 'case_sharing', False) for app in self.applications()], False)

    def save(self, **params):
        self.last_modified = datetime.utcnow()
        if not self._rev:
            # mark any new domain as timezone migration complete
            set_tz_migration_complete(self.name)
        super(Domain, self).save(**params)

        from corehq.apps.domain.signals import commcare_domain_post_save
        results = commcare_domain_post_save.send_robust(sender='domain', domain=self)
        for result in results:
            # Second argument is None if there was no error
            if result[1]:
                notify_exception(
                    None,
                    message="Error occured during domain post_save %s: %s" %
                            (self.name, str(result[1]))
                )

    def save_copy(self, new_domain_name=None, new_hr_name=None, user=None,
                  copy_by_id=None, share_reminders=True,
                  share_user_roles=True):
        from corehq.apps.app_manager.dbaccessors import get_app
        from corehq.apps.reminders.models import CaseReminderHandler
        from corehq.apps.fixtures.models import FixtureDataItem
        from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
        from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_class
        from corehq.apps.fixtures.models import FixtureDataType
        from corehq.apps.users.models import UserRole

        db = Domain.get_db()
        new_id = db.copy_doc(self.get_id)['id']
        if new_domain_name is None:
            new_domain_name = new_id

        with CriticalSection(['request_domain_name_{}'.format(new_domain_name)]):
            new_domain_name = Domain.generate_name(new_domain_name)
            new_domain = Domain.get(new_id)
            new_domain.name = new_domain_name
            new_domain.hr_name = new_hr_name
            new_domain.copy_history = self.get_updated_history()
            new_domain.is_snapshot = False
            new_domain.snapshot_time = None
            new_domain.organization = None  # TODO: use current user's organization (?)

            # reset stuff
            new_domain.cda.signed = False
            new_domain.cda.date = None
            new_domain.cda.type = None
            new_domain.cda.user_id = None
            new_domain.cda.user_ip = None
            new_domain.is_test = "none"
            new_domain.internal = InternalProperties()
            new_domain.creating_user = user.username if user else None
            new_domain.date_created = datetime.utcnow()

            for field in self._dirty_fields:
                if hasattr(new_domain, field):
                    delattr(new_domain, field)

            # Saving the domain should happen before we import any apps since
            # importing apps can update the domain object (for example, if user
            # as a case needs to be enabled)
            try:
                new_domain.save()
            except PreconditionFailed:
                # This is a hack to resolve http://manage.dimagi.com/default.asp?241492
                # Following solution in
                # https://github.com/dimagi/commcare-hq/commit/d59b1e403060ade599cc4a03db0aabc4da62b668
                time.sleep(0.5)
                new_domain.save()

            new_app_components = {}  # a mapping of component's id to its copy

            def copy_data_items(old_type_id, new_type_id):
                for item in FixtureDataItem.by_data_type(self.name, old_type_id):
                    comp = self.copy_component(
                        item.doc_type, item._id, new_domain_name, user=user)
                    comp.data_type_id = new_type_id
                    comp.save()

            def get_latest_app_id(doc_id):
                app = get_app(self.name, doc_id).get_latest_saved()
                if app:
                    return app._id, app.doc_type

            for app in get_brief_apps_in_domain(self.name):
                doc_id, doc_type = app.get_id, app.doc_type
                original_doc_id = doc_id
                if copy_by_id and doc_id not in copy_by_id:
                    continue
                if not self.is_snapshot:
                    doc_id, doc_type = get_latest_app_id(doc_id) or (doc_id, doc_type)
                component = self.copy_component(doc_type, doc_id, new_domain_name, user=user)
                if component:
                    new_app_components[original_doc_id] = component

            for doc_id in get_doc_ids_in_domain_by_class(self.name, FixtureDataType):
                if copy_by_id and doc_id not in copy_by_id:
                    continue
                component = self.copy_component(
                    'FixtureDataType', doc_id, new_domain_name, user=user)
                copy_data_items(doc_id, component._id)

            if share_reminders:
                for doc_id in get_doc_ids_in_domain_by_class(self.name, CaseReminderHandler):
                    self.copy_component(
                        'CaseReminderHandler', doc_id, new_domain_name, user=user)
            if share_user_roles:
                for doc_id in get_doc_ids_in_domain_by_class(self.name, UserRole):
                    self.copy_component('UserRole', doc_id, new_domain_name, user=user)

        if user:
            def add_dom_to_user(user):
                user.add_domain_membership(new_domain_name, is_admin=True)
            apply_update(user, add_dom_to_user)

        def update_events(handler):
            """
            Change the form_unique_id to the proper form for each event in a newly copied CaseReminderHandler
            """
            from corehq.apps.app_manager.models import FormBase
            for event in handler.events:
                if not event.form_unique_id:
                    continue
                form = FormBase.get_form(event.form_unique_id)
                form_app = form.get_app()
                m_index, f_index = form_app.get_form_location(form.unique_id)
                form_copy = new_app_components[form_app._id].get_module(m_index).get_form(f_index)
                event.form_unique_id = form_copy.unique_id

        def update_for_copy(handler):
            handler.active = False
            update_events(handler)

        if share_reminders:
            for handler in CaseReminderHandler.get_handlers(new_domain_name):
                apply_update(handler, update_for_copy)

        return new_domain

    def reminder_should_be_copied(self, handler):
        from corehq.apps.reminders.models import ON_DATETIME
        return (handler.start_condition_type != ON_DATETIME and
                handler.user_group_id is None)

    def copy_component(self, doc_type, id, new_domain_name, user=None):
        from corehq.apps.app_manager.models import import_app
        from corehq.apps.users.models import UserRole
        from corehq.apps.reminders.models import CaseReminderHandler
        from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem

        str_to_cls = {
            'UserRole': UserRole,
            'CaseReminderHandler': CaseReminderHandler,
            'FixtureDataType': FixtureDataType,
            'FixtureDataItem': FixtureDataItem,
        }
        if doc_type in ('Application', 'RemoteApp'):
            new_doc = import_app(id, new_domain_name)
            new_doc.copy_history.append(id)
            new_doc.case_sharing = False
            # when copying from app-docs that don't have
            # unique_id attribute on Modules
            new_doc.ensure_module_unique_ids(should_save=False)
        else:
            cls = str_to_cls[doc_type]
            db = cls.get_db()
            if doc_type == 'CaseReminderHandler':
                cur_doc = cls.get(id)
                if not self.reminder_should_be_copied(cur_doc):
                    return None

            new_id = db.copy_doc(id)['id']

            new_doc = cls.get(new_id)

            for field in self._dirty_fields:
                if hasattr(new_doc, field):
                    delattr(new_doc, field)

            if hasattr(cls, '_meta_fields'):
                for field in cls._meta_fields:
                    if not field.startswith('_') and hasattr(new_doc, field):
                        delattr(new_doc, field)

            new_doc.domain = new_domain_name

            if doc_type == 'FixtureDataType':
                new_doc.copy_from = id
                new_doc.is_global = True

        if self.is_snapshot and doc_type == 'Application':
            new_doc.prepare_multimedia_for_exchange()

        new_doc.save()
        return new_doc

    def save_snapshot(self, share_reminders, copy_by_id=None):
        if self.is_snapshot:
            return self
        else:
            try:
                copy = self.save_copy(
                    copy_by_id=copy_by_id, share_reminders=share_reminders,
                    share_user_roles=False)
            except NameUnavailableException:
                return None
            copy.is_snapshot = True
            head = self.snapshots(limit=1).first()
            if head and head.snapshot_head:
                head.snapshot_head = False
                head.save()
            copy.snapshot_head = True
            copy.snapshot_time = datetime.utcnow()
            del copy.deployment
            copy.save()
            return copy

    def snapshots(self, **view_kwargs):
        return Domain.view('domain/snapshots',
            startkey=[self._id, {}],
            endkey=[self._id],
            include_docs=True,
            reduce=False,
            descending=True,
            **view_kwargs
        )

    @memoized
    def published_snapshot(self):
        snapshots = self.snapshots().all()
        for snapshot in snapshots:
            if snapshot.published:
                return snapshot
        return None

    def update_deployment(self, **kwargs):
        self.deployment.update(kwargs)
        self.save()

    def update_internal(self, **kwargs):
        self.internal.update(kwargs)
        self.save()

    def display_name(self):
        if self.is_snapshot:
            return "Snapshot of %s" % self.copied_from.display_name()
        return self.hr_name or self.name

    def long_display_name(self):
        if self.is_snapshot:
            return format_html("Snapshot of {}", self.copied_from.display_name())
        return self.hr_name or self.name

    __str__ = long_display_name

    def get_license_display(self):
        return LICENSES.get(self.license)

    def get_license_url(self):
        return LICENSE_LINKS.get(self.license)

    def copies(self):
        return Domain.view('domain/copied_from_snapshot', key=self._id, include_docs=True)

    def copies_of_parent(self):
        return Domain.view('domain/copied_from_snapshot', keys=[s._id for s in self.copied_from.snapshots()], include_docs=True)

    def delete(self):
        self._pre_delete()
        super(Domain, self).delete()

    def _pre_delete(self):
        from corehq.apps.domain.signals import commcare_domain_pre_delete
        from corehq.apps.domain.deletion import apply_deletion_operations

        dynamic_deletion_operations = []
        results = commcare_domain_pre_delete.send_robust(sender='domain', domain=self)
        for result in results:
            response = result[1]
            if isinstance(response, Exception):
                raise DomainDeleteException(u"Error occurred during domain pre_delete {}: {}".format(self.name, str(response)))
            elif response:
                assert isinstance(response, list)
                dynamic_deletion_operations.extend(response)

        # delete all associated objects
        for db, related_doc_ids in get_all_doc_ids_for_domain_grouped_by_db(self.name):
            iter_bulk_delete(db, related_doc_ids, chunksize=500)

        apply_deletion_operations(self.name, dynamic_deletion_operations)

    def all_media(self, from_apps=None):  # todo add documentation or refactor
        from corehq.apps.hqmedia.models import CommCareMultimedia
        dom_with_media = self if not self.is_snapshot else self.copied_from

        if self.is_snapshot:
            app_ids = [app.copied_from.get_id for app in self.full_applications()]
            if from_apps:
                from_apps = set([a_id for a_id in app_ids if a_id in from_apps])
            else:
                from_apps = app_ids

        if from_apps:
            media = []
            media_ids = set()
            apps = [app for app in dom_with_media.full_applications() if app.get_id in from_apps]
            for app in apps:
                if app.doc_type != 'Application':
                    continue
                for _, m in app.get_media_objects():
                    if m.get_id not in media_ids:
                        media.append(m)
                        media_ids.add(m.get_id)
            return media

        return CommCareMultimedia.view('hqmedia/by_domain', key=dom_with_media.name, include_docs=True).all()

    def most_restrictive_licenses(self, apps_to_check=None):
        from corehq.apps.hqmedia.utils import most_restrictive
        licenses = [m.license['type'] for m in self.all_media(from_apps=apps_to_check) if m.license]
        return most_restrictive(licenses)

    @classmethod
    def get_module_by_name(cls, domain_name):
        """
        import and return the python module corresponding to domain_name, or
        None if it doesn't exist.
        """
        from corehq.apps.domain.utils import get_domain_module_map
        module_name = get_domain_module_map().get(domain_name, domain_name)

        try:
            return import_module(module_name) if module_name else None
        except ImportError:
            return None

    @property
    @memoized
    def commtrack_settings(self):
        # this import causes some dependency issues so lives in here
        from corehq.apps.commtrack.models import CommtrackConfig
        if self.commtrack_enabled:
            return CommtrackConfig.for_domain(self.name)
        else:
            return None

    @property
    def has_custom_logo(self):
        return (self['_attachments'] and
                LOGO_ATTACHMENT in self['_attachments'])

    def get_custom_logo(self):
        if not self.has_custom_logo:
            return None

        return (
            self.fetch_attachment(LOGO_ATTACHMENT),
            self['_attachments'][LOGO_ATTACHMENT]['content_type']
        )

    def get_case_display(self, case):
        """Get the properties display definition for a given case"""
        return self.case_display.case_details.get(case.type)

    def get_form_display(self, form):
        """Get the properties display definition for a given XFormInstance"""
        return self.case_display.form_details.get(form.xmlns)

    @property
    def total_downloads(self):
        """
            Returns the total number of downloads from every snapshot created from this domain
        """
        from corehq.apps.domain.dbaccessors import count_downloads_for_all_snapshots
        return count_downloads_for_all_snapshots(self.get_id)

    @property
    @memoized
    def download_count(self):
        """
            Updates and returns the total number of downloads from every sister snapshot.
        """
        if self.is_snapshot:
            self.full_downloads = self.copied_from.total_downloads
        return self.full_downloads

    @property
    @memoized
    def published_by(self):
        from corehq.apps.users.models import CouchUser
        pb_id = self.cda.user_id
        return CouchUser.get_by_user_id(pb_id) if pb_id else None

    @property
    def name_of_publisher(self):
        return self.published_by.human_friendly_name if self.published_by else ""

    @property
    def location_types(self):
        from corehq.apps.locations.models import LocationType
        return LocationType.objects.filter(domain=self.name).all()

    @memoized
    def has_privilege(self, privilege):
        from corehq.apps.accounting.utils import domain_has_privilege
        return domain_has_privilege(self, privilege)

    @property
    @memoized
    def uses_locations(self):
        from corehq import privileges
        from corehq.apps.locations.models import LocationType
        return (self.has_privilege(privileges.LOCATIONS)
                and (self.commtrack_enabled
                     or LocationType.objects.filter(domain=self.name).exists()))

    @property
    def supports_multiple_locations_per_user(self):
        """
        This method is a wrapper around the toggle that
        enables multiple location functionality. Callers of this
        method should know that this is special functionality
        left around for special applications, and not a feature
        flag that should be set normally.
        """
        return toggles.MULTIPLE_LOCATIONS_PER_USER.enabled(self.name)

    @property
    def is_onboarding_domain(self):
        # flag used for case management onboarding analytics
        if not settings.ONBOARDING_DOMAIN_TEST_DATE:
            return False
        onboarding_date = datetime(
            settings.ONBOARDING_DOMAIN_TEST_DATE[0],
            settings.ONBOARDING_DOMAIN_TEST_DATE[1],
            settings.ONBOARDING_DOMAIN_TEST_DATE[2],
        )
        return self.first_domain_for_user and self.date_created > onboarding_date


    def convert_to_commtrack(self):
        """
        One-stop-shop to make a domain CommTrack
        """
        from corehq.apps.commtrack.util import make_domain_commtrack
        make_domain_commtrack(self)

    def clear_caches(self):
        from .utils import domain_restricts_superusers
        super(Domain, self).clear_caches()
        self.get_by_name.clear(self.__class__, self.name)
        self.is_secure_session_required.clear(self.name)
        domain_restricts_superusers.clear(self.name)


class TransferDomainRequest(models.Model):
    active = models.BooleanField(default=True, blank=True)
    request_time = models.DateTimeField(null=True, blank=True)
    request_ip = models.CharField(max_length=80, null=True, blank=True)
    confirm_time = models.DateTimeField(null=True, blank=True)
    confirm_ip = models.CharField(max_length=80, null=True, blank=True)
    transfer_guid = models.CharField(max_length=32, null=True, blank=True)

    domain = models.CharField(max_length=256)
    from_username = models.CharField(max_length=80)
    to_username = models.CharField(max_length=80)

    TRANSFER_TO_EMAIL = 'domain/email/domain_transfer_to_request'
    TRANSFER_FROM_EMAIL = 'domain/email/domain_transfer_from_request'
    DIMAGI_CONFIRM_EMAIL = 'domain/email/domain_transfer_confirm'
    DIMAGI_CONFIRM_ADDRESS = 'commcarehq-support@dimagi.com'

    class Meta:
        app_label = 'domain'

    @property
    @memoized
    def to_user(self):
        from corehq.apps.users.models import WebUser
        return WebUser.get_by_username(self.to_username)

    @property
    @memoized
    def from_user(self):
        from corehq.apps.users.models import WebUser
        return WebUser.get_by_username(self.from_username)

    @classmethod
    def get_by_guid(cls, guid):
        try:
            return cls.objects.get(transfer_guid=guid, active=True)
        except TransferDomainRequest.DoesNotExist:
            return None

    @classmethod
    def get_active_transfer(cls, domain, from_username):
        try:
            return cls.objects.get(domain=domain, from_username=from_username, active=True)
        except TransferDomainRequest.DoesNotExist:
            return None
        except TransferDomainRequest.MultipleObjectsReturned:
            # Deactivate all active transfer except for most recent
            latest = cls.objects \
                .filter(domain=domain, from_username=from_username, active=True, request_time__isnull=False) \
                .latest('request_time')
            cls.objects \
                .filter(domain=domain, from_username=from_username) \
                .exclude(pk=latest.pk) \
                .update(active=False)

            return latest

    def requires_active_transfer(fn):
        def decorate(self, *args, **kwargs):
            if not self.active:
                raise InactiveTransferDomainException(_("Transfer domain request is no longer active"))
            return fn(self, *args, **kwargs)
        return decorate

    @requires_active_transfer
    def send_transfer_request(self):
        self.transfer_guid = uuid.uuid4().hex
        self.request_time = datetime.utcnow()
        self.save()

        self.email_to_request()
        self.email_from_request()

    def activate_url(self):
        return u"{url_base}/domain/transfer/{guid}/activate".format(
            url_base=get_url_base(),
            guid=self.transfer_guid
        )

    def deactivate_url(self):
        return u"{url_base}/domain/transfer/{guid}/deactivate".format(
            url_base=get_url_base(),
            guid=self.transfer_guid
        )

    def email_to_request(self):
        context = self.as_dict()

        html_content = render_to_string("{template}.html".format(template=self.TRANSFER_TO_EMAIL), context)
        text_content = render_to_string("{template}.txt".format(template=self.TRANSFER_TO_EMAIL), context)

        send_html_email_async.delay(
            _(u'Transfer of ownership for CommCare project space.'),
            self.to_user.email,
            html_content,
            text_content=text_content)

    def email_from_request(self):
        context = self.as_dict()
        context['settings_url'] = u"{url_base}{path}".format(
            url_base=get_url_base(),
            path=reverse('transfer_domain_view', args=[self.domain]))

        html_content = render_to_string("{template}.html".format(template=self.TRANSFER_FROM_EMAIL), context)
        text_content = render_to_string("{template}.txt".format(template=self.TRANSFER_FROM_EMAIL), context)

        send_html_email_async.delay(
            _(u'Transfer of ownership for CommCare project space.'),
            self.from_user.email,
            html_content,
            text_content=text_content)

    @requires_active_transfer
    def transfer_domain(self, *args, **kwargs):

        self.confirm_time = datetime.utcnow()
        if 'ip' in kwargs:
            self.confirm_ip = kwargs['ip']

        self.from_user.transfer_domain_membership(self.domain, self.to_user, is_admin=True)
        self.from_user.save()
        self.to_user.save()
        self.active = False
        self.save()

        html_content = render_to_string(
            "{template}.html".format(template=self.DIMAGI_CONFIRM_EMAIL),
            self.as_dict())
        text_content = render_to_string(
            "{template}.txt".format(template=self.DIMAGI_CONFIRM_EMAIL),
            self.as_dict())

        send_html_email_async.delay(
            _(u'There has been a transfer of ownership of {domain}').format(
                domain=self.domain), self.DIMAGI_CONFIRM_ADDRESS,
            html_content, text_content=text_content
        )

    def as_dict(self):
        return {
            'domain': self.domain,
            'from_username': self.from_username,
            'to_username': self.to_username,
            'guid': self.transfer_guid,
            'request_time': self.request_time,
            'deactivate_url': self.deactivate_url(),
            'activate_url': self.activate_url(),
        }
