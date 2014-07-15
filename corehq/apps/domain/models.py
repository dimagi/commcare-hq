from datetime import datetime, timedelta
import hashlib
import json
import logging
from couchdbkit.exceptions import ResourceConflict
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from couchdbkit.ext.django.schema import (
    Document, StringProperty, BooleanProperty, DateTimeProperty, IntegerProperty,
    DocumentSchema, SchemaProperty, DictProperty,
    StringListProperty, SchemaListProperty, TimeProperty, DecimalProperty
)
from django.core.cache import cache
from corehq.apps.appstore.models import Review, SnapshotMixin
from dimagi.utils.couch.cache import cache_core
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.html import format_html
from dimagi.utils.logging import notify_exception
from dimagi.utils.couch.database import get_db, get_safe_write_kwargs, apply_update
from itertools import chain
from langcodes import langs as all_langs
from collections import defaultdict
from django.utils.importlib import import_module


lang_lookup = defaultdict(str)

DATA_DICT = settings.INTERNAL_DATA
AREA_CHOICES = [a["name"] for a in DATA_DICT["area"]]
SUB_AREA_CHOICES = reduce(list.__add__, [a["sub_areas"] for a in DATA_DICT["area"]], [])

for lang in all_langs:
    lang_lookup[lang['three']] = lang['names'][0] # arbitrarily using the first name if there are multiple
    if lang['two'] != '':
        lang_lookup[lang['two']] = lang['names'][0]

class DomainMigrations(DocumentSchema):
    has_migrated_permissions = BooleanProperty(default=False)

    def apply(self, domain):
        if not self.has_migrated_permissions:
            logging.info("Applying permissions migration to domain %s" % domain.name)
            from corehq.apps.users.models import UserRole, WebUser
            UserRole.init_domain_with_presets(domain.name)
            for web_user in WebUser.by_domain(domain.name):
                try:
                    web_user.save()
                except ResourceConflict:
                    # web_user has already been saved by another thread in the last few seconds
                    pass

            self.has_migrated_permissions = True
            domain.save()

