import uuid
from collections import defaultdict
from datetime import datetime
from functools import reduce

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.db import models
from django.db.models import F
from django.contrib.postgres.fields import ArrayField
from django.db.transaction import atomic
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from memoized import memoized

from couchforms.analytics import domain_has_submission_in_last_30_days
from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DateTimeProperty,
    DecimalProperty,
    DictProperty,
    Document,
    DocumentSchema,
    IntegerProperty,
    SchemaListProperty,
    SchemaProperty,
    StringListProperty,
    StringProperty,
    TimeProperty,
)
from dimagi.utils.couch.database import (
    get_safe_write_kwargs,
    iter_bulk_delete,
    iter_docs,
)
from dimagi.utils.logging import log_signal_errors
from dimagi.utils.next_available_name import next_available_name
from dimagi.utils.web import get_url_base

from corehq import toggles
from corehq.apps.app_manager.const import (
    AMPLIFIES_NO,
    AMPLIFIES_NOT_SET,
    AMPLIFIES_YES,
)
from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.appstore.models import SnapshotMixin
from corehq.apps.cachehq.mixins import QuickCachedDocumentMixin
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.util import log_user_change
from corehq.blobs import CODES as BLOB_CODES
from corehq.blobs.mixin import BlobMixin
from corehq.dbaccessors.couchapps.all_docs import (
    get_all_doc_ids_for_domain_grouped_by_db,
)
from corehq.util.quickcache import quickcache, get_session_key
from corehq.util.soft_assert import soft_assert
from langcodes import langs as all_langs

from .exceptions import (
    InactiveTransferDomainException,
    NameUnavailableException,
)
from .project_access.models import SuperuserProjectEntryRecord  # noqa

from django.core.validators import MaxValueValidator, MinValueValidator

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

# These are the UCR Expressions (Data Transformation Engine expressions) that are not currently
# supported by SaaS. If any domain wants to use them them it can be
# enabled from  Project Settings > Project Information Internal
RESTRICTED_UCR_EXPRESSIONS = [
    ('base_item_expression', 'Base Item Expressions'),
    ('related_doc', 'Related Document Expressions')
]


def all_restricted_ucr_expressions():
    return [exp[0] for exp in RESTRICTED_UCR_EXPRESSIONS]


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


def icds_conditional_session_key():
    if settings.SERVER_ENVIRONMENT in settings.ICDS_ENVS:
        # memoize for process lifecycle
        return None
    else:
        # memoize for request lifecycle
        return get_session_key


class UpdatableSchema(object):

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

    form_datasource_enabled = BooleanProperty(default=True)
    case_datasource_enabled = BooleanProperty(default=True)
    case_actions_datasource_enabled = BooleanProperty(default=True)

    def fixtures_are_active(self):
        return self.enabled and self.use_fixtures

    def config_is_valid(self):
        return (self.use_user_location_as_owner or self.case_owner_id) and self.case_type

    def update_from_app_config(self, config):
        """Update datasources enabled based on app config.

        Follows similar logic to CallCenterIndicators
        :returns: True if changes were made
        """
        pre = (self.form_datasource_enabled, self.case_datasource_enabled, self.case_actions_datasource_enabled)
        self.form_datasource_enabled = config.forms_submitted.enabled or bool(config.custom_form)
        self.case_datasource_enabled = (
            config.cases_total.enabled
            or config.cases_opened.enabled
            or config.cases_closed.enabled
        )
        self.case_actions_datasource_enabled = config.cases_active.enabled
        post = (self.form_datasource_enabled, self.case_datasource_enabled, self.case_actions_datasource_enabled)
        return pre != post


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
    partner_technical_competency = IntegerProperty()
    support_prioritization = IntegerProperty()
    gs_continued_involvement = StringProperty()
    technical_complexity = StringProperty()
    app_design_comments = StringProperty()
    training_materials = StringProperty()
    partner_comments = StringProperty()
    partner_contact = StringProperty()
    dimagi_contact = StringProperty()


class CaseDisplaySettings(DocumentSchema):
    case_details = DictProperty(
        verbose_name="Mapping of case type to definitions of properties "
                     "to display above the fold on case details")
    form_details = DictProperty(
        verbose_name="Mapping of form xmlns to definitions of properties "
                     "to display for individual forms")


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


