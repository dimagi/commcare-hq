import datetime
import hashlib
import json
import logging
import re
import uuid
from collections import OrderedDict, defaultdict
from copy import deepcopy
from functools import wraps
from itertools import chain
from mimetypes import guess_type
from urllib.parse import urljoin
from urllib.request import urlopen

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import DEFAULT_DB_ALIAS, models
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import override

from couchdbkit import ResourceNotFound
from looseversion import LooseVersion
from memoized import memoized

from corehq.apps.users.models import ActivityLevel
from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DateTimeProperty,
    DictProperty,
    DocumentSchema,
    IntegerProperty,
    SchemaDictProperty,
    SchemaListProperty,
    SchemaProperty,
    StringListProperty,
    StringProperty,
)
from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.web import get_url_base, parse_int

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager import (
    app_strings,
    commcare_settings,
    const,
    remote_app,
)
from corehq.apps.app_manager.app_schemas.case_properties import (
    expire_case_properties_caches,
    get_all_case_properties,
    get_usercase_properties,
)
from corehq.apps.app_manager.commcare_settings import check_condition
from corehq.apps.app_manager.const import (
    ANDROID_LOGO_PROPERTY_MAPPING,
    LATEST_APK_VALUE,
    LATEST_APP_VALUE,
)
from corehq.apps.app_manager.dbaccessors import (
    domain_has_apps,
    get_app,
    get_app_languages,
    get_apps_in_domain,
    get_build_ids,
    get_latest_build_doc,
    get_latest_released_app_doc,
    wrap_app,
)
from corehq.apps.app_manager.exceptions import (
    AppEditingError,
    AppValidationError,
    FormNotFoundException,
    ModuleIdMissingException,
    ModuleNotFoundException,
    RearrangeError,
    VersioningError,
    XFormException,
)
from corehq.apps.app_manager.feature_support import CommCareFeatureSupportMixin
from corehq.apps.app_manager.helpers.validators import (
    ApplicationBaseValidator,
    ApplicationValidator,
)
from corehq.apps.app_manager.suite_xml.generator import (
    MediaSuiteGenerator,
    SuiteGenerator,
)

from corehq.apps.app_manager.tasks import prune_auto_generated_builds
from corehq.apps.app_manager.templatetags.xforms_extras import (
    trans,
)
from corehq.apps.app_manager.util import (
    expire_get_latest_app_release_by_location_cache,
    get_and_assert_practice_user_in_domain,
    get_correct_app_class,
    get_latest_app_release_by_location,
    is_remote_app,
    domain_has_usercase_access,
    save_xform,
    update_form_unique_ids,
    update_report_module_ids,
)
from corehq.apps.app_manager.xform import XForm
from corehq.apps.app_manager.xform import parse_xml as _parse_xml
from corehq.apps.appstore.models import SnapshotMixin
from corehq.apps.builds.models import BuildRecord, BuildSpec
from corehq.apps.builds.utils import get_default_build_spec
from corehq.apps.cloudcare.utils import get_mobile_ucr_count
from corehq.apps.domain.models import Domain
from corehq.apps.hqmedia.models import (
    ApplicationMediaMixin,
    CommCareMultimedia,
)
from corehq.apps.integration.models import ApplicationIntegrationMixin
from corehq.apps.linked_domain.applications import (
    get_latest_master_app_release,
    get_latest_master_releases_versions,
    get_master_app_briefs,
)
from corehq.apps.linked_domain.exceptions import ActionNotPermitted
from corehq.apps.locations.models import SQLLocation
from corehq.apps.userreports.exceptions import ReportConfigurationNotFoundError
from corehq.apps.userreports.util import get_static_report_mapping
from corehq.apps.users.dbaccessors import get_display_name_for_user_id
from corehq.apps.users.util import cc_user_domain
from corehq.blobs.mixin import CODES, BlobMixin
from corehq.const import USER_DATE_FORMAT, USER_TIME_FORMAT
from corehq.util import bitly
from corehq.util.quickcache import quickcache
from corehq.util.timer import TimingContext, time_method
from corehq.util.timezones.conversions import ServerTime

from .base import (
    CustomAssertion,
    IndexedSchema,
    rename_key,
)
from .form_actions import (
    FormActionCondition,
    UpdateCaseAction,
)
from .forms import (
    AdvancedForm,
    FormBase,
    ShadowForm,
)
from .mixins import (
    CommentMixin,
)

ATTACHMENT_REGEX = r'[^/]*\.xml'


class LazyBlobDoc(BlobMixin):
    """LazyAttachmentDoc for blob db

    Cache blobs in local memory (for this request)
    and in django cache (for the next few requests)
    and commit to couchdb.

    See also `dimagi.utils.couch.lazy_attachment_doc.LazyAttachmentDoc`

    Cache strategy:
    - on fetch, check in local memory, then cache
      - if both are a miss, fetch from couchdb and store in both
    - after an attachment is committed to the blob db and the
      save save has succeeded, save the attachment in the cache
    """

    class Meta:
        app_label = 'app_manager'

    def __init__(self, *args, **kwargs):
        super(LazyBlobDoc, self).__init__(*args, **kwargs)
        self._LAZY_ATTACHMENTS = {}
        # to cache fetched attachments
        # these we do *not* send back down upon save
        self._LAZY_ATTACHMENTS_CACHE = {}

    @classmethod
    def wrap(cls, data):
        if "_attachments" in data:
            data = data.copy()
            attachments = data.pop("_attachments").copy()
            if cls._migrating_blobs_from_couch:
                # preserve stubs so couch attachments don't get deleted on save
                stubs = {}
                for name, value in list(attachments.items()):
                    if isinstance(value, dict) and "stub" in value:
                        stubs[name] = attachments.pop(name)
                if stubs:
                    data["_attachments"] = stubs
        else:
            attachments = None
        self = super(LazyBlobDoc, cls).wrap(data)
        if attachments:
            for name, attachment in attachments.items():
                if isinstance(attachment, str):
                    attachment = attachment.encode('utf-8')
                if isinstance(attachment, bytes):
                    info = {"content": attachment}
                else:
                    raise ValueError("Unknown attachment format: {!r}"
                                     .format(attachment))
                self.lazy_put_attachment(name=name, **info)
        return self

    def __attachment_cache_key(self, name):
        return 'lazy_attachment/{id}/{name}'.format(id=self.get_id, name=name)

    def __set_cached_attachment(self, name, content, timeout=60 * 10):
        cache.set(self.__attachment_cache_key(name), content, timeout=timeout)
        self._LAZY_ATTACHMENTS_CACHE[name] = content

    def __get_cached_attachment(self, name):
        try:
            # it has been fetched already during this request
            content = self._LAZY_ATTACHMENTS_CACHE[name]
        except KeyError:
            content = cache.get(self.__attachment_cache_key(name))
            if content is not None:
                if isinstance(content, str):
                    return None
                self._LAZY_ATTACHMENTS_CACHE[name] = content
        return content

    def put_attachment(self, content, name=None, *args, **kw):
        cache.delete(self.__attachment_cache_key(name))
        self._LAZY_ATTACHMENTS_CACHE.pop(name, None)
        return super(LazyBlobDoc, self).put_attachment(content, name, *args, **kw)

    def has_attachment(self, name):
        return name in self.lazy_list_attachments()

    def lazy_put_attachment(self, content, name=None, content_type=None,
                            content_length=None):
        """
        Ensure the attachment is available through lazy_fetch_attachment
        and that upon self.save(), the attachments are put to the doc as well

        """
        self._LAZY_ATTACHMENTS[name] = {
            'content': content,
            'content_type': content_type,
            'content_length': content_length,
        }

    def lazy_fetch_attachment(self, name):
        # it has been put/lazy-put already during this request
        if name in self._LAZY_ATTACHMENTS:
            content = self._LAZY_ATTACHMENTS[name]['content']
        else:
            content = self.__get_cached_attachment(name)

            if content is None:
                try:
                    content = self.fetch_attachment(name)
                except ResourceNotFound as e:
                    # django cache will pickle this exception for you
                    # but e.response isn't picklable
                    if hasattr(e, 'response'):
                        del e.response
                    content = e
                    self.__set_cached_attachment(name, content, timeout=60 * 5)
                    raise
                else:
                    self.__set_cached_attachment(name, content)

        if isinstance(content, ResourceNotFound):
            raise content

        return content

    def lazy_list_attachments(self):
        keys = set()
        keys.update(getattr(self, '_LAZY_ATTACHMENTS', None) or {})
        keys.update(self.blobs or {})
        return keys

    def save(self, **params):
        def super_save():
            super(LazyBlobDoc, self).save(**params)
        if self._LAZY_ATTACHMENTS:
            with self.atomic_blobs(super_save):
                for name, info in self._LAZY_ATTACHMENTS.items():
                    if not info['content_type']:
                        info['content_type'] = ';'.join(filter(None, guess_type(name)))
                    super(LazyBlobDoc, self).put_attachment(name=name, **info)
            # super_save() has succeeded by now
            for name, info in self._LAZY_ATTACHMENTS.items():
                self.__set_cached_attachment(name, info['content'])
            self._LAZY_ATTACHMENTS.clear()
        else:
            super_save()


