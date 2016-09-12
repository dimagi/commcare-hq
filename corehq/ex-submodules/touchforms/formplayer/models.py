from __future__ import absolute_import
from django.db import models
from django.core.files import File
from datetime import datetime
from xml.etree import ElementTree
import re
import os
import hashlib
import tempfile
from django.contrib.auth.models import User

VERSION_KEY = "version"
UIVERSION_KEY = "uiVersion"


class SqlStatus(models.Model):
    username = models.CharField(max_length=255, primary_key=True)
    app_version = models.IntegerField()
    last_modified = models.DateTimeField(null=True)
    date_created = models.DateTimeField(null=True)


class Session(models.Model):
    sess_id = models.CharField(max_length=100, primary_key=True)
    sess_json = models.TextField()
    last_modified = models.DateTimeField(null=True)
    date_created = models.DateTimeField(null=True)

    class Meta:
        app_label = 'formplayer'


class EntrySession(models.Model):
    session_id = models.CharField(max_length=100, primary_key=True)
    user = models.ForeignKey(User)
    form = models.CharField(max_length=255)  # url of cloudcare form
    app_id = models.CharField(max_length=32, null=True, blank=True)  # HQ app ID, if relevant
    session_name = models.CharField(max_length=100)
    created_date = models.DateTimeField(default=datetime.utcnow)
    last_activity_date = models.DateTimeField(null=True)
    
    class Meta:
        app_label = 'formplayer'


class XForm(models.Model):
    """A record of an XForm"""
    
    # NOTE: this is a somewhat static list for BHOMA.  It may not be
    # worth all the overhead to keep this flexible in this model.
    
    # NOTE: should these be in couch?
    created = models.DateTimeField(default=datetime.utcnow)
    name = models.CharField(max_length=255)
    namespace = models.CharField(max_length=255)
    version = models.IntegerField(null=True)
    uiversion = models.IntegerField(null=True)
    checksum = models.CharField(help_text='Attachment SHA-1 Checksum',
                                max_length=40, blank=True)
    file = models.FileField(upload_to="xforms", max_length=255)
    
    def __unicode__(self):
        return "%s (%s)" % (self.name, self.namespace)
    
    class Meta:
        app_label = 'formplayer'

    @classmethod
    def from_file(cls, filename, name=None):
        """Create an xform from the original xml/xhtml file"""
        f = File(open(filename, 'r'))
        try:
            if name is None:
                name = os.path.basename(f.name)
            file_contents = f.read()
            checksum = hashlib.sha1(file_contents).hexdigest()
            # TODO: parsing is exremely brittle and we should use jad/jar javarosa 
            # stuff for it
            element = ElementTree.XML(file_contents)
            head = element[0]
            namespace, version, uiversion = [None,] * 3
            for child in head:
                if "model" in child.tag:
                    for subchild in child:
                        if "instance" in subchild.tag and 'src' not in subchild.attrib:
                            instance_root = subchild[0]
                            r = re.search('{[a-zA-Z0-9_\-\.\/\:]*}', instance_root.tag)
                            if r is None:
                                raise Exception("No namespace found in xform: %s" % name)
                            for key, value in instance_root.attrib.items():
                                # we do case-sensitive comparison because that's the 
                                # xml spec.  we may want to make this less academic
                                # and more user friendly.
                                if key.strip() == VERSION_KEY:
                                    version = int(value)
                                elif key.strip() == UIVERSION_KEY:
                                    uiversion = int(value)
                            
                            namespace = r.group(0).strip('{').strip('}')
            if not namespace:
                raise Exception("No namespace found in xform: %s" % name)
        
            instance = cls.objects.create(name=name, namespace=namespace, 
                                            version=version, uiversion=uiversion,
                                            checksum=checksum, file=f)           
            return instance
        finally:
            f.close()
                        
    @classmethod
    def from_raw(cls, raw_xml):
        """Create an xform from the raw xml content"""
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as f:
            f.write(raw_xml)

        checksum = hashlib.sha1(raw_xml).hexdigest()
        element = ElementTree.XML(raw_xml)
        head = element[0]
        namespace, version, uiversion = [None,] * 3
        for child in head:
            if "model" in child.tag:
                for subchild in child:
                    if "instance" in subchild.tag and 'src' not in subchild.attrib:
                        instance_root = subchild[0]
                        r = re.search('{[a-zA-Z0-9_\-\.\/\:]*}', instance_root.tag)
                        if r is None:
                            raise Exception("No namespace found in xform: %s" % name)
                        for key, value in instance_root.attrib.items():
                            # we do case-sensitive comparison because that's the 
                            # xml spec.  we may want to make this less academic
                            # and more user friendly.
                            if key.strip() == VERSION_KEY:
                                version = int(value)
                            elif key.strip() == UIVERSION_KEY:
                                uiversion = int(value)
                            
                        namespace = r.group(0).strip('{').strip('}')
            if 'title' in child.tag:
                name = child.text
        if not namespace:
            raise Exception("No namespace found in xform: %s" % name)
        
        try:
            return cls.objects.get(checksum=checksum)
        except cls.DoesNotExist:
            with File(open(path)) as f:
                o = cls(name=name, namespace=namespace, 
                        version=version, uiversion=uiversion,
                        checksum=checksum, file=f)
                o.save()
                return o