class Domain(QuickCachedDocumentMixin, BlobMixin, Document, SnapshotMixin):
    """
        Domain is the highest level collection of people/stuff
        in the system.  Pretty much everything happens at the
        domain-level, including user membership, permission to
        see data, reports, charts, etc.

        Exceptions: accounting has some models that combine multiple domains,
        which make "enterprise" multi-domain features like the enterprise console possible.

        Naming conventions:
        Most often, variables representing domain names are named `domain`, and
        variables representing domain objects are named `domain_obj`. New code should
        follow this convention, unless it's in an area that consistently uses `domain`
        for the object and `domain_name` for the string.

        There's a `project` attribute attached to requests that's a domain object.
        In spite of this, don't use `project` in new code.
   """

    _blobdb_type_code = BLOB_CODES.domain

    name = StringProperty()
    is_active = BooleanProperty()
    # date_created is expected to be a naive datetime specified in UTC
    # Defaulting to a lambda rather than utcnow directly to make freezegun function. Not ideal
    date_created = DateTimeProperty(default=lambda: datetime.utcnow())
    default_timezone = StringProperty(default=getattr(settings, "TIME_ZONE", "UTC"))
    default_geocoder_location = DictProperty()
    case_sharing = BooleanProperty(default=False)
    secure_submissions = BooleanProperty(default=False)
    cloudcare_releases = StringProperty(choices=['stars', 'nostars', 'default'], default='default')
    organization = StringProperty()
    hr_name = StringProperty()  # the human-readable name for this project
    project_description = StringProperty()  # Brief description of the project
    creating_user = StringProperty()  # username of the user who created this domain

    # domain metadata
    project_type = StringProperty()  # e.g. MCH, HIV
    is_test = StringProperty(choices=["true", "false", "none"], default="none")
    description = StringProperty()
    short_description = StringProperty()
    is_shared = BooleanProperty(default=False)
    commtrack_enabled = BooleanProperty(default=False)
    call_center_config = SchemaProperty(CallCenterProperties)
    restrict_superusers = BooleanProperty(default=False)
    allow_domain_requests = BooleanProperty(default=False)
    location_restriction_for_users = BooleanProperty(default=False)
    usercase_enabled = BooleanProperty(default=False)
    hipaa_compliant = BooleanProperty(default=False)
    first_domain_for_user = BooleanProperty(default=False)

    # CommConnect settings
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
    sms_language_fallback = StringProperty()
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
    enable_registration_welcome_sms_for_case = BooleanProperty(default=False)
    enable_registration_welcome_sms_for_mobile_worker = BooleanProperty(default=False)
    sms_worker_registration_alert_emails = StringListProperty()
    sms_survey_date_format = StringProperty()

    granted_messaging_access = BooleanProperty(default=False)

    # Allowed outbound SMS per day
    # If this is None, then the default is applied. See get_daily_outbound_sms_limit()
    custom_daily_outbound_sms_limit = IntegerProperty()

    # Twilio Whatsapp-enabled phone number
    twilio_whatsapp_phone_number = StringProperty()

    # Allowed number of case updates or closes from automatic update rules in the daily rule run.
    # If this value is None, the value in settings.MAX_RULE_UPDATES_IN_ONE_RUN is used.
    auto_case_update_limit = IntegerProperty()

    # Time to run auto case update rules. Expected values are 0-23.
    # If this value is None, the value in settings.RULE_UPDATE_HOUR is used.
    auto_case_update_hour = IntegerProperty()

    # Allowed number of max OData feeds that this domain can create.
    # NOTE: This value is generally None. If you want the value the system will use,
    # please use the `get_odata_feed_limit` method instead
    odata_feed_limit = IntegerProperty()

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

    cached_properties = DictProperty()

    internal = SchemaProperty(InternalProperties)

    # extra user specified properties
    tags = StringListProperty()
    area = StringProperty(choices=AREA_CHOICES)
    sub_area = StringProperty(choices=SUB_AREA_CHOICES)

    last_modified = DateTimeProperty(default=datetime(2015, 1, 1))

    # when turned on, use settings.SECURE_TIMEOUT for sessions of users who are members of this domain
    secure_sessions = BooleanProperty(default=False)
    secure_sessions_timeout = IntegerProperty()

    two_factor_auth = BooleanProperty(default=False)
    strong_mobile_passwords = BooleanProperty(default=False)
    disable_mobile_login_lockout = BooleanProperty(default=False)
    allow_invite_email_only = BooleanProperty(default=False)

    requested_report_builder_subscription = StringListProperty()

    # seconds between sending mobile UCRs to users. Can be overridden per user
    default_mobile_ucr_sync_interval = IntegerProperty()

    ga_opt_out = BooleanProperty(default=False)
    orphan_case_alerts_warning = BooleanProperty(default=False)

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

        if 'granted_messaging_access' not in data:
            # enable messaging for domains created before this flag was added
            data['granted_messaging_access'] = True

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
        domain_obj = Domain.get_by_name(name)
        return domain_obj and domain_obj.secure_sessions

    @staticmethod
    @quickcache(['name'], timeout=24 * 60 * 60)
    def secure_timeout(name):
        domain_obj = Domain.get_by_name(name)
        if not domain_obj:
            return None

        if domain_obj.secure_sessions:
            if toggles.SECURE_SESSION_TIMEOUT.enabled(name):
                return domain_obj.secure_sessions_timeout or settings.SECURE_TIMEOUT
            return settings.SECURE_TIMEOUT

        return None

    @staticmethod
    @quickcache(['couch_user._id', 'is_active'], timeout=5 * 60, memoize_timeout=10)
    def active_for_couch_user(couch_user, is_active=True):
        domain_names = couch_user.get_domains()
        return Domain.view(
            "domain/by_status",
            keys=[[is_active, d] for d in domain_names],
            reduce=False,
            include_docs=True,
        ).all()

    @staticmethod
    def active_for_user(user, is_active=True):
        if isinstance(user, AnonymousUser):
            return []
        from corehq.apps.users.models import CouchUser
        if isinstance(user, CouchUser):
            couch_user = user
        else:
            couch_user = CouchUser.from_django_user(user)
        if couch_user:
            return Domain.active_for_couch_user(couch_user, is_active=is_active)
        else:
            return []

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
    def has_media(self):
        from corehq.apps.app_manager.util import is_remote_app
        for app in self.full_applications():
            if not is_remote_app(app) and app.has_media():
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

    @classmethod
    @quickcache(['name'], skip_arg='strict', timeout=30 * 60,
        session_function=icds_conditional_session_key())
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
    def get_or_create_with_name(cls, name, is_active=False, secure_submissions=True):
        result = cls.view("domain/domains", key=name, reduce=False, include_docs=True).first()
        if result:
            return result
        else:
            new_domain = Domain(
                name=name,
                is_active=is_active,
                date_created=datetime.utcnow(),
                secure_submissions=secure_submissions,
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
        from corehq.apps.domain.dbaccessors import domain_or_deleted_domain_exists
        name = get_domain_url_slug(hr_name, max_length=max_length)
        if not name:
            raise NameUnavailableException
        if domain_or_deleted_domain_exists(name):
            prefix = name
            while len(prefix):
                name = next_available_name(prefix, Domain.get_names_by_prefix(prefix + '-'))
                if domain_or_deleted_domain_exists(name):
                    # should never happen
                    raise NameUnavailableException
                if len(name) <= max_length:
                    return name
                prefix = prefix[:-1]
            raise NameUnavailableException

        return name

    @classmethod
    def get_all(cls, include_docs=True, include_snapshots=False):
        domains = Domain.view("domain/not_snapshots", include_docs=False).all()
        if include_snapshots:
            snapshots = Domain.get_db().view("domain/snapshots", include_docs=True, reduce=False).all()
            # make snapshots look like items returned from domains/not_snapshots view
            snapshots = [{'id': d['id'], 'key': d['doc']['name'], 'value': None} for d in snapshots]
            domains = domains + snapshots
        if not include_docs:
            return domains
        else:
            return map(cls.wrap, iter_docs(cls.get_db(), [d['id'] for d in domains]))

    @classmethod
    def get_all_names(cls, include_snapshots=False):
        return sorted({d['key'] for d in cls.get_all(include_docs=False, include_snapshots=include_snapshots)})

    @classmethod
    def get_deleted_domain_names(cls):
        domains = Domain.view("domain/deleted_domains", include_docs=False, reduce=False).all()
        return {d['key'] for d in domains}

    @classmethod
    def get_all_ids(cls):
        return [d['id'] for d in cls.get_all(include_docs=False)]

    @classmethod
    def get_names_by_prefix(cls, prefix):
        return [d['key'] for d in Domain.view(
            "domain/domains",
            startkey=prefix,
            endkey=prefix + "zzz",
            reduce=False,
            include_docs=False
        ).all()] + [d['key'] for d in Domain.view(
            "domain/deleted_domains",
            startkey=prefix,
            endkey=prefix + "zzz",
            reduce=False,
            include_docs=False
        ).all()]

    def case_sharing_included(self):
        return self.case_sharing or reduce(
            lambda x, y: x or y, [getattr(app, 'case_sharing', False) for app in self.applications()], False
        )

    def save(self, **params):
        from corehq.apps.domain.dbaccessors import domain_or_deleted_domain_exists

        self.last_modified = datetime.utcnow()
        if not self._rev:
            if domain_or_deleted_domain_exists(self.name):
                raise NameUnavailableException(self.name)
        super(Domain, self).save(**params)

        from corehq.apps.domain.signals import commcare_domain_post_save
        results = commcare_domain_post_save.send_robust(sender='domain', domain=self)
        log_signal_errors(results, "Error occurred during domain post_save (%s)", {'domain': self.name})

    def snapshots(self, **view_kwargs):
        return Domain.view('domain/snapshots',
            startkey=[self._id, {}],
            endkey=[self._id],
            include_docs=True,
            reduce=False,
            descending=True,
            **view_kwargs
        )

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

    __str__ = display_name

    def get_license_display(self):
        return LICENSES.get(self.license)

    def get_license_url(self):
        return LICENSE_LINKS.get(self.license)

    def copies(self):
        return Domain.view('domain/copied_from_snapshot', key=self._id, include_docs=True)

    def copies_of_parent(self):
        return Domain.view(
            'domain/copied_from_snapshot', keys=[s._id for s in self.copied_from.snapshots()], include_docs=True
        )

    def delete(self, leave_tombstone=False):
        if not leave_tombstone and not settings.UNIT_TESTING:
            raise ValueError(
                'Cannot delete domain without leaving a tombstone except during testing')
        self._pre_delete()
        if leave_tombstone:
            domain = self.get(self._id)
            if not domain.doc_type.endswith('-Deleted'):
                domain.doc_type = '{}-Deleted'.format(domain.doc_type)
                domain.save()
        else:
            super().delete()

        # The save signals can undo effect of clearing the cache within the save
        # because they query the stale view (but attaches the up to date doc).
        # This is only a problem on delete/soft-delete,
        # because these change the presence in the index, not just the doc content.
        # Since this is rare, I'm opting to just re-clear the cache here
        # rather than making the signals use a strict lookup or something like that.
        self.clear_caches()

    def _pre_delete(self):
        from corehq.apps.domain.deletion import apply_deletion_operations

        # delete SQL models first because UCR tables are indexed by configs in couch
        apply_deletion_operations(self.name)

        # delete couch docs
        for db, related_doc_ids in get_all_doc_ids_for_domain_grouped_by_db(self.name):
            iter_bulk_delete(db, related_doc_ids, chunksize=500)

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
        return self.has_attachment(LOGO_ATTACHMENT)

    def get_custom_logo(self):
        if not self.has_custom_logo:
            return None

        return (
            self.fetch_attachment(LOGO_ATTACHMENT),
            self.blobs[LOGO_ATTACHMENT].content_type
        )

    def get_odata_feed_limit(self):
        return self.odata_feed_limit or settings.DEFAULT_ODATA_FEED_LIMIT

    def put_attachment(self, *args, **kw):
        return super(Domain, self).put_attachment(domain=self.name, *args, **kw)

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
        self.secure_timeout.clear(self.name)
        domain_restricts_superusers.clear(self.name)

    def get_daily_outbound_sms_limit(self):
        if self.custom_daily_outbound_sms_limit:
            return self.custom_daily_outbound_sms_limit

        # https://manage.dimagi.com/default.asp?274299
        return 50000


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

    class Meta(object):
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
        return "{url_base}/domain/transfer/{guid}/activate".format(
            url_base=get_url_base(),
            guid=self.transfer_guid
        )

    def deactivate_url(self):
        return "{url_base}/domain/transfer/{guid}/deactivate".format(
            url_base=get_url_base(),
            guid=self.transfer_guid
        )

    def email_to_request(self):
        context = self.as_dict()

        html_content = render_to_string("{template}.html".format(template=self.TRANSFER_TO_EMAIL), context)
        text_content = render_to_string("{template}.txt".format(template=self.TRANSFER_TO_EMAIL), context)

        send_html_email_async.delay(
            _('Transfer of ownership for CommCare project space.'),
            self.to_user.get_email(),
            html_content,
            text_content=text_content,
            domain=self.domain,
            use_domain_gateway=True,
        )

    def email_from_request(self):
        context = self.as_dict()
        context.update({
            'settings_url': "{url_base}{path}".format(url_base=get_url_base(),
                                                      path=reverse('transfer_domain_view', args=[self.domain])),
            'support_email': settings.SUPPORT_EMAIL,
        })

        html_content = render_to_string("{template}.html".format(template=self.TRANSFER_FROM_EMAIL), context)
        text_content = render_to_string("{template}.txt".format(template=self.TRANSFER_FROM_EMAIL), context)

        send_html_email_async.delay(
            _('Transfer of ownership for CommCare project space.'),
            self.from_user.get_email(),
            html_content,
            text_content=text_content,
            domain=self.domain,
            use_domain_gateway=True,
        )

    @requires_active_transfer
    def transfer_domain(self, by_user, *args, transfer_via=None, **kwargs):

        self.confirm_time = datetime.utcnow()
        if 'ip' in kwargs:
            self.confirm_ip = kwargs['ip']

        self.from_user.transfer_domain_membership(self.domain, self.to_user, is_admin=True)
        self.from_user.save()
        if by_user:
            log_user_change(by_domain=self.domain, for_domain=self.domain, couch_user=self.from_user,
                            changed_by_user=by_user, changed_via=transfer_via,
                            change_messages=UserChangeMessage.domain_removal(self.domain))
            log_user_change(by_domain=self.domain, for_domain=self.domain, couch_user=self.to_user,
                            changed_by_user=by_user, changed_via=transfer_via,
                            change_messages=UserChangeMessage.domain_addition(self.domain))
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
            _('There has been a transfer of ownership of {domain}').format(domain=self.domain),
            settings.SUPPORT_EMAIL, html_content, text_content=text_content,
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


class DomainAuditRecordEntry(models.Model):
    domain = models.TextField(unique=True, db_index=True)
    cp_n_downloads_custom_exports = models.BigIntegerField(default=0)
    cp_n_viewed_ucr_reports = models.BigIntegerField(default=0)
    cp_n_viewed_non_ucr_reports = models.BigIntegerField(default=0)
    cp_n_reports_created = models.BigIntegerField(default=0)
    cp_n_reports_edited = models.BigIntegerField(default=0)
    cp_n_saved_scheduled_reports = models.BigIntegerField(default=0)
    cp_n_click_app_deploy = models.BigIntegerField(default=0)
    cp_n_form_builder_entered = models.BigIntegerField(default=0)
    cp_n_saved_app_changes = models.BigIntegerField(default=0)

    @classmethod
    @atomic
    def update_calculations(cls, domain, property_to_update):
        obj, is_new = cls.objects.get_or_create(domain=domain)
        setattr(obj, property_to_update, F(property_to_update) + 1)
        # update_fields prevents the possibility of a race condition
        # https://stackoverflow.com/a/1599090
        obj.save(update_fields=[property_to_update])


class AllowedUCRExpressionSettings(models.Model):
    """
    Model contains UCR(aka Data Transformation Engine) expressions settings for a domain.
    The expressions defined in RESTRICTED_UCR_EXPRESSIONS are not generally available yet.
    But these expressions are enabled by default on every domain so that current flow does not change.
    If any expression's usage is to be restricted on any domain
    then the  Expressions should be explicitly removed from
    Domain settings page on HQ.
    """

    domain = models.CharField(unique=True, max_length=256)
    allowed_ucr_expressions = ArrayField(
        models.CharField(max_length=32, choices=RESTRICTED_UCR_EXPRESSIONS),
        default=all_restricted_ucr_expressions
    )

    @classmethod
    @quickcache(['domain_name'])
    def get_allowed_ucr_expressions(cls, domain_name):
        try:
            ucr_expressions_obj = AllowedUCRExpressionSettings.objects.get(domain=domain_name)
            allowed_ucr_expressions = ucr_expressions_obj.allowed_ucr_expressions
        except AllowedUCRExpressionSettings.DoesNotExist:
            allowed_ucr_expressions = all_restricted_ucr_expressions()
        return allowed_ucr_expressions

    @classmethod
    def save_allowed_ucr_expressions(cls, domain_name, expressions):
        AllowedUCRExpressionSettings.objects.update_or_create(
            domain=domain_name,
            defaults={
                'allowed_ucr_expressions': expressions
            }
        )

    @classmethod
    def disallowed_ucr_expressions(cls, domain_name):
        allowed_expressions_for_domain = set(cls.get_allowed_ucr_expressions(domain_name))
        restricted_expressions = set(all_restricted_ucr_expressions())
        return restricted_expressions - allowed_expressions_for_domain


class ProjectLimitType():
    LIVE_GOOGLE_SHEETS = 'lgs'

    CHOICES = (
        (LIVE_GOOGLE_SHEETS, "Live Google Sheets"),
    )


class ProjectLimit(models.Model):
    domain = models.CharField(max_length=256, db_index=True)
    limit_type = models.CharField(max_length=5, choices=ProjectLimitType.CHOICES)
    limit_value = models.IntegerField(default=20)


class OperatorCallLimitSettings(models.Model):
    CALL_LIMIT_MINIMUM = 1
    CALL_LIMIT_MAXIMUM = 1000
    CALL_LIMIT_DEFAULT = 120

    domain = models.CharField(max_length=256, db_index=True)
    call_limit = models.IntegerField(
        default=CALL_LIMIT_DEFAULT,
        validators=[
            MinValueValidator(CALL_LIMIT_MINIMUM),
            MaxValueValidator(CALL_LIMIT_MAXIMUM)
        ]
    )


class SMSAccountConfirmationSettings(models.Model):
    PROJECT_NAME_DEFAULT = "CommCare HQ"
    PROJECT_NAME_MAX_LENGTH = 30
    CONFIRMATION_LINK_EXPIRY_DAYS_DEFAULT = 14
    CONFIRMATION_LINK_EXPIRY_DAYS_MINIMUM = 1
    CONFIRMATION_LINK_EXPIRY_DAYS_MAXIMUM = 30

    domain = models.CharField(max_length=256, db_index=True)
    project_name = models.CharField(
        default=PROJECT_NAME_DEFAULT,
        max_length=PROJECT_NAME_MAX_LENGTH,
    )
    confirmation_link_expiry_time = models.IntegerField(
        default=CONFIRMATION_LINK_EXPIRY_DAYS_DEFAULT,
        validators=[
            MinValueValidator(CONFIRMATION_LINK_EXPIRY_DAYS_MINIMUM),
            MaxValueValidator(CONFIRMATION_LINK_EXPIRY_DAYS_MAXIMUM),
        ]
    )

    @staticmethod
    def get_settings(domain):
        domain_obj, _ = SMSAccountConfirmationSettings.objects.get_or_create(domain=domain)
        return domain_obj


class AppReleaseModeSetting(models.Model):

    domain = models.CharField(max_length=256, db_index=True, unique=True)
    is_visible = models.BooleanField(default=False)

    @staticmethod
    def get_settings(domain):
        domain_obj, created = AppReleaseModeSetting.objects.get_or_create(domain=domain)
        return domain_obj