def absolute_url_property(method):
    """
    Helper for the various fully qualified application URLs
    Turns a method returning an unqualified URL
    into a property returning a fully qualified URL
    (e.g., '/my_url/' => 'https://www.commcarehq.org/my_url/')
    Expects `self.url_base` to be fully qualified url base

    """
    @wraps(method)
    def _inner(self):
        return urljoin(self.url_base, method(self))
    return property(_inner)


class BuildProfile(DocumentSchema):
    name = StringProperty()
    langs = StringListProperty()
    practice_mobile_worker_id = StringProperty()

    def __eq__(self, other):
        return self.langs == other.langs and self.practice_mobile_worker_id == other.practice_mobile_worker_id


class ApplicationBase(LazyBlobDoc, SnapshotMixin,
                      CommCareFeatureSupportMixin,
                      CommentMixin):
    """
    Abstract base class for Application and RemoteApp.
    Contains methods for generating the various files and zipping them into CommCare.jar

    See note at top of file for high-level overview.
    """

    _blobdb_type_code = CODES.application
    recipients = StringProperty(default="")
    domain = StringProperty()

    # Version-related properties. An application keeps an auto-incrementing version number and knows how to
    # make copies of itself, delete a copy of itself, and revert back to an earlier copy of itself.
    copy_of = StringProperty()
    version = IntegerProperty()
    short_odk_url = StringProperty()
    short_odk_media_url = StringProperty()
    _meta_fields = ['_id', '_rev', 'domain', 'copy_of', 'version',
                    'short_odk_url', 'short_odk_media_url']

    # this is the supported way of specifying which commcare build to use
    build_spec = SchemaProperty(BuildSpec)

    # The following properties should only appear on saved builds
    # built_with stores a record of CommCare build used in a saved app
    built_with = SchemaProperty(BuildRecord)
    build_signed = BooleanProperty(default=True)
    built_on = DateTimeProperty(required=False)
    build_comment = StringProperty()
    comment_from = StringProperty()
    last_released = DateTimeProperty(required=False)
    build_broken = BooleanProperty(default=False)
    is_auto_generated = BooleanProperty(default=False)
    # for internal use only, not user-facing
    build_broken_reason = StringProperty()

    # watch out for a past bug:
    # when reverting to a build that happens to be released
    # that got copied into into the new app doc, and when new releases were made,
    # they were automatically starred
    # AFAIK this is fixed in code, but my rear its ugly head in an as-yet-not-understood
    # way for apps that already had this problem. Just keep an eye out
    is_released = BooleanProperty(default=False)

    # django-style salted hash of the admin password
    admin_password = StringProperty()
    # a=Alphanumeric, n=Numeric, x=Neither (not allowed)
    admin_password_charset = StringProperty(choices=['a', 'n', 'x'], default='n')

    langs = StringListProperty()

    secure_submissions = BooleanProperty(default=False)

    # metadata for data platform
    amplifies_workers = StringProperty(
        choices=[const.AMPLIFIES_YES, const.AMPLIFIES_NO, const.AMPLIFIES_NOT_SET],
        default=const.AMPLIFIES_NOT_SET
    )
    amplifies_project = StringProperty(
        choices=[const.AMPLIFIES_YES, const.AMPLIFIES_NO, const.AMPLIFIES_NOT_SET],
        default=const.AMPLIFIES_NOT_SET
    )
    minimum_use_threshold = StringProperty(
        default='15'
    )
    experienced_threshold = StringProperty(
        default='3'
    )

    # exchange properties
    cached_properties = DictProperty()
    description = StringProperty()
    deployment_date = DateTimeProperty()
    phone_model = StringProperty()
    user_type = StringProperty()
    attribution_notes = StringProperty()

    # always false for RemoteApp
    case_sharing = BooleanProperty(default=False)
    vellum_case_management = BooleanProperty(default=True)

    # legacy property; kept around to be able to identify (deprecated) v1 apps
    application_version = StringProperty(
        default=const.APP_V2,
        choices=[const.APP_V1, const.APP_V2],
        required=False,
    )
    last_modified = DateTimeProperty()

    def assert_app_v2(self):
        assert self.application_version == const.APP_V2

    build_profiles = SchemaDictProperty(BuildProfile)
    practice_mobile_worker_id = StringProperty()

    # use commcare_flavor to avoid checking for none
    target_commcare_flavor = StringProperty(
        default='none',
        choices=['none', const.TARGET_COMMCARE, const.TARGET_COMMCARE_LTS]
    )

    # Whether or not the Application has had any forms submitted against it
    has_submissions = BooleanProperty(default=False)

    mobile_ucr_restore_version = StringProperty(
        default=const.MOBILE_UCR_VERSION_2, choices=const.MOBILE_UCR_VERSIONS, required=False
    )
    location_fixture_restore = StringProperty(
        default=const.DEFAULT_LOCATION_FIXTURE_OPTION, choices=const.LOCATION_FIXTURE_OPTIONS,
        required=False
    )

    persistent_menu = BooleanProperty(default=False)
    show_breadcrumbs = BooleanProperty(default=True)

    @property
    def id(self):
        return self._id

    @property
    def origin_id(self):
        # For app builds this is the ID of the app they were built from. Otherwise, it's just the app's ID.
        return self.copy_of or self._id

    def is_deleted(self):
        return self.doc_type.endswith(DELETED_SUFFIX)

    def unretire(self):
        self.doc_type = self.get_doc_type()
        self.save()

    def get_doc_type(self):
        if self.doc_type.endswith(DELETED_SUFFIX):
            return self.doc_type[:-len(DELETED_SUFFIX)]
        else:
            return self.doc_type

    @classmethod
    def wrap(cls, data):
        self = super(ApplicationBase, cls).wrap(data)
        if not self.build_spec or self.build_spec.is_null():
            self.build_spec = get_default_build_spec()

        return self

    @property
    @memoized
    def global_app_config(self):
        return GlobalAppConfig.by_app(self)

    def rename_lang(self, old_lang, new_lang):
        validate_lang(new_lang)

    def is_remote_app(self):
        return False

    @memoized
    def get_latest_build(self):
        return self.view('app_manager/applications',
            startkey=[self.domain, self.origin_id, {}],
            endkey=[self.domain, self.origin_id],
            include_docs=True,
            limit=1,
            descending=True,
        ).first()

    @memoized
    def _get_version_comparison_build(self):
        '''
        Returns an earlier build to be used for comparing forms and multimedia
        when making a new build and setting the versions of those items.
        For normal applications, this is just the previous build.
        '''
        return self.get_latest_build()

    @memoized
    def get_latest_saved(self):
        """
        This looks really similar to get_latest_app, not sure why tim added
        """
        doc = (get_latest_released_app_doc(self.domain, self._id)
               or get_latest_build_doc(self.domain, self._id))
        return self.__class__.wrap(doc) if doc else None

    def set_admin_password(self, raw_password):
        self.admin_password = make_password(raw_password)

        if raw_password.isnumeric():
            self.admin_password_charset = 'n'
        elif raw_password.isalnum():
            self.admin_password_charset = 'a'
        else:
            self.admin_password_charset = 'x'

    def get_build(self):
        return self.build_spec.get_build()

    @property
    def build_version(self):
        # `LooseVersion`s are smart!
        # LooseVersion('2.12.0') > '2.2'
        # (even though '2.12.0' < '2.2')
        if self.build_spec.version:
            return LooseVersion(self.build_spec.version)

    @property
    def commcare_minor_release(self):
        """This is mostly just for views"""
        return '%d.%d' % self.build_spec.minor_release()

    @property
    def short_name(self):
        return self.name if len(self.name) <= 12 else '%s..' % self.name[:10]

    @property
    def url_base(self):
        custom_base_url = getattr(self, 'custom_base_url', None)
        return custom_base_url or get_url_base()

    @absolute_url_property
    def post_url(self):
        if self.secure_submissions:
            url_name = 'receiver_secure_post_with_app_id'
        else:
            url_name = 'receiver_post_with_app_id'
        return reverse(url_name, args=[self.domain, self.get_id])

    @absolute_url_property
    def key_server_url(self):
        return reverse('key_server_url', args=[self.domain])

    def heartbeat_url(self, build_profile_id=None):
        return self.base_heartbeat_url + '?build_profile_id=%s' % (build_profile_id or '')

    @absolute_url_property
    def base_heartbeat_url(self):
        return reverse('phone_heartbeat', args=[self.domain, self.get_id])

    @absolute_url_property
    def ota_restore_url(self):
        return reverse('app_aware_restore', args=[self.domain, self._id])

    @absolute_url_property
    def hq_profile_url(self):
        # RemoteApp already has a property called "profile_url",
        # Application.profile_url just points here to stop the conflict
        # http://manage.dimagi.com/default.asp?227088#1149422
        return "%s?latest=true" % (
            reverse('download_profile', args=[self.domain, self._id])
        )

    @absolute_url_property
    def media_profile_url(self):
        return "%s?latest=true" % (
            reverse('download_media_profile', args=[self.domain, self._id])
        )

    @property
    def profile_loc(self):
        return "jr://resource/profile.xml"

    @absolute_url_property
    def jar_url(self):
        return reverse('download_jar', args=[self.domain, self._id])

    @absolute_url_property
    def recovery_measures_url(self):
        return reverse('recovery_measures', args=[self.domain, self._id])

    def create_build_files(self, build_profile_id=None):
        all_files = self.create_all_files(build_profile_id)
        for filepath in all_files:
            self.lazy_put_attachment(all_files[filepath],
                                     'files/%s' % filepath)

    @property
    @memoized
    def timing_context(self):
        return TimingContext(self.name)

    def validate_app(self):
        return ApplicationBaseValidator(self).validate_app()

    @absolute_url_property
    def odk_profile_url(self):
        return reverse('download_odk_profile', args=[self.domain, self._id])

    @absolute_url_property
    def odk_media_profile_url(self):
        return reverse('download_odk_media_profile', args=[self.domain, self._id])

    def get_odk_qr_code(self, with_media=False, build_profile_id=None, download_target_version=False):
        """Returns a QR code, as a PNG to install on CC-ODK"""
        filename = 'qrcode.png' if not download_target_version else 'qrcode-targeted.png'
        try:
            return self.lazy_fetch_attachment(filename)
        except ResourceNotFound:
            from corehq.apps.settings.views import get_qrcode
            url = self.odk_profile_url if not with_media else self.odk_media_profile_url
            kwargs = []
            if build_profile_id is not None:
                kwargs.append('profile={profile_id}'.format(profile_id=build_profile_id))
            if download_target_version:
                kwargs.append('download_target_version=true')
            url += '?' + '&'.join(kwargs)

            qr_content = get_qrcode(url)
            self.lazy_put_attachment(qr_content, filename,
                                     content_type="image/png")
            return qr_content

    def generate_shortened_url(self, view_name, build_profile_id=None):
        try:
            view_url = reverse(view_name, args=[self.domain, self._id])
            if build_profile_id is not None:
                long_url = urljoin(
                    self.url_base,
                    f'{view_url}?profile={build_profile_id}'
                )
            else:
                long_url = urljoin(self.url_base, view_url)
            shortened_url = bitly.shorten(long_url)
        except Exception:
            logging.exception("Problem creating bitly url for app %s. Do you have network?" % self.get_id)
        else:
            return shortened_url

    def get_short_odk_url(self, with_media=False, build_profile_id=None):
        if not build_profile_id:
            if with_media:
                if not self.short_odk_media_url:
                    self.short_odk_media_url = self.generate_shortened_url('download_odk_media_profile')
                    self.save()
                return self.short_odk_media_url
            else:
                if not self.short_odk_url:
                    self.short_odk_url = self.generate_shortened_url('download_odk_profile')
                    self.save()
                return self.short_odk_url
        else:
            if with_media:
                return self.generate_shortened_url('download_odk_media_profile', build_profile_id)
            else:
                return self.generate_shortened_url('download_odk_profile', build_profile_id)

    @time_method()
    def make_build(self, comment=None, user_id=None):
        assert self.get_id
        assert self.copy_of is None
        cls = self.__class__
        copies = cls.view(
            'app_manager/applications',
            key=[self.domain, self._id, self.version],
            include_docs=True,
            limit=1
        ).all()
        if copies:
            copy = copies[0]
        else:
            copy = deepcopy(self.to_json())
            bad_keys = ('_id', '_rev', '_attachments', 'external_blobs',
                        'short_odk_url', 'short_odk_media_url', 'recipients')

            for bad_key in bad_keys:
                if bad_key in copy:
                    del copy[bad_key]

            copy = cls.wrap(copy)
            copy.convert_app_to_build(self._id, user_id, comment)
            copy.copy_attachments(self)

        if not copy._id:
            # I expect this always to be the case
            # but check explicitly so as not to change the _id if it exists
            copy._id = uuid.uuid4().hex

        errors = copy.validate_app()
        if errors:
            raise AppValidationError(errors)

        copy.create_build_files()

        # since this hard to put in a test
        # I'm putting this assert here if copy._id is ever None
        # which makes tests error
        assert copy._id
        prune_auto_generated_builds.delay(self.domain, self._id)

        return copy

    def convert_app_to_build(self, copy_of, user_id, comment=None):
        self.copy_of = copy_of
        built_on = datetime.datetime.utcnow()
        self.date_created = built_on
        self.built_on = built_on
        self.built_with = BuildRecord(
            version=self.build_spec.version,
            build_number=self.version,
            datetime=built_on,
        )
        self.build_comment = comment
        self.comment_from = user_id
        self.is_released = False

    def convert_build_to_app(self):
        self.copy_of = None
        self.date_created = None
        self.built_on = None
        self.built_with = BuildRecord()
        self.build_comment = None
        self.comment_from = None
        self.is_released = False

    def get_attachments(self):
        attachments = {}
        for name in self.lazy_list_attachments():
            if re.match(ATTACHMENT_REGEX, name):
                # FIXME loss of metadata (content type, etc.)
                attachments[name] = self.lazy_fetch_attachment(name)
        return attachments

    def save_attachments(self, attachments, save=None):
        with self.atomic_blobs(save=save):
            for name, attachment in attachments.items():
                if re.match(ATTACHMENT_REGEX, name):
                    self.put_attachment(attachment, name)
        return self

    def copy_attachments(self, other, regexp=ATTACHMENT_REGEX):
        for name in other.lazy_list_attachments() or {}:
            if regexp is None or re.match(regexp, name):
                self.lazy_put_attachment(other.lazy_fetch_attachment(name), name)

    def delete_app(self):
        from .delete_records import DeleteApplicationRecord
        domain_has_apps.clear(self.domain)
        get_app_languages.clear(self.domain)
        get_apps_in_domain.clear(self.domain, True)
        get_apps_in_domain.clear(self.domain, False)
        get_mobile_ucr_count.clear(self.domain)
        self.doc_type += '-Deleted'
        record = DeleteApplicationRecord(
            domain=self.domain,
            app_id=self.id,
            datetime=datetime.datetime.utcnow()
        )
        record.save()
        return record

    def save(self, response_json=None, increment_version=None, **params):
        from corehq.apps.case_search.utils import get_app_context_by_case_type
        self.last_modified = datetime.datetime.utcnow()
        if not self._rev and not domain_has_apps(self.domain):
            domain_has_apps.clear(self.domain)
        if self.get_id:
            # expire cache unless new application
            self.global_app_config.clear_version_caches()
            get_app_context_by_case_type.clear(self.domain, self.get_id)
        get_all_case_properties.clear(self)
        expire_case_properties_caches(self.domain)
        get_usercase_properties.clear(self)
        get_app_languages.clear(self.domain)
        get_apps_in_domain.clear(self.domain, True)
        get_apps_in_domain.clear(self.domain, False)
        get_mobile_ucr_count.clear(self.domain)

        if self.copy_of:
            cache.delete('app_build_cache_{}_{}'.format(self.domain, self.get_id))

        if increment_version is None:
            increment_version = not self.copy_of
        if increment_version:
            self.version = self.version + 1 if self.version else 1
        super(ApplicationBase, self).save(**params)

        _refresh_data_dictionary(self.domain, self.get_id)
        if response_json is not None:
            if 'update' not in response_json:
                response_json['update'] = {}
            response_json['update']['app-version'] = self.version

    @classmethod
    def save_docs(cls, docs, **kwargs):
        utcnow = datetime.datetime.utcnow()
        for doc in docs:
            doc['last_modified'] = utcnow
        super(ApplicationBase, cls).save_docs(docs, **kwargs)

    bulk_save = save_docs

    def set_form_versions(self):
        # by default doing nothing here is fine.
        pass

    def set_media_versions(self):
        pass

    def get_build_langs(self, build_profile_id=None):
        if build_profile_id is not None:
            return self.build_profiles[build_profile_id].langs
        else:
            return self.langs

    def convert_to_application(self):
        doc = self.to_json()
        doc['doc_type'] = 'Application'
        del doc['upstream_app_id']
        del doc['upstream_version']
        del doc['linked_app_translations']
        del doc['linked_app_logo_refs']
        del doc['linked_app_attrs']
        return Application.wrap(doc)

    @property
    def commcare_flavor(self):
        return None if self.target_commcare_flavor == "none" else self.target_commcare_flavor


