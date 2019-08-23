from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
from zipfile import ZipFile
from couchdbkit.exceptions import ResourceNotFound, BadValueError
from corehq.apps.app_manager.const import APP_V2
from dimagi.ext.couchdbkit import *
from corehq.apps.builds.fixtures import commcare_build_config
from corehq.apps.builds.jadjar import JadJar
from corehq.apps.domain import SHARED_DOMAIN
from corehq.blobs import CODES as BLOB_CODES
from corehq.blobs.mixin import BlobMixin
from corehq.util.quickcache import quickcache
from itertools import groupby
from distutils.version import StrictVersion


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
    j2me_enabled = BooleanProperty(default=True)
    _blobdb_type_code = BLOB_CODES.commcarebuild

    def put_file(self, payload, path, filename=None):
        """
        Add an attachment to the build (useful for constructing the build)
        payload should be a file-like object
        filename should be something like "Nokia/S40-generic/CommCare.jar"

        """
        if filename:
            path = '/'.join([path, filename])
        content_type = {
            'jad': 'text/vnd.sun.j2me.app-descriptor',
            'jar': 'application/java-archive',
        }.get(path.split('.')[-1])
        self.put_attachment(payload, path, content_type, domain=SHARED_DOMAIN)

    def fetch_file(self, path, filename=None):
        if filename:
            path = '/'.join([path, filename])
        attachment = self.fetch_attachment(path)
        try:
            return attachment.decode('utf-8')
        except UnicodeDecodeError:
            return attachment

    def get_jadjar(self, path, use_j2me_endpoint):
        """
        build.get_jadjar("Nokia/S40-generic")
        """
        try:
            jad = self.fetch_file(path, "CommCare.jad")
        except ResourceNotFound:
            jad = None

        return JadJar(
            jad=jad,
            jar=self.fetch_file(path, "CommCare.jar"),
            version=self.version,
            build_number=self.build_number,
            use_j2me_endpoint=use_j2me_endpoint,
        )

    @classmethod
    def create_from_zip(cls, f, version, build_number):
        """f should be a file-like object or a path to a zipfile"""
        self = cls(build_number=build_number, version=version, time=datetime.utcnow())
        self.save()
        # Clear cache to have this new build included immediately
        cls.j2me_enabled_builds.clear(cls)

        with ZipFile(f) as z:
            try:
                for name in z.namelist():
                    path = name.split('/')
                    if path[0] == "dist" and path[-1] != "":
                        path = '/'.join(path[1:])
                        self.put_file(z.read(name), path)
            except:
                self.delete()
                raise
        return self

    @classmethod
    def create_without_artifacts(cls, version, build_number):
        self = cls(build_number=build_number, version=version,
                   time=datetime.utcnow(), j2me_enabled=False)
        self.save()
        # Clear cache to have this build number excluded immediately if build added
        # with existing version number but not supporting j2me now
        cls.j2me_enabled_builds.clear(cls)
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

    @classmethod
    @quickcache([], timeout=5 * 60)
    def j2me_enabled_builds(cls):
        j2me_enabled_builds = []
        for version_number, group in groupby(cls.all_builds(), lambda x: x['version']):
            latest_version_build = list(group)[-1]
            if latest_version_build['j2me_enabled']:
                j2me_enabled_builds.append(latest_version_build)

        return j2me_enabled_builds

    @classmethod
    def j2me_enabled_build_versions(cls):
        return [x.version for x in cls.j2me_enabled_builds()]


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

    def supports_j2me(self):
        return self.get_menu_item_label() in CommCareBuildConfig.j2me_enabled_config_labels()

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

    def release_greater_than_or_equal_to(self, version):
        if not self.version:
            return False
        return StrictVersion(self.version) >= StrictVersion(version)


class BuildMenuItem(DocumentSchema):
    build = SchemaProperty(BuildSpec)
    label = StringProperty(required=False)
    superuser_only = BooleanProperty(default=False)
    j2me_enabled = BooleanProperty(default=True)

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

    @classmethod
    @quickcache([], timeout=5 * 60)
    def j2me_enabled_configs(cls):
        return [build for build in cls.fetch().menu if build.j2me_enabled]

    @classmethod
    def j2me_enabled_config_labels(cls):
        return [x.label for x in cls.j2me_enabled_configs()]

    @classmethod
    def latest_j2me_enabled_config(cls):
        return cls.j2me_enabled_configs()[-1]


class BuildRecord(BuildSpec):
    signed = BooleanProperty(default=True)
    datetime = DateTimeProperty(required=False)
