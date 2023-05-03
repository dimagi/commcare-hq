from datetime import datetime
from looseversion import LooseVersion
from zipfile import ZipFile

from couchdbkit.exceptions import BadValueError, ResourceNotFound

from dimagi.ext.couchdbkit import *

from corehq.apps.app_manager.const import APP_V2
from corehq.apps.builds.fixtures import commcare_build_config
from corehq.apps.domain import SHARED_DOMAIN
from corehq.blobs import CODES as BLOB_CODES
from corehq.blobs.mixin import BlobMixin
from corehq.util.quickcache import quickcache


class SemanticVersionProperty(StringProperty):

    def validate(self, value, required=True):
        super(SemanticVersionProperty, self).validate(value, required)
        if not self.required and not value:
            return value
        try:
            major, minor, point = value.split('.')
            int(major)
            int(minor)
            int(point)
        except Exception:
            raise BadValueError("Build version %r does not comply with the x.y.z schema" % value)
        return value


class CommCareBuild(BlobMixin, Document):
    """
    #python manage.py shell
    #>>> from corehq.apps.builds.models import CommCareBuild
    #>>> build = CommCareBuild.create_from_zip('/Users/droberts/Desktop/zip/7106.zip', '1.2.dev', 7106)

    """

    build_number = IntegerProperty()
    version = SemanticVersionProperty()
    time = DateTimeProperty()
    _blobdb_type_code = BLOB_CODES.commcarebuild

    def fetch_file(self, path, filename=None):
        if filename:
            path = '/'.join([path, filename])
        attachment = self.fetch_attachment(path)
        try:
            return attachment.decode('utf-8')
        except UnicodeDecodeError:
            return attachment

    @classmethod
    def create_without_artifacts(cls, version, build_number):
        self = cls(build_number=build_number, version=version,
                   time=datetime.utcnow())
        self.save()
        return self

    def minor_release(self):
        major, minor, _ = self.version.split('.')
        return int(major), int(minor)

    def major_release(self):
        major, _, _ = self.version.split('.')
        return int(major)

    @classmethod
    def get_build(cls, version, build_number=None, latest=False):
        """
        Call as either
            CommCareBuild.get_build(version, build_number)
        or
            CommCareBuild.get_build(version, latest=True)
        """

        if latest:
            startkey = [version]
        else:
            build_number = int(build_number)
            startkey = [version, build_number]

        self = cls.view('builds/all',
            startkey=startkey + [{}],
            endkey=startkey,
            descending=True,
            limit=1,
            include_docs=True,
            reduce=False,
        ).one()

        if not self:
            raise KeyError("Can't find build {label}. For instructions on how to add it, see https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/builds/README.md".format(label=BuildSpec(
                version=version,
                build_number=build_number,
                latest=latest
            )))
        return self

    @classmethod
    def all_builds(cls):
        return cls.view('builds/all', include_docs=True, reduce=False)


class BuildSpec(DocumentSchema):
    version = SemanticVersionProperty(required=False)
    build_number = IntegerProperty(required=False)
    latest = BooleanProperty()

    def get_build(self):
        if self.latest:
            return CommCareBuild.get_build(self.version, latest=True)
        else:
            return CommCareBuild.get_build(self.version, self.build_number)

    def is_null(self):
        return not (self.version and (self.build_number or self.latest))

    def get_label(self):
        if not self.is_null():
            fmt = "{self.version}"
            return fmt.format(self=self)
        else:
            return None

    def get_menu_item_label(self):
        build_config = CommCareBuildConfig.fetch()
        for item in build_config.menu:
            if item.build.version == self.version:
                return item.label or self.get_label()
        return self.get_label()

    def __str__(self):
        fmt = "{self.version}/"
        fmt += "latest" if self.latest else "{self.build_number}"
        return fmt.format(self=self)

    def to_string(self):
        return str(self)

    @classmethod
    def from_string(cls, string):
        version, build_number = string.split('/')
        if build_number == "latest":
            return cls(version=version, latest=True)
        else:
            build_number = int(build_number)
            return cls(version=version, build_number=build_number)

    def minor_release(self):
        major, minor, _ = self.version.split('.')
        return int(major), int(minor)

    def major_release(self):
        return self.version.split('.')[0]

    def patch_release(self):
        major, minor, minimal = self.version.split('.')
        return int(major), int(minor), int(minimal)

    def release_greater_than_or_equal_to(self, version):
        if not self.version:
            return False
        return LooseVersion(self.version) >= LooseVersion(version)


class BuildMenuItem(DocumentSchema):
    build = SchemaProperty(BuildSpec)
    label = StringProperty(required=False)
    superuser_only = BooleanProperty(default=False)

    def get_build(self):
        return self.build.get_build()

    def get_label(self):
        return self.label or self.build.get_label()


class CommCareBuildConfig(Document):
    _ID = 'config--commcare-builds'

    preview = SchemaProperty(BuildSpec)
    defaults = SchemaListProperty(BuildSpec)
    application_versions = StringListProperty()
    menu = SchemaListProperty(BuildMenuItem)

    @classmethod
    def bootstrap(cls):
        config = cls.wrap(commcare_build_config)
        config._id = config._ID
        config.save()
        return config

    @classmethod
    def clear_local_cache(cls):
        cls.fetch.clear(cls)

    @classmethod
    @quickcache([], timeout=24 * 60 * 60)
    def fetch(cls):
        try:
            return cls.get(cls._ID)
        except ResourceNotFound:
            return cls.bootstrap()

    def get_default(self, application_version=APP_V2):
        i = self.application_versions.index(application_version)
        return self.defaults[i]

    def get_menu(self):
        return self.menu


class BuildRecord(BuildSpec):
    signed = BooleanProperty(default=True)
    datetime = DateTimeProperty(required=False)