def _refresh_data_dictionary(domain, get_id):  # easy patch target
    from corehq.apps.app_manager.tasks import refresh_data_dictionary_from_app
    refresh_data_dictionary_from_app.delay(domain, get_id)


def validate_lang(lang):
    if not re.match(r'^[a-z]{2,3}(-[a-z]*)?$', lang):
        raise ValueError("Invalid Language")


class SavedAppBuild(ApplicationBase):
    def releases_list_json(self, timezone):
        """
        returns minimum possible data that could be used to list a Build on releases page on HQ

        :param timezone: timezone expected for timestamps in result
        :return: data dict
        """
        data = super(SavedAppBuild, self).to_json().copy()
        # ignore details that are not used
        for key in ('modules', 'user_registration', 'external_blobs',
                    '_attachments', 'profile', 'translations',
                    'description', 'short_description', 'multimedia_map', 'media_language_map'):
            data.pop(key, None)
        built_on_user_time = ServerTime(self.built_on).user_time(timezone)
        menu_item_label = self.built_with.get_menu_item_label()
        data.update({
            'id': self.id,
            'built_on_date': built_on_user_time.ui_string(USER_DATE_FORMAT),
            'built_on_time': built_on_user_time.ui_string(USER_TIME_FORMAT),
            'menu_item_label': menu_item_label,
            'short_name': self.short_name,
            'enable_offline_install': self.enable_offline_install,
            'include_media': not is_remote_app(self),
            'commcare_flavor': (
                self.commcare_flavor
                if toggles.TARGET_COMMCARE_FLAVOR.enabled(self.domain) else None
            ),
        })
        comment_from = data['comment_from']
        if comment_from:
            data['comment_user_name'] = get_display_name_for_user_id(
                self.domain, comment_from, default=comment_from)

        return data


