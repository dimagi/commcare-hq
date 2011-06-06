from datetime import datetime
from zipfile import ZipFile
from couchdbkit.exceptions import ResourceNotFound
from couchdbkit.ext.django.schema import *
from corehq.apps.builds.jadjar import JadJar

class CommCareBuild(Document):
    """
    #python manage.py shell
    #>>> from corehq.apps.builds.models import CommCareBuild
    #>>> build = CommCareBuild.create_from_zip('/Users/droberts/Desktop/zip/7106.zip', '1.2.dev', 7106)

    """

    build_number = IntegerProperty()
    version = StringProperty()
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
        try:
            z = ZipFile(f)
            for name in z.namelist():
                path = name.split('/')
                if path[0] == "dist":
                    path = '/'.join(path[1:])
                    self.put_file(z.read(name), path)
        except:
            z.close()
            self.delete()
            raise
        z.close()
        return self

    @classmethod
    def get_build(cls, version, build_number):
        build_number = int(build_number)
        self = cls.view('builds/all',
            startkey=[version, build_number],
            endkey=[version, build_number, {}],
            limit=1,
            include_docs=True,
        ).one()
        if not self:
            raise KeyError()
        return self


