from datetime import datetime
import logging
from zipfile import ZipFile
from corehq.apps.app_manager.const import APP_V1, APP_V2
from couchdbkit.exceptions import ResourceNotFound, BadValueError
from couchdbkit.ext.django.schema import *
from corehq.apps.builds.fixtures import commcare_build_config
from corehq.apps.builds.jadjar import JadJar

class SemanticVersionProperty(StringProperty):
    def validate(self, value, required=True):
        super(SemanticVersionProperty, self).validate(value, required)
        try:
            major, minor, _ = value.split('.')
            int(major)
            int(minor)
        except Exception:
            raise BadValueError("Build version %r does not comply with the x.y.z schema" % value)
        return value
    
class CommCareBuild(Document):
    """
    #python manage.py shell
    #>>> from corehq.apps.builds.models import CommCareBuild
    #>>> build = CommCareBuild.create_from_zip('/Users/droberts/Desktop/zip/7106.zip', '1.2.dev', 7106)

    """

    build_number = IntegerProperty()
    version = SemanticVersionProperty()
    time = DateTimeProperty()
    
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
        self.put_attachment(payload, path, content_type)

    def fetch_file(self, path, filename=None):
        if filename:
            path = '/'.join([path, filename])
        return self.fetch_attachment(path)

    def get_jadjar(self, path):
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
            build_number=self.build_number
        )

    @classmethod
    def create_from_zip(cls, f, version, build_number):
        """f should be a file-like object or a path to a zipfile"""
        self = cls(build_number=build_number, version=version, time=datetime.utcnow())
        self.save()

        z = ZipFile(f)
        try:
            for name in z.namelist():
                path = name.split('/')
                if path[0] == "dist" and path[-1] != "":
                    path = '/'.join(path[1:])
                    self.put_file(z.read(name), path)
        except:
            self.delete()
            raise
        finally:
            z.close()
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
        ).one()

        if not self:
            raise KeyError("Can't find build {label}. For instructions on how to add it, see https://github.com/dimagi/core-hq/blob/master/corehq/apps/builds/README.md".format(label=BuildSpec(
                version=version,
                build_number=build_number,
                latest=latest
            )))
        return self

    @classmethod
    def all_builds(cls):
        return cls.view('builds/all', include_docs=True)

class BuildSpec(DocumentSchema):
    version = StringProperty()
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
            fmt = "{self.version} "
            fmt += "(latest)" if self.latest else "({self.build_number})"
            return fmt.format(self=self)
        else:
            return None

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
        return ".".join(self.version.split('.')[:2])
    def major_release(self):
        return self.version.split('.')[0]

class BuildMenuItem(DocumentSchema):
    build = SchemaProperty(BuildSpec)
    label = StringProperty(required=False)
    superuser_only = BooleanProperty(default=False)

    def get_build(self):
        return self.build.get_build()

    def get_label(self):
        return self.label or self.build.get_label()
    
class CommCareBuildConfig(Document):
    ID = "config--commcare-builds"
    preview = SchemaProperty(BuildSpec)
    defaults = SchemaListProperty(BuildSpec)
    application_versions = StringListProperty()
    menu = SchemaListProperty(BuildMenuItem)

    @classmethod
    def bootstrap(cls):
        config = cls.wrap(commcare_build_config)
        config._id = config.ID
        config.save()
        return config

    @classmethod
    def fetch(cls):
        try:
            return cls.get(cls.ID.default)
        except ResourceNotFound:
            return cls.bootstrap()

    def get_default(self, application_version):
        i = self.application_versions.index(application_version)
        return self.defaults[i]

    def get_menu(self, application_version=None):
        if application_version:
            major = {
                APP_V1: '1',
                APP_V2: '2',
            }[application_version]
            return filter(lambda x: x.build.major_release() == major, self.menu)
        else:
            return self.menu


class BuildRecord(BuildSpec):
    signed = BooleanProperty(default=True)
    datetime = DateTimeProperty(required=False)