class Application(ApplicationBase, ApplicationMediaMixin, ApplicationIntegrationMixin):
    """
    An Application that can be created entirely through the online interface

    """
    from .modules import ModuleBase

    modules = SchemaListProperty(ModuleBase)
    name = StringProperty()
    # profile's schema is {'features': {}, 'properties': {}, 'custom_properties': {}}
    # ended up not using a schema because properties is a reserved word
    profile = DictProperty()
    use_custom_suite = BooleanProperty(default=False)
    custom_base_url = StringProperty()
    cloudcare_enabled = BooleanProperty(default=False)

    translations = DictProperty()
    translation_strategy = StringProperty(default='select-known',
                                          choices=list(app_strings.CHOICES.keys()))
    auto_gps_capture = BooleanProperty(default=False)
    date_created = DateTimeProperty()
    created_from_template = StringProperty()
    use_grid_menus = BooleanProperty(default=False)
    grid_form_menus = StringProperty(default='none',
                                     choices=['none', 'all', 'some'])
    add_ons = DictProperty()
    smart_lang_display = BooleanProperty()  # null means none set so don't default to false/true
    custom_assertions = SchemaListProperty(CustomAssertion)

    family_id = StringProperty()  # ID of earliest parent app across copies and linked apps

    def __repr__(self):
        return (f"{self.doc_type}(id='{self._id}', domain='{self.domain}', "
                f"name='{self.name}', copy_of={repr(self.copy_of)})")

    def has_modules(self):
        return len(self.get_modules()) > 0 and not self.is_remote_app()

    @property
    @memoized
    def commtrack_enabled(self):
        if settings.UNIT_TESTING:
            return False  # override with .tests.util.commtrack_enabled
        domain_obj = Domain.get_by_name(self.domain) if self.domain else None
        return domain_obj.commtrack_enabled if domain_obj else False

    @classmethod
    def wrap(cls, data):
        self = super(Application, cls).wrap(data)

        # make sure all form versions are None on working copies
        if not self.copy_of:
            for form in self.get_forms():
                form.version = None

        # weird edge case where multimedia_map gets set to null and causes issues
        if self.multimedia_map is None:
            self.multimedia_map = {}

        return self

    def save(self, *args, **kwargs):
        super(Application, self).save(*args, **kwargs)
        # Import loop if this is imported at the top
        # TODO: revamp so signal_connections <- models <- signals
        from corehq.apps.app_manager import signals
        from couchforms.analytics import get_form_analytics_metadata
        from corehq.apps.reports.analytics.esaccessors import (
            guess_form_name_from_submissions_using_xmlns)
        for xmlns in self.get_xmlns_map():
            get_form_analytics_metadata.clear(self.domain, self._id, xmlns)
            guess_form_name_from_submissions_using_xmlns.clear(self.domain, xmlns)
        signals.app_post_save.send(Application, application=self)

    def delete_copy(self, copy):
        if copy.copy_of != self._id:
            raise VersioningError("%s is not a copy of %s" % (copy, self))
        copy.delete_app()
        copy.save(increment_version=False)

    def make_reversion_to_copy(self, copy):
        """
        Replaces couch doc with a copy of the backup ("copy").
        Returns a new Application referring to this updated couch doc.
        The returned doc should be used in place of
        the original doc, i.e. should be called as follows:
            app = app.make_reversion_to_copy(copy)
            app.save()
        """
        if copy.copy_of != self._id:
            raise VersioningError("%s is not a copy of %s" % (copy, self))
        app = deepcopy(copy.to_json())
        app['_rev'] = self._rev
        app['_id'] = self._id
        app['version'] = self.version
        app['copy_of'] = None
        app.pop('_attachments', None)
        app.pop('external_blobs', None)
        cls = self.__class__
        app = cls.wrap(app)
        app.copy_attachments(copy)

        for form in app.get_forms():
            # reset the form's validation cache, since the form content is
            # likely to have changed in the revert!
            form.clear_validation_cache()
            form.version = None

        app.build_broken = False

        return app

    @property
    def profile_url(self):
        return self.hq_profile_url

    @absolute_url_property
    def suite_url(self):
        return reverse('download_suite', args=[self.domain, self.get_id])

    @property
    def suite_loc(self):
        if self.enable_relative_suite_path:
            return './suite.xml'
        else:
            return "jr://resource/suite.xml"

    @absolute_url_property
    def media_suite_url(self):
        return reverse('download_media_suite', args=[self.domain, self.get_id])

    @property
    def media_suite_loc(self):
        if self.enable_relative_suite_path:
            return "./media_suite.xml"
        else:
            return "jr://resource/media_suite.xml"

    @property
    def default_language(self):
        return self.langs[0] if len(self.langs) > 0 else "en"

    @time_method()
    def set_form_versions(self):
        """
        Set the 'version' property on each form as follows to the current app version if the form is new
        or has changed since the last build. Otherwise set it to the version from the last build.
        """
        def _hash(val):
            return hashlib.md5(val).hexdigest()

        latest_build = self._get_version_comparison_build()
        if not latest_build:
            return
        force_new_version = self.build_profiles != latest_build.build_profiles
        for form_stuff in self.get_forms(bare=False):
            filename = 'files/%s' % self.get_form_filename(**form_stuff)
            current_form = form_stuff["form"]
            if not force_new_version:
                try:
                    previous_form = latest_build.get_form(current_form.unique_id)
                    # take the previous version's compiled form as-is
                    # (generation code may have changed since last build)
                    previous_source = latest_build.fetch_attachment(filename)
                except (ResourceNotFound, FormNotFoundException):
                    current_form.version = None
                else:
                    previous_hash = _hash(previous_source)

                    # set form version to previous version, and only update if content has changed
                    current_form.version = previous_form.get_version()
                    current_form = current_form.validate_form()
                    current_hash = _hash(current_form.render_xform())
                    if previous_hash != current_hash:
                        current_form.version = None
                        # clear cache since render_xform was called with a mutated form set to the previous version
                        current_form.render_xform.reset_cache(current_form)
            else:
                current_form.version = None

    @time_method()
    def set_media_versions(self):
        """
        Set the media version numbers for all media in the app to the current app version
        if the media is new or has changed since the last build. Otherwise set it to the
        version from the last build.
        """

        # access to .multimedia_map is slow
        previous_version = self._get_version_comparison_build()
        prev_multimedia_map = previous_version.multimedia_map if previous_version else {}

        for path, map_item in self.multimedia_map.items():
            prev_map_item = prev_multimedia_map.get(path, None)
            if prev_map_item and prev_map_item.unique_id:
                # Re-use the id so CommCare knows it's the same resource
                map_item.unique_id = prev_map_item.unique_id
            if (prev_map_item and prev_map_item.version
                    and prev_map_item.multimedia_id == map_item.multimedia_id):
                map_item.version = prev_map_item.version
            else:
                map_item.version = self.version

    def ensure_module_unique_ids(self, should_save=False):
        """
            Creates unique_ids for modules that don't have unique_id attributes
            should_save: the doc will be saved only if should_save is set to True

            WARNING: If called on the same doc in different requests without saving,
            this function will set different uuid each time,
            likely causing unexpected behavior
        """
        if any(not mod.unique_id for mod in self.modules):
            for mod in self.modules:
                mod.get_or_create_unique_id()
            if should_save:
                self.save()

    def set_translations(self, lang, translations):
        self.translations[lang] = translations

    def create_app_strings(self, lang, build_profile_id=None):
        gen = app_strings.CHOICES[self.translation_strategy]
        if lang == 'default':
            return gen.create_default_app_strings(self, build_profile_id)
        else:
            return gen.create_app_strings(self, lang)

    @time_method()
    def create_profile(self, is_odk=False, with_media=False,
                       build_profile_id=None, commcare_flavor=None):
        self__profile = self.profile
        app_profile = defaultdict(dict)

        for setting in commcare_settings.get_custom_commcare_settings():
            setting_type = setting['type']
            setting_id = setting['id']

            if setting_type not in ('properties', 'features'):
                setting_value = None
            elif setting_id not in self__profile.get(setting_type, {}):
                if 'commcare_default' in setting and setting['commcare_default'] != setting['default']:
                    setting_value = setting['default']
                else:
                    setting_value = None
            else:
                setting_value = self__profile[setting_type][setting_id]
            if setting_value:
                app_profile[setting_type][setting_id] = {
                    'value': setting_value,
                    'force': setting.get('force', False)
                }
            # assert that it gets explicitly set once per loop
            del setting_value

        logo_refs = [logo_name for logo_name in self.logo_refs if logo_name in ANDROID_LOGO_PROPERTY_MAPPING]
        if logo_refs and domain_has_privilege(self.domain, privileges.COMMCARE_LOGO_UPLOADER):
            for logo_name in logo_refs:
                app_profile['properties'][ANDROID_LOGO_PROPERTY_MAPPING[logo_name]] = {
                    'force': True,
                    'value': self.logo_refs[logo_name]['path'],
                }

        if toggles.MOBILE_RECOVERY_MEASURES.enabled(self.domain):
            app_profile['properties']['recovery-measures-url'] = {
                'force': True,
                'value': self.recovery_measures_url,
            }

        if with_media:
            profile_url = self.media_profile_url if not is_odk else (self.odk_media_profile_url + '?latest=true')
        else:
            profile_url = self.profile_url if not is_odk else (self.odk_profile_url + '?latest=true')

        if toggles.CUSTOM_PROPERTIES.enabled(self.domain) and "custom_properties" in self__profile:
            app_profile['custom_properties'].update(self__profile['custom_properties'])

        if not domain_has_privilege(self.domain, privileges.APP_DEPENDENCIES):
            # remove any previous dependencies if privilege was revoked
            if 'dependencies' in app_profile['features']:
                del app_profile['features']['dependencies']

        apk_heartbeat_url = self.heartbeat_url(build_profile_id)
        locale = self.get_build_langs(build_profile_id)[0]
        target_package_id = {
            const.TARGET_COMMCARE: 'org.commcare.dalvik',
            const.TARGET_COMMCARE_LTS: 'org.commcare.lts',
        }.get(commcare_flavor)

        return render_to_string('app_manager/profile.xml', {
            'is_odk': is_odk,
            'app': self,
            'profile_url': profile_url,
            'app_profile': app_profile,
            'cc_user_domain': cc_user_domain(self.domain),
            'include_media_suite': with_media,
            'uniqueid': self.origin_id,
            'name': self.name,
            'descriptor': "Profile File",
            'build_profile_id': build_profile_id,
            'locale': locale,
            'apk_heartbeat_url': apk_heartbeat_url,
            'target_package_id': target_package_id,
            'support_email': settings.SUPPORT_EMAIL if not settings.IS_DIMAGI_ENVIRONMENT else None,
        }).encode('utf-8')

    @property
    def custom_suite(self):
        try:
            return self.lazy_fetch_attachment('custom_suite.xml')
        except ResourceNotFound:
            return ""

    def set_custom_suite(self, value):
        self.put_attachment(value, 'custom_suite.xml')

    @time_method()
    def create_suite(self, build_profile_id=None):
        self.assert_app_v2()
        return SuiteGenerator(self, build_profile_id).generate_suite()

    def create_media_suite(self, build_profile_id=None):
        return MediaSuiteGenerator(self, build_profile_id).generate_suite()

    @memoized
    def get_practice_user_id(self, build_profile_id=None):
        # returns app or build profile specific practice_mobile_worker_id
        if build_profile_id:
            build_spec = self.build_profiles[build_profile_id]
            return build_spec.practice_mobile_worker_id
        else:
            return self.practice_mobile_worker_id

    @property
    @memoized
    def enable_practice_users(self):
        return (
            self.supports_practice_users
            and domain_has_privilege(self.domain, privileges.PRACTICE_MOBILE_WORKERS)
        )

    @property
    @memoized
    def enable_update_prompts(self):
        return (
            self.supports_update_prompts and domain_has_privilege(self.domain, privileges.PHONE_APK_HEARTBEAT)
        )

    @memoized
    def get_practice_user(self, build_profile_id=None):
        """
        kwargs:
            build_profile_id: id of a particular build profile to get the practice user for
                If it's None, practice user of the default app is returned

        Returns:
            App or build profile specific practice user and validates that the user is
                a practice mode user and that user belongs to app.domain

        This is memoized to avoid refetching user when validating app, creating build files and
            generating suite file.
        """
        practice_user_id = self.get_practice_user_id(build_profile_id=build_profile_id)
        if practice_user_id:
            return get_and_assert_practice_user_in_domain(practice_user_id, self.domain)
        else:
            return None

    @time_method()
    def create_practice_user_restore(self, build_profile_id=None):
        """
        Returns:
            Returns restore xml as a string for the practice user of app or
                app profile specfied by build_profile_id
            Raises a PracticeUserException if the user is not practice user
        """
        from corehq.apps.ota.models import DemoUserRestore
        if not self.enable_practice_users:
            return None
        user = self.get_practice_user(build_profile_id)
        if user:
            user_restore = DemoUserRestore.objects.get(id=user.demo_restore_id)
            return user_restore.get_restore_as_string()
        else:
            return None

    @classmethod
    def get_form_filename(cls, type=None, form=None, module=None):
        return 'modules-%s/forms-%s.xml' % (module.id, form.id)

    @time_method()
    def _make_language_files(self, prefix, build_profile_id):
        return {
            "{}{}/app_strings.txt".format(prefix, lang):
                self.create_app_strings(lang, build_profile_id).encode('utf-8')
            for lang in ['default'] + self.get_build_langs(build_profile_id)
        }

    @time_method()
    def _get_form_files(self, prefix, build_profile_id):
        files = {}
        for form_stuff in self.get_forms(bare=False):
            def exclude_form(form):
                return isinstance(form, ShadowForm) or form.is_a_disabled_release_form()

            if not exclude_form(form_stuff['form']):
                filename = prefix + self.get_form_filename(**form_stuff)
                form = form_stuff['form']
                try:
                    files[filename] = form.render_xform(build_profile_id=build_profile_id)
                except XFormException as e:
                    raise XFormException(_('Error in form "{}": {}').format(trans(form.name), e))
        return files

    @time_method()
    @memoized
    def create_all_files(self, build_profile_id=None):
        self.set_form_versions()
        self.set_media_versions()
        prefix = '' if not build_profile_id else build_profile_id + '/'
        files = {
            '{}profile.xml'.format(prefix): self.create_profile(is_odk=False, build_profile_id=build_profile_id),
            '{}profile.ccpr'.format(prefix): self.create_profile(is_odk=True, build_profile_id=build_profile_id),
            '{}media_profile.xml'.format(prefix):
                self.create_profile(is_odk=False, with_media=True, build_profile_id=build_profile_id),
            '{}media_profile.ccpr'.format(prefix):
                self.create_profile(is_odk=True, with_media=True, build_profile_id=build_profile_id),
            '{}suite.xml'.format(prefix): self.create_suite(build_profile_id),
            '{}media_suite.xml'.format(prefix): self.create_media_suite(build_profile_id),
        }
        if self.commcare_flavor:
            files['{}profile-{}.xml'.format(prefix, self.commcare_flavor)] = self.create_profile(
                is_odk=False,
                build_profile_id=build_profile_id,
                commcare_flavor=self.commcare_flavor,
            )
            files['{}profile-{}.ccpr'.format(prefix, self.commcare_flavor)] = self.create_profile(
                is_odk=True,
                build_profile_id=build_profile_id,
                commcare_flavor=self.commcare_flavor,
            )
            files['{}media_profile-{}.xml'.format(prefix, self.commcare_flavor)] = self.create_profile(
                is_odk=False,
                with_media=True,
                build_profile_id=build_profile_id,
                commcare_flavor=self.commcare_flavor,
            )
            files['{}media_profile-{}.ccpr'.format(prefix, self.commcare_flavor)] = self.create_profile(
                is_odk=True,
                with_media=True,
                build_profile_id=build_profile_id,
                commcare_flavor=self.commcare_flavor,
            )

        practice_user_restore = self.create_practice_user_restore(build_profile_id)
        if practice_user_restore:
            files.update({
                '{}practice_user_restore.xml'.format(prefix): practice_user_restore
            })

        files.update(self._make_language_files(prefix, build_profile_id))
        files.update(self._get_form_files(prefix, build_profile_id))
        return files

    get_modules = IndexedSchema.Getter('modules')

    @parse_int([1])
    def get_module(self, i):
        try:
            return self.modules[i].with_id(i % len(self.modules), self)
        except IndexError:
            raise ModuleNotFoundException(_("Could not find module with index {}".format(i)))

    def get_module_by_unique_id(self, unique_id, error=''):
        def matches(module):
            return module.get_or_create_unique_id() == unique_id
        for obj in self.get_modules():
            if matches(obj):
                return obj
        if not error:
            error = _("Could not find module with ID='{unique_id}' in app '{app_name}'.").format(
                app_name=self.name, unique_id=unique_id)
        raise ModuleNotFoundException(error)

    def get_module_index(self, unique_id):
        for index, module in enumerate(self.get_modules()):
            if module.unique_id == unique_id:
                return index
        error = _("Could not find module with ID='{unique_id}' in app '{app_name}'.").format(
            app_name=self.name, unique_id=unique_id)
        raise ModuleNotFoundException(error)

    def get_report_modules(self):
        from .modules import ReportModule
        for module in self.get_modules():
            if isinstance(module, ReportModule):
                yield module

    def get_forms(self, bare=True):
        for module in self.get_modules():
            for form in module.get_forms():
                yield form if bare else {
                    'type': 'module_form',
                    'module': module,
                    'form': form
                }

    def get_form(self, form_unique_id, bare=True):
        def matches(form):
            return form.get_unique_id() == form_unique_id
        for obj in self.get_forms(bare):
            if matches(obj if bare else obj['form']):
                return obj
        raise FormNotFoundException(
            ("Form in app '%s' with unique id '%s' not found"
             % (self.id, form_unique_id)))

    def get_form_location(self, form_unique_id):
        for m_index, module in enumerate(self.get_modules()):
            for f_index, form in enumerate(module.get_forms()):
                if form_unique_id == form.unique_id:
                    return m_index, f_index
        raise KeyError("Form in app '%s' with unique id '%s' not found" % (self.id, form_unique_id))

    @classmethod
    def new_app(cls, domain, name, lang="en"):
        app = cls(domain=domain, modules=[], name=name, langs=[lang], date_created=datetime.datetime.utcnow())
        return app

    def add_module(self, module):
        self.modules.append(module)
        return self.get_module(-1)

    def delete_module(self, module_unique_id):
        from .delete_records import DeleteModuleRecord
        module = self.get_module_by_unique_id(module_unique_id)
        record = DeleteModuleRecord(
            domain=self.domain,
            app_id=self.id,
            module_id=module.id,
            module=module,
            datetime=datetime.datetime.utcnow()
        )
        del self.modules[module.id]
        record.save()
        return record

    def new_form(self, module_id, name, lang, attachment=Ellipsis):
        module = self.get_module(module_id)
        return module.new_form(name, lang, attachment)

    def delete_form(self, module_unique_id, form_unique_id):
        from .delete_records import DeleteFormRecord
        try:
            module = self.get_module_by_unique_id(module_unique_id)
            form = self.get_form(form_unique_id)
        except (ModuleNotFoundException, FormNotFoundException):
            return None

        record = DeleteFormRecord(
            domain=self.domain,
            app_id=self.id,
            module_unique_id=module_unique_id,
            form_id=form.id,
            form=form,
            datetime=datetime.datetime.utcnow(),
        )
        record.save()

        try:
            form.pre_delete_hook()
        except NotImplementedError:
            pass

        del module['forms'][form.id]
        return record

    def rename_lang(self, old_lang, new_lang):
        validate_lang(new_lang)
        if old_lang == new_lang:
            return
        if new_lang in self.langs:
            raise AppEditingError("Language %s already exists!" % new_lang)
        for i, lang in enumerate(self.langs):
            if lang == old_lang:
                self.langs[i] = new_lang
        for profile in self.build_profiles:
            for i, lang in enumerate(profile.langs):
                if lang == old_lang:
                    profile.langs[i] = new_lang
        for module in self.get_modules():
            module.rename_lang(old_lang, new_lang)
        rename_key(self.translations, old_lang, new_lang)

    def rearrange_modules(self, from_index, to_index):
        modules = self.modules
        try:
            if toggles.LEGACY_CHILD_MODULES.enabled(self.domain):
                modules.insert(to_index, modules.pop(from_index))
            else:
                # remove module
                moving_module = modules.pop(from_index)

                # remove its children
                children = [m for m in modules if m.root_module_id == moving_module.unique_id]
                modules = [m for m in modules if m.root_module_id != moving_module.unique_id]

                # add back in module and children
                modules = modules[:to_index] + [moving_module] + children + modules[to_index:]
        except IndexError:
            raise RearrangeError()
        self.modules = modules

    def rearrange_forms(self, from_module_uid, to_module_uid, from_index, to_index):
        """
        The case type of the two modules conflict, the rearrangement goes through anyway.
        This is intentional.

        """
        from_module = self.get_module_by_unique_id(from_module_uid)
        to_module = self.get_module_by_unique_id(to_module_uid)
        try:
            from_module.get_form(from_index).pre_move_hook(from_module, to_module)
        except NotImplementedError:
            pass
        try:
            form = from_module.forms.pop(from_index)
            if not isinstance(form, AdvancedForm):
                if from_module.is_surveys != to_module.is_surveys:
                    if from_module.is_surveys:
                        form.requires = "case"
                        form.actions.update_case = UpdateCaseAction(
                            condition=FormActionCondition(type='always'))
                    else:
                        form.requires = "none"
                        form.actions.update_case = UpdateCaseAction(
                            condition=FormActionCondition(type='never'))
            to_module.add_insert_form(from_module, form, index=to_index, with_source=True)
        except IndexError:
            raise RearrangeError()

    def move_child_modules_after_parents(self):
        # This makes the module ordering compatible with the front-end display
        modules_by_parent_id = OrderedDict(
            (m.unique_id, [m]) for m in self.get_modules() if not m.root_module_id
        )
        orphaned_modules = []
        for module in self.get_modules():
            if module.root_module_id:
                if module.root_module_id in modules_by_parent_id:
                    modules_by_parent_id[module.root_module_id].append(module)
                else:
                    orphaned_modules.append(module)

        normal_modules = [m for modules in modules_by_parent_id.values() for m in modules]
        self.modules = normal_modules + orphaned_modules

    @classmethod
    def from_source(cls, source, domain):
        for field in cls._meta_fields:
            if field in source:
                del source[field]
        source['domain'] = domain
        app = cls.wrap(source)
        return app

    def export_json(self, dump_json=True):
        source = deepcopy(self.to_json())
        for field in self._meta_fields:
            if field in source:
                del source[field]
        _attachments = self.get_attachments()

        # the '_attachments' value is a dict of `name: blob_content`
        # pairs, and is part of the exported (serialized) app interface
        source['_attachments'] = {k: v.decode('utf-8') for (k, v) in _attachments.items()}
        source.pop("external_blobs", None)
        source = self.scrub_source(source)

        return json.dumps(source) if dump_json else source

    def scrub_source(self, source):
        """
        Use this to scrub out anything
        that should be shown in the
        application source, such as ids, etc.
        """
        source = update_form_unique_ids(source, ids_map={})
        return update_report_module_ids(source)

    def copy_form(self, from_module, form, to_module, rename=False):
        """
        The case type of the two modules conflict,
        copying (confusingly) is still allowed.
        This is intentional.

        """
        copy_source = deepcopy(form.to_json())
        # only one form can be a release notes form, so set them to False explicitly when copying
        copy_source['is_release_notes_form'] = False
        copy_source['enable_release_notes'] = False
        if 'unique_id' in copy_source:
            del copy_source['unique_id']

        if rename:
            for lang, name in copy_source['name'].items():
                with override(lang):
                    copy_source['name'][lang] = _('Copy of {name}').format(name=name)

        copy_form = to_module.add_insert_form(from_module, FormBase.wrap(copy_source))
        to_app = to_module.get_app()
        save_xform(to_app, copy_form, form.source.encode('utf-8'))

        return copy_form

    @memoized
    def case_type_exists(self, case_type):
        return case_type in self.get_case_types()

    @memoized
    def get_case_types(self):
        extra_types = set()
        if domain_has_usercase_access(self.domain):
            extra_types.add(const.USERCASE_TYPE)

        return set(chain(*[m.get_case_types() for m in self.get_modules()])) | extra_types

    def has_media(self):
        return len(self.multimedia_map) > 0

    @memoized
    def get_xmlns_map(self):
        xmlns_map = defaultdict(list)
        for form in self.get_forms():
            xmlns_map[form.xmlns].append(form)
        return xmlns_map

    def get_forms_by_xmlns(self, xmlns, log_missing=True):
        """
        Return the forms with the given xmlns.
        This function could return multiple forms if there are shadow forms in the app.
        """
        if xmlns == "http://code.javarosa.org/devicereport":
            return []
        forms = self.get_xmlns_map()[xmlns]
        if len(forms) < 1:
            if log_missing:
                logging.error('App %s in domain %s has %s forms with xmlns %s' % (
                    self.get_id,
                    self.domain,
                    len(forms),
                    xmlns,
                ))
            return []
        non_shadow_forms = [form for form in forms if form.form_type != 'shadow_form']
        assert len(non_shadow_forms) <= 1
        return forms

    def get_xform_by_xmlns(self, xmlns, log_missing=True):
        forms = self.get_forms_by_xmlns(xmlns, log_missing)
        if not forms:
            return None
        else:
            # If there are multiple forms with the same xmlns, then all but one are shadow forms, therefore they
            # all have the same xform.
            return forms[0].wrapped_xform()

    def get_questions(self, xmlns, langs=None, include_triggers=False, include_groups=False,
                      include_translations=False):
        forms = self.get_forms_by_xmlns(xmlns)
        if not forms:
            return []
        # If there are multiple forms with the same xmlns, then some of them are shadow forms, so all the questions
        # will be the same.
        return forms[0].get_questions(langs or self.langs, include_triggers, include_groups, include_translations)

    def validate_app(self):
        validator = ApplicationValidator(self)
        try:
            return validator.validate_app()
        except ModuleIdMissingException:
            # For apps (mainly Exchange apps) that lost unique_id attributes on Module
            self.ensure_module_unique_ids(should_save=True)
            return validator.validate_app()

    def get_profile_setting(self, s_type, s_id):
        setting = self.profile.get(s_type, {}).get(s_id)
        if setting is not None:
            return setting
        yaml_setting = commcare_settings.get_commcare_settings_lookup()[s_type][s_id]
        for contingent in yaml_setting.get("contingent_default", []):
            if check_condition(self, contingent["condition"]):
                setting = contingent["value"]
        if setting is not None:
            return setting
        if not self.build_version or self.build_version < LooseVersion(yaml_setting.get("since", "0")):
            setting = yaml_setting.get("disabled_default", None)
            if setting is not None:
                return setting
        return yaml_setting.get("default")

    @quickcache(['self._id', 'self.version'])
    def get_case_metadata(self):
        from corehq.apps.app_manager.app_schemas.app_case_metadata import AppCaseMetadataBuilder
        return AppCaseMetadataBuilder(self.domain, self).case_metadata()

    def get_subcase_types(self, case_type):
        """
        Return the subcase types defined across an app for the given case type
        """
        return {t for m in self.get_modules()
                if m.case_type == case_type
                for t in m.get_subcase_types()}

    @memoized
    def grid_display_for_some_modules(self):
        return self.grid_form_menus == 'some'

    @memoized
    def grid_display_for_all_modules(self):
        return self.grid_form_menus == 'all'