LICENSES = {
    'cc': 'Creative Commons Attribution',
    'cc-sa': 'Creative Commons Attribution, Share Alike',
    'cc-nd': 'Creative Commons Attribution, No Derivatives',
    'cc-nc': 'Creative Commons Attribution, Non-Commercial',
    'cc-nc-sa': 'Creative Commons Attribution, Non-Commercial, and Share Alike',
    'cc-nc-nd': 'Creative Commons Attribution, Non-Commercial, and No Derivatives',
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
    date = DateTimeProperty()
    city = StringProperty()
    country = StringProperty()
    region = StringProperty() # e.g. US, LAC, SA, Sub-saharn Africa, East Africa, West Africa, Southeast Asia)
    description = StringProperty()
    public = BooleanProperty(default=False)

class CallCenterProperties(DocumentSchema):
    enabled = BooleanProperty(default=False)
    case_owner_id = StringProperty()
    case_type = StringProperty()

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
    services = StringProperty(choices=["", "basic", "plus", "full", "custom"], default="")
    initiative = StringListProperty()
    workshop_region = StringProperty()
    project_state = StringProperty(choices=["", "POC", "transition", "at-scale"], default="")
    self_started = BooleanProperty()
    area = StringProperty()
    sub_area = StringProperty()
    using_adm = BooleanProperty()
    using_call_center = BooleanProperty()
    custom_eula = BooleanProperty()
    can_use_data = BooleanProperty()
    notes = StringProperty()
    organization_name = StringProperty()
    platform = StringListProperty()
    project_manager = StringProperty()
    phone_model = StringProperty()
    goal_time_period = IntegerProperty()
    goal_followup_rate = DecimalProperty()


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
    report = StringProperty() # fully-qualified path to template report class
    name = StringProperty() # report display name in sidebar
    kwargs = DictProperty() # arbitrary settings to configure report
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

class Domain(Document, SnapshotMixin):
    """Domain is the highest level collection of people/stuff
       in the system.  Pretty much everything happens at the
       domain-level, including user membership, permission to
       see data, reports, charts, etc."""

    name = StringProperty()
    is_active = BooleanProperty()
    is_public = BooleanProperty(default=False)
    date_created = DateTimeProperty()
    default_timezone = StringProperty(default=getattr(settings, "TIME_ZONE", "UTC"))
    case_sharing = BooleanProperty(default=False)
    secure_submissions = BooleanProperty(default=False)
    ota_restore_caching = BooleanProperty(default=False)
    cloudcare_releases = StringProperty(choices=['stars', 'nostars', 'default'], default='default')
    organization = StringProperty()
    hr_name = StringProperty() # the human-readable name for this project within an organization
    creating_user = StringProperty() # username of the user who created this domain

    # domain metadata
    project_type = StringProperty() # e.g. MCH, HIV
    customer_type = StringProperty() # plus, full, etc.
    is_test = StringProperty(choices=["true", "false", "none"], default="none")
    description = StringProperty()
    short_description = StringProperty()
    is_shared = BooleanProperty(default=False)
    commtrack_enabled = BooleanProperty(default=False)
    call_center_config = SchemaProperty(CallCenterProperties)
    has_careplan = BooleanProperty(default=False)
    restrict_superusers = BooleanProperty(default=False)
    location_restriction_for_users = BooleanProperty(default=True)

    case_display = SchemaProperty(CaseDisplaySettings)

    # CommConnect settings
    commconnect_enabled = BooleanProperty(default=False)
    survey_management_enabled = BooleanProperty(default=False)
    sms_case_registration_enabled = BooleanProperty(default=False) # Whether or not a case can register via sms
    sms_case_registration_type = StringProperty() # Case type to apply to cases registered via sms
    sms_case_registration_owner_id = StringProperty() # Owner to apply to cases registered via sms
    sms_case_registration_user_id = StringProperty() # Submitting user to apply to cases registered via sms
    sms_mobile_worker_registration_enabled = BooleanProperty(default=False) # Whether or not a mobile worker can register via sms
    default_sms_backend_id = StringProperty()
    use_default_sms_response = BooleanProperty(default=False)
    default_sms_response = StringProperty()
    chat_message_count_threshold = IntegerProperty()
    custom_chat_template = StringProperty() # See settings.CUSTOM_CHAT_TEMPLATES
    custom_case_username = StringProperty() # Case property to use when showing the case's name in a chat window
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
    send_to_duplicated_case_numbers = BooleanProperty(default=False)

    # exchange/domain copying stuff
    is_snapshot = BooleanProperty(default=False)
    is_approved = BooleanProperty(default=False)
    snapshot_time = DateTimeProperty()
    published = BooleanProperty(default=False)
    license = StringProperty(choices=LICENSES, default='cc')
    title = StringProperty()
    cda = SchemaProperty(LicenseAgreement)
    multimedia_included = BooleanProperty(default=True)
    downloads = IntegerProperty(default=0) # number of downloads for this specific snapshot
    full_downloads = IntegerProperty(default=0) # number of downloads for all snapshots from this domain
    author = StringProperty()
    phone_model = StringProperty()
    attribution_notes = StringProperty()
    publisher = StringProperty(choices=["organization", "user"], default="user")
    yt_id = StringProperty()

    deployment = SchemaProperty(Deployment)

    image_path = StringProperty()
    image_type = StringProperty()

    migrations = SchemaProperty(DomainMigrations)

    cached_properties = DictProperty()

    internal = SchemaProperty(InternalProperties)

    dynamic_reports = SchemaListProperty(DynamicReportSet)

    # extra user specified properties
    tags = StringListProperty()
    area = StringProperty(choices=AREA_CHOICES)
    sub_area = StringProperty(choices=SUB_AREA_CHOICES)
    launch_date = DateTimeProperty

    # to be eliminated from projects and related documents when they are copied for the exchange
    _dirty_fields = ('admin_password', 'admin_password_charset', 'city', 'country', 'region', 'customer_type')

    default_mobile_worker_redirect = StringProperty(default=None)

    @property
    def domain_type(self):
        """
        The primary type of this domain.  Used to determine site-specific
        branding.
        """
        if self.commtrack_enabled:
            return 'commtrack'
        else:
            return 'commcare'

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

        self = super(Domain, cls).wrap(data)
        if self.deployment is None:
            self.deployment = Deployment()
        if self.get_id:
            self.apply_migrations()
        if should_save:
            self.save()
        return self

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
            domain_names = couch_user.get_domains()
            return cache_core.cached_view(Domain.get_db(), "domain/by_status",
                                          keys=[[is_active, d] for d in domain_names],
                                          reduce=False,
                                          include_docs=True,
                                          wrapper=Domain.wrap
            )
        else:
            return []

    @classmethod
    def field_by_prefix(cls, field, prefix='', is_approved=True):
        # unichr(0xfff8) is something close to the highest character available
        res = cls.view("domain/fields_by_prefix",
                                    group=True,
                                    startkey=[field, is_approved, prefix],
                                    endkey=[field, is_approved, "%s%c" % (prefix, unichr(0xfff8)), {}])
        vals = [(d['value'], d['key'][2]) for d in res]
        vals.sort(reverse=True)
        return [(v[1], v[0]) for v in vals]

    @classmethod
    def get_by_field(cls, field, value, is_approved=True):
        return cls.view('domain/fields_by_prefix', key=[field, is_approved, value], reduce=False, include_docs=True).all()

    def apply_migrations(self):
        self.migrations.apply(self)

    @staticmethod
    def all_for_user(user):
        if not hasattr(user,'get_profile'):
            # this had better be an anonymous user
            return []
        from corehq.apps.users.models import CouchUser
        couch_user = CouchUser.from_django_user(user)
        if couch_user:
            domain_names = couch_user.get_domains()
            return Domain.view("domain/domains",
                keys=domain_names,
                reduce=False,
                include_docs=True).all()
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
        from corehq.apps.app_manager.models import ApplicationBase
        return ApplicationBase.view('app_manager/applications_brief',
                                    startkey=[self.name],
                                    endkey=[self.name, {}]).all()

    def full_applications(self, include_builds=True):
        from corehq.apps.app_manager.models import Application, RemoteApp
        WRAPPERS = {'Application': Application, 'RemoteApp': RemoteApp}
        def wrap_application(a):
            return WRAPPERS[a['doc']['doc_type']].wrap(a['doc'])

        if include_builds:
            startkey = [self.name]
            endkey = [self.name, {}]
        else:
            startkey = [self.name, None]
            endkey = [self.name, None, {}]

        return get_db().view('app_manager/applications',
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

    def has_shared_media(self):
        return False

    def recent_submissions(self):
        from corehq.apps.reports.util import make_form_couch_key
        key = make_form_couch_key(self.name)
        res = get_db().view('reports_forms/all_forms',
            startkey=key+[{}],
            endkey=key,
            descending=True,
            reduce=False,
            include_docs=False,
            limit=1).all()
        if len(res) > 0: # if there have been any submissions in the past 30 days
            return (datetime.now() <=
                    datetime.strptime(res[0]['key'][2], "%Y-%m-%dT%H:%M:%SZ")
                    + timedelta(days=30))
        else:
            return False

    @cached_property
    def languages(self):
        apps = self.applications()
        return set(chain.from_iterable([a.langs for a in apps]))

    def readable_languages(self):
        return ', '.join(lang_lookup[lang] or lang for lang in self.languages())

    def __unicode__(self):
        return self.name

    @classmethod
    def get_by_name(cls, name, strict=False):
        if not name:
            # get_by_name should never be called with name as None (or '', etc)
            # I fixed the code in such a way that if I raise a ValueError
            # all tests pass and basic pages load,
            # but in order not to break anything in the wild,
            # I'm opting to notify by email if/when this happens
            # but fall back to the previous behavior of returning None
            try:
                raise ValueError('%r is not a valid domain name' % name)
            except ValueError:
                if settings.DEBUG:
                    raise
                else:
                    notify_exception(None, '%r is not a valid domain name' % name)
                    return None
        cache_key = _domain_cache_key(name)
        MISSING = object()
        res = cache.get(cache_key, MISSING)
        if res != MISSING:
            return res
        else:
            domain = cls._get_by_name(name, strict)
            # 30 mins, so any unforeseen invalidation bugs aren't too bad.
            cache.set(cache_key, domain, 30*60)
            return domain

    @classmethod
    def _get_by_name(cls, name, strict=False):
        extra_args = {'stale': settings.COUCH_STALE_QUERY} if not strict else {}

        db = cls.get_db()
        res = cache_core.cached_view(db, "domain/domains", key=name, reduce=False,
                                     include_docs=True, wrapper=cls.wrap, force_invalidate=strict,
                                     **extra_args)

        if len(res) > 0:
            result = res[0]
        else:
            result = None

        if result is None and not strict:
            # on the off chance this is a brand new domain, try with strict
            return cls.get_by_name(name, strict=True)

        return result

    @classmethod
    def get_by_organization(cls, organization):
        result = cache_core.cached_view(
            cls.get_db(), "domain/by_organization",
            startkey=[organization],
            endkey=[organization, {}],
            reduce=False,
            include_docs=True,
            wrapper=cls.wrap
        )
        from corehq.apps.accounting.utils import domain_has_privilege
        from corehq import privileges
        result = filter(
            lambda x: domain_has_privilege(x.name, privileges.CROSS_PROJECT_REPORTS),
            result
        )
        return result

    @classmethod
    def get_by_organization_and_hrname(cls, organization, hr_name):
        result = cls.view("domain/by_organization",
                          key=[organization, hr_name],
                          reduce=False,
                          include_docs=True)
        return result

    @classmethod
    def get_or_create_with_name(cls, name, is_active=False,
                                secure_submissions=True):
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
            new_domain.migrations = DomainMigrations(has_migrated_permissions=True)
            new_domain.save(**get_safe_write_kwargs())
            return new_domain

    def password_format(self):
        """
        This was a performance hit, so for now we'll just return 'a' no matter what
        If a single application is alphanumeric, return alphanumeric; otherwise, return numeric
        """
        return 'a'

    @classmethod
    def get_all(cls, include_docs=True):
        # todo: this should use iter_docs
        return Domain.view("domain/not_snapshots",
                            include_docs=include_docs).all()

    def case_sharing_included(self):
        return self.case_sharing or reduce(lambda x, y: x or y, [getattr(app, 'case_sharing', False) for app in self.applications()], False)

    def save(self, **params):
        super(Domain, self).save(**params)
        cache.delete(_domain_cache_key(self.name))

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

    def save_copy(self, new_domain_name=None, user=None, ignore=None):
        from corehq.apps.app_manager.models import get_app
        from corehq.apps.reminders.models import CaseReminderHandler

        ignore = ignore if ignore is not None else []
        if new_domain_name is not None and Domain.get_by_name(new_domain_name):
            return None
        db = get_db()

        new_id = db.copy_doc(self.get_id)['id']
        if new_domain_name is None:
            new_domain_name = new_id
        new_domain = Domain.get(new_id)
        new_domain.name = new_domain_name
        new_domain.copy_history = self.get_updated_history()
        new_domain.is_snapshot = False
        new_domain.snapshot_time = None
        new_domain.organization = None # TODO: use current user's organization (?)

        # reset stuff
        new_domain.cda.signed = False
        new_domain.cda.date = None
        new_domain.cda.type = None
        new_domain.cda.user_id = None
        new_domain.cda.user_ip = None
        new_domain.is_test = "none"
        new_domain.internal = InternalProperties()
        new_domain.creating_user = user.username if user else None

        for field in self._dirty_fields:
            if hasattr(new_domain, field):
                delattr(new_domain, field)

        new_comps = {}  # a mapping of component's id to it's copy
        for res in db.view('domain/related_to_domain', key=[self.name, True]):
            if not self.is_snapshot and res['value']['doc_type'] in ('Application', 'RemoteApp'):
                app = get_app(self.name, res['value']['_id']).get_latest_saved()
                if app:
                    comp = self.copy_component(app.doc_type, app._id, new_domain_name, user=user)
                else:
                    comp = self.copy_component(res['value']['doc_type'], res['value']['_id'], new_domain_name, user=user)
            elif res['value']['doc_type'] not in ignore:
                comp = self.copy_component(res['value']['doc_type'], res['value']['_id'], new_domain_name, user=user)
            else:
                comp = None
            if comp:
                new_comps[res['value']['_id']] = comp

        new_domain.save()

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
                form_copy = new_comps[form_app._id].get_module(m_index).get_form(f_index)
                event.form_unique_id = form_copy.unique_id

        def update_for_copy(handler):
            handler.active = False
            update_events(handler)

        if 'CaseReminderHandler' not in ignore:
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

        str_to_cls = {
            'UserRole': UserRole,
            'CaseReminderHandler': CaseReminderHandler,
        }
        db = get_db()
        if doc_type in ('Application', 'RemoteApp'):
            new_doc = import_app(id, new_domain_name)
            new_doc.copy_history.append(id)
        else:
            cls = str_to_cls[doc_type]

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

        if self.is_snapshot and doc_type == 'Application':
            new_doc.prepare_multimedia_for_exchange()

        new_doc.save()
        return new_doc

    def save_snapshot(self, ignore=None):
        if self.is_snapshot:
            return self
        else:
            copy = self.save_copy(ignore=ignore)
            if copy is None:
                return None
            copy.is_snapshot = True
            copy.snapshot_time = datetime.now()
            del copy.deployment
            copy.save()
            return copy

    def from_snapshot(self):
        return not self.is_snapshot and self.original_doc is not None

    def snapshots(self):
        return Domain.view('domain/snapshots',
            startkey=[self._id, {}],
            endkey=[self._id],
            include_docs=True,
            reduce=False,
            descending=True
        )

    @memoized
    def published_snapshot(self):
        snapshots = self.snapshots().all()
        for snapshot in snapshots:
            if snapshot.published:
                return snapshot
        return None

    @classmethod
    def published_snapshots(cls, include_unapproved=False, page=None, per_page=10):
        skip = None
        limit = None
        if page:
            skip = (page - 1) * per_page
            limit = per_page
        if include_unapproved:
            return cls.view('domain/published_snapshots', startkey=[False, {}], include_docs=True, descending=True, limit=limit, skip=skip)
        else:
            return cls.view('domain/published_snapshots', endkey=[True], include_docs=True, descending=True, limit=limit, skip=skip)

    @classmethod
    def snapshot_search(cls, query, page=None, per_page=10):
        skip = None
        limit = None
        if page:
            skip = (page - 1) * per_page
            limit = per_page
        results = get_db().search('domain/snapshot_search',
            q=json.dumps(query),
            limit=limit,
            skip=skip,
            #stale='ok',
        )
        return map(cls.get, [r['id'] for r in results]), results.total_rows

    @memoized
    def get_organization(self):
        from corehq.apps.orgs.models import Organization
        return Organization.get_by_name(self.organization)

    @memoized
    def organization_title(self):
        if self.organization:
            return self.get_organization().title
        else:
            return ''

    def update_deployment(self, **kwargs):
        self.deployment.update(kwargs)
        self.save()

    def update_internal(self, **kwargs):
        self.internal.update(kwargs)
        self.save()

    def display_name(self):
        if self.is_snapshot:
            return "Snapshot of %s" % self.copied_from.display_name()
        if self.hr_name and self.organization:
            return self.hr_name
        else:
            return self.name

    def long_display_name(self):
        if self.is_snapshot:
            return format_html(
                "Snapshot of {0} &gt; {1}",
                self.get_organization().title,
                self.copied_from.display_name()
            )
        if self.organization:
            return format_html(
                '{0} &gt; {1}',
                self.get_organization().title,
                self.hr_name or self.name
            )
        else:
            return self.name

    __str__ = long_display_name

    def get_license_display(self):
        return LICENSES.get(self.license)

    def copies(self):
        return Domain.view('domain/copied_from_snapshot', key=self._id, include_docs=True)

    def copies_of_parent(self):
        return Domain.view('domain/copied_from_snapshot', keys=[s._id for s in self.copied_from.snapshots()], include_docs=True)

    def delete(self):
        # delete all associated objects
        db = get_db()
        related_docs = db.view('domain/related_to_domain', startkey=[self.name], endkey=[self.name, {}], include_docs=True)
        for doc in related_docs:
            db.delete_doc(doc['doc'])
        super(Domain, self).delete()

    def all_media(self, from_apps=None): #todo add documentation or refactor
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
    def popular_sort(cls, domains):
        sorted_list = []
        MIN_REVIEWS = 1.0

        domains = [(domain, Review.get_average_rating_by_app(domain.copied_from._id), Review.get_num_ratings_by_app(domain.copied_from._id)) for domain in domains]
        domains = [(domain, avg or 0.0, num or 0) for domain, avg, num in domains]

        total_average_sum = sum(avg for domain, avg, num in domains)
        total_average_count = len(domains)
        if not total_average_count:
            return []
        total_average = (total_average_sum / total_average_count)

        for domain, average_rating, num_ratings in domains:
            if num_ratings == 0:
                sorted_list.append((0.0, domain))
            else:
                weighted_rating = ((num_ratings / (num_ratings + MIN_REVIEWS)) * average_rating + (MIN_REVIEWS / (num_ratings + MIN_REVIEWS)) * total_average)
                sorted_list.append((weighted_rating, domain))

        sorted_list = [domain for weighted_rating, domain in sorted(sorted_list, key=lambda domain: domain[0], reverse=True)]

        return sorted_list

    @classmethod
    def hit_sort(cls, domains):
        domains = list(domains)
        domains = sorted(domains, key=lambda domain: domain.download_count, reverse=True)
        return domains

    @classmethod
    def public_deployments(cls):
        return Domain.view('domain/with_deployment', include_docs=True).all()

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
        return get_db().view("domain/snapshots",
            startkey=[self.get_id],
            endkey=[self.get_id, {}],
            reduce=True,
            include_docs=False,
        ).one()["value"]

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

class DomainCounter(Document):
    domain = StringProperty()
    name = StringProperty()
    count = IntegerProperty()
    
    @classmethod
    def get_or_create(cls, domain, name):
        #TODO: Need to make this atomic
        counter = cls.view("domain/counter",
            key = [domain, name],
            include_docs=True
        ).one()
        if counter is None:
            counter = DomainCounter (
                domain = domain,
                name = name,
                count = 0
            )
            counter.save()
        return counter
    
    @classmethod
    def increment(cls, domain, name, amount=1):
        num_tries = 0
        while True:
            try:
                counter = cls.get_or_create(domain, name)
                range_start = counter.count + 1
                counter.count += amount
                counter.save()
                range_end = counter.count
                break
            except ResourceConflict:
                num_tries += 1
                if num_tries >= 500:
                    raise
        return (range_start, range_end)


def _domain_cache_key(name):
    return hashlib.md5(u'cchq:domain:{name}'.format(name=name).encode('utf-8')).hexdigest()