class RemoteApp(ApplicationBase):
    """
    A wrapper for a url pointing to a suite or profile file. This allows you to
    write all the files for an app by hand, and then give the url to app_manager
    and let it package everything together for you.

    """
    profile_url = StringProperty(default="http://")
    name = StringProperty()
    manage_urls = BooleanProperty(default=False)

    questions_map = DictProperty(required=False)

    def is_remote_app(self):
        return True

    @classmethod
    def new_app(cls, domain, name, lang='en'):
        app = cls(domain=domain, name=name, langs=[lang])
        return app

    def create_profile(self, is_odk=False, langs=None):
        # we don't do odk for now anyway
        return remote_app.make_remote_profile(self, langs)

    def strip_location(self, location):
        return remote_app.strip_location(self.profile_url, location)

    def fetch_file(self, location):
        location = self.strip_location(location)
        url = urljoin(self.profile_url, location)

        try:
            content = urlopen(url).read()
        except Exception:
            raise AppEditingError('Unable to access resource url: "%s"' % url)

        return location, content

    def get_build_langs(self):
        if self.build_profiles:
            if len(list(self.build_profiles.keys())) > 1:
                raise AppEditingError('More than one app profile for a remote app')
            else:
                # return first profile, generated as part of lazy migration
                return self.build_profiles[list(self.build_profiles.keys())[0]].langs
        else:
            return self.langs

    @classmethod
    def get_locations(cls, suite):
        for resource in suite.findall('*/resource'):
            try:
                loc = resource.findtext('location[@authority="local"]')
            except Exception:
                loc = resource.findtext('location[@authority="remote"]')
            yield resource.getparent().tag, loc

    @property
    def SUITE_XPATH(self):
        return 'suite/resource/location[@authority="local"]'

    def create_all_files(self, build_profile_id=None):
        langs_for_build = self.get_build_langs()
        files = {
            'profile.xml': self.create_profile(langs=langs_for_build),
        }
        tree = _parse_xml(files['profile.xml'])

        def add_file_from_path(path, strict=False, transform=None):
            added_files = []
            # must find at least one
            try:
                tree.find(path).text
            except (TypeError, AttributeError):
                if strict:
                    raise AppEditingError("problem with file path reference!")
                else:
                    return
            for loc_node in tree.findall(path):
                loc, file = self.fetch_file(loc_node.text)
                if transform:
                    file = transform(file)
                files[loc] = file
                added_files.append(file)
            return added_files

        add_file_from_path('features/users/logo')
        try:
            suites = add_file_from_path(
                self.SUITE_XPATH,
                strict=True,
                transform=(lambda suite:
                           remote_app.make_remote_suite(self, suite))
            )
        except AppEditingError:
            raise AppEditingError(_('Problem loading suite file from profile file. Is your profile file correct?'))

        for suite in suites:
            suite_xml = _parse_xml(suite)

            for tag, location in self.get_locations(suite_xml):
                location, data = self.fetch_file(location)
                if tag == 'xform' and langs_for_build:
                    try:
                        xform = XForm(data, domain=self.domain)
                    except XFormException as e:
                        raise XFormException('In file %s: %s' % (location, e))
                    xform.exclude_languages(whitelist=langs_for_build)
                    data = xform.render()
                files.update({location: data})
        return files

    def make_questions_map(self):
        langs_for_build = self.get_build_langs()
        if self.copy_of:
            xmlns_map = {}

            def fetch(location):
                filepath = self.strip_location(location)
                return self.fetch_attachment('files/%s' % filepath)

            profile_xml = _parse_xml(fetch('profile.xml'))
            suite_location = profile_xml.find(self.SUITE_XPATH).text
            suite_xml = _parse_xml(fetch(suite_location))

            for tag, location in self.get_locations(suite_xml):
                if tag == 'xform':
                    xform = XForm(fetch(location).decode('utf-8'), domain=self.domain)
                    xmlns = xform.data_node.tag_xmlns
                    questions = xform.get_questions(langs_for_build)
                    xmlns_map[xmlns] = questions
            return xmlns_map
        else:
            return None

    def get_questions(self, xmlns):
        if not self.questions_map:
            self.questions_map = self.make_questions_map()
            if not self.questions_map:
                return []
            self.save()
        questions = self.questions_map.get(xmlns, [])
        return questions


class LinkedApplication(Application):
    """
    An app that can pull changes from an app in a different domain.
    """
    upstream_app_id = StringProperty()  # ID of the app that was most recently pulled
    upstream_version = IntegerProperty()  # Version of the app that was most recently pulled

    # The following properties will overwrite their corresponding values from
    # the master app everytime the new master is pulled
    linked_app_translations = DictProperty()  # corresponding property: translations
    linked_app_logo_refs = DictProperty()  # corresponding property: logo_refs
    linked_app_attrs = DictProperty()  # corresponds to app attributes

    @property
    def supported_settings(self):
        return ['target_commcare_flavor', 'practice_mobile_worker_id']

    @property
    @memoized
    def domain_link(self):
        from corehq.apps.linked_domain.dbaccessors import get_upstream_domain_link
        return get_upstream_domain_link(self.domain)

    @memoized
    def get_master_app_briefs(self):
        if self.domain_link:
            return get_master_app_briefs(self.domain_link, self.family_id)
        return []

    @property
    def master_is_remote(self):
        if self.domain_link:
            return self.domain_link.is_remote

    def get_master_name(self):
        if self.master_is_remote:
            return _('Remote Application')  # Avoid the potentially expensive or impossible query

        latest_app = self.get_latest_master_release(self.upstream_app_id)
        return latest_app.name

    def get_latest_master_release(self, master_app_id):
        if self.domain_link:
            return get_latest_master_app_release(self.domain_link, master_app_id)
        raise ActionNotPermitted

    def get_latest_master_releases_versions(self):
        if self.domain_link:
            versions = get_latest_master_releases_versions(self.domain_link)
            # Use self.get_master_app_briefs to limit return value by family_id
            upstream_ids = [b.id for b in self.get_master_app_briefs()]
            return {key: value for key, value in versions.items() if key in upstream_ids}
        return {}

    @memoized
    def get_latest_build_from_upstream(self, upstream_app_id):
        build_ids = get_build_ids(self.domain, self.origin_id)
        for build_id in build_ids:
            build_doc = Application.get_db().get(build_id)
            if build_doc.get('upstream_app_id') == upstream_app_id:
                return self.wrap(build_doc)
        return None

    @memoized
    def _get_version_comparison_build(self):
        previous_version = self.get_latest_build_from_upstream(self.upstream_app_id)
        if not previous_version:
            # If there's no previous version, check for a previous version in the same family.
            # This allows projects using multiple masters to copy a master app and start pulling
            # from that copy without resetting the form and multimedia versions.
            previous_version = self.get_latest_build_from_upstream(self.family_id)
        return previous_version

    def reapply_overrides(self):
        # Used by app_manager.views.utils.update_linked_app()
        self.translations.update(self.linked_app_translations)
        self.logo_refs.update(self.linked_app_logo_refs)
        for attribute, value in self.linked_app_attrs.items():
            setattr(self, attribute, value)
        for key, ref in self.logo_refs.items():
            mm = CommCareMultimedia.get(ref['m_id'])
            self.create_mapping(mm, ref['path'], save=False)


def import_app(app_id_or_doc, domain, extra_properties=None, request=None):
    source_app = _get_source_app(app_id_or_doc)
    source_doc = source_app.export_json(dump_json=False)

    attachments = _get_attachments(source_doc)
    source_doc['_attachments'] = {}

    if extra_properties is not None:
        source_doc.update(extra_properties)

    # Allow the wrapper to update to the current default build_spec
    if 'build_spec' in source_doc:
        del source_doc['build_spec']

    app = _create_app_from_doc(domain, source_doc)
    if source_app.domain == domain:
        app.family_id = source_app.origin_id

    report_map = get_static_report_mapping(source_app.domain, domain)
    _update_report_config_ids(app, report_map, source_app.domain)

    app.save_attachments(attachments)

    try:
        _update_valid_domains_for_media(app, domain)
    except ReportConfigurationNotFoundError:
        if request:
            messages.warning(request, _("Copying the application succeeded, but the application will have errors "
                                        "because your application contains a Mobile Report Module that references "
                                        "a UCR configured in this project space. Multimedia may be absent."))
    except ResourceNotFound:
        messages.warning(request, _("Copying the application succeeded, but the application is missing "
                                    "multimedia file(s)."))

    return app


def _get_source_app(app_id_or_doc):
    if isinstance(app_id_or_doc, str):
        source_app = get_app(None, app_id_or_doc)
    else:
        source_app = wrap_app(app_id_or_doc)
    return source_app


def _get_attachments(doc):
    try:
        attachments = doc['_attachments']
    except KeyError:
        attachments = {}

    return attachments


def _create_app_from_doc(domain, doc):
    app_class = get_correct_app_class(doc)
    app = app_class.from_source(doc, domain)
    app.convert_build_to_app()
    app.date_created = datetime.datetime.utcnow()
    app.cloudcare_enabled = domain_has_privilege(domain, privileges.CLOUDCARE)

    return app


def _update_report_config_ids(app, report_map, domain):
    if report_map:
        for module in app.get_report_modules():
            for config in module.report_configs:
                try:
                    config.report_id = report_map[config.report_id]
                except KeyError:
                    if config.report(domain).is_static:
                        raise AppEditingError(
                            "Report {} not found in {}".format(config.report_id, domain)
                        )


def _update_valid_domains_for_media(app, domain_to_add):
    if not app.is_remote_app():
        for path, media in app.get_media_objects(remove_unused=True):
            if domain_to_add not in media.valid_domains:
                media.valid_domains.append(domain_to_add)
                media.save()



class ExchangeApplication(models.Model):
    domain = models.CharField(max_length=255, null=False)
    app_id = models.CharField(max_length=255, null=False)
    help_link = models.CharField(max_length=255, null=True)
    changelog_link = models.CharField(max_length=255, null=True)
    required_privileges = models.TextField(null=True, blank=True, help_text=_("Space-separated list of privilege"
                                                                 " strings from corehq.privileges"))

    class Meta(object):
        unique_together = ('domain', 'app_id')


class ExchangeApplicationAdmin(admin.ModelAdmin):
    model = ExchangeApplication
    list_display = ['domain', 'app_id', 'help_link', 'changelog_link']
    list_filter = ['domain', 'app_id']


admin.site.register(ExchangeApplication, ExchangeApplicationAdmin)


class GlobalAppConfig(models.Model):
    choices = [(c, c) for c in ("on", "off", "forced")]

    domain = models.CharField(max_length=255, null=False)

    # this should be the unique id of the app (not of a versioned copy)
    app_id = models.CharField(max_length=255, null=False)
    app_prompt = models.CharField(max_length=32, choices=choices, default="off")
    apk_prompt = models.CharField(max_length=32, choices=choices, default="off")
    apk_version = models.CharField(max_length=32, null=True)
    app_version = models.IntegerField(null=True)

    class Meta(object):
        unique_together = ('domain', 'app_id')

    _app = None

    @classmethod
    def by_app(cls, app):
        model = cls.by_app_id(app.domain, app.origin_id)
        model._app = app
        return model

    @classmethod
    def by_app_id(cls, domain, app_id):
        model, created = cls.objects.get_or_create(app_id=app_id, domain=domain, defaults={
            'apk_version': LATEST_APK_VALUE,
            'app_version': LATEST_APP_VALUE,
        })
        return model

    def save(self, force_insert=False, force_update=False, using=DEFAULT_DB_ALIAS, update_fields=None):
        if self.pk:
            self.clear_version_caches()
        super().save(
            force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields
        )

    @property
    def app(self):
        if not self._app:
            app = get_app(self.domain, self.app_id, latest=True, target='release')
            assert self.app_id == app.origin_id, "this class doesn't handle copy app ids"
            self._app = app
        return self._app

    def get_latest_apk_version(self):
        self.app  # noqa validate app
        if self.apk_prompt == "off":
            return {}
        else:
            configured_version = self.apk_version
            if configured_version == LATEST_APK_VALUE:
                value = get_default_build_spec().version
            else:
                value = BuildSpec.from_string(configured_version).version
            force = self.apk_prompt == "forced"
            return {"value": value, "force": force}

    def get_latest_app_version(self):
        self.app  # noqa validate app
        if self.app_prompt == "off":
            return {}
        else:
            force = self.app_prompt == "forced"
            app_version = self.app_version
            if app_version != LATEST_APP_VALUE:
                return {"value": app_version, "force": force}
            else:
                if not self.app or not self.app.is_released:
                    return {}
                else:
                    version = self.app.version
                    return {"value": version, "force": force}

    @classmethod
    @quickcache(['domain', 'app_id'])
    def get_latest_version_info(cls, domain, app_id):
        config = GlobalAppConfig.by_app_id(domain, app_id)
        return {
            "latest_apk_version": config.get_latest_apk_version(),
            "latest_ccz_version": config.get_latest_app_version(),
        }

    def clear_version_caches(self):
        GlobalAppConfig.get_latest_version_info.clear(
            GlobalAppConfig, self.domain, self.app_id
        )


class AppReleaseByLocation(models.Model):
    domain = models.CharField(max_length=255, null=False)
    app_id = models.CharField(max_length=255, null=False)
    location = models.ForeignKey(SQLLocation, on_delete=models.CASCADE, to_field='location_id')
    build_id = models.CharField(max_length=255, null=False)
    version = models.IntegerField(null=False)
    active = models.BooleanField(default=True)
    activated_on = models.DateTimeField(null=True, blank=True)
    deactivated_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = (("domain", "build_id", "location", "version"),)

    def save(self, *args, **kwargs):
        super(AppReleaseByLocation, self).save(*args, **kwargs)
        expire_get_latest_app_release_by_location_cache(self)

    @property
    @memoized
    def build(self):
        return get_app(self.domain, self.build_id)

    def clean(self):
        if self.active:
            if not self.build.is_released:
                raise ValidationError({'version': _("Version {} not released. Please mark it as released to add "
                                                    "restrictions.").format(self.build.version)})
            enabled_release = get_latest_app_release_by_location(self.domain, self.location.location_id,
                                                                 self.app_id)
            if enabled_release and enabled_release.version > self.version:
                raise ValidationError({'version': _("Higher version {} already enabled for this application and "
                                                    "location").format(enabled_release.version)})

    @classmethod
    def update_status(cls, domain, app_id, build_id, location_id, version, active):
        """
        create a new object or just set the status of an existing one with provided
        domain, app_id, build_id, location_id and version to the status passed
        :param build_id: id of the build corresponding to the version
        """
        try:
            release = AppReleaseByLocation.objects.get(
                domain=domain, app_id=app_id, build_id=build_id, location_id=location_id, version=version
            )
        except cls.DoesNotExist:
            release = AppReleaseByLocation(
                domain=domain, app_id=app_id, build_id=build_id, location_id=location_id, version=version
            )
        release.activate() if active else release.deactivate()

    def deactivate(self):
        self.active = False
        self.deactivated_on = datetime.datetime.utcnow()
        self.full_clean()
        self.save()

    def activate(self):
        self.active = True
        self.activated_on = datetime.datetime.utcnow()
        self.full_clean()
        self.save()

    def to_json(self):
        return {
            'location': self.location.get_path_display(),
            'app': self.app_id,
            'build_id': self.build_id,
            'version': self.version,
            'active': self.active,
            'id': self._get_pk_val(),
            'activated_on': (datetime.datetime.strftime(self.activated_on, '%Y-%m-%d  %H:%M:%S')
                             if self.activated_on else None),
            'deactivated_on': (datetime.datetime.strftime(self.deactivated_on, '%Y-%m-%d %H:%M:%S')
                               if self.deactivated_on else None),
        }


class ApplicationReleaseLog(models.Model):
    ACTION_RELEASED = "released"
    ACTION_IN_TEST = "in_test"
    ACTION_CREATED = "created"
    ACTION_REVERTED = "reverted"
    ACTION_DELETED = "deleted"

    ACTION_DISPLAY = {
        ACTION_RELEASED: _("Released"),
        ACTION_IN_TEST: _("In Test"),
        ACTION_CREATED: _("Created"),
        ACTION_REVERTED: _("Reverted"),
        ACTION_DELETED: _("Deleted")
    }

    domain = models.CharField(max_length=255, null=False, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=255)
    version = models.IntegerField()
    app_id = models.CharField(max_length=255)
    user_id = models.CharField(max_length=255)
    info = models.JSONField(default=dict)

    def to_json(self):
        return {
            "created_at": self.created_at,
            "action": self.ACTION_DISPLAY[self.action],
            "version": self.version,
            "user_id": self.user_id,
        }


class CredentialApplication(models.Model):
    """
    Represents an application that issues credentials to users when
    they have been active for a certain activity_level.
    """
    domain = models.CharField(max_length=255)
    app_id = models.CharField(max_length=255)
    activity_level = models.CharField(
        max_length=32,
        choices=ActivityLevel.choices,
        default=ActivityLevel.THREE_MONTHS,
    )

    class Meta:
        unique_together = ('domain', 'app_id')
