from django.db import models
from django.contrib.auth.models import User
from hq.models import ExtUser
from hq.models import Domain
from requestlogger.models import RequestLog

from buildmanager.jar import validate_jar, extract_xforms
from buildmanager.exceptions import BuildError

import os
import logging
import settings
from datetime import datetime
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse

BUILDFILES_PATH = settings.RAPIDSMS_APPS['buildmanager']['buildpath']


class Project (models.Model):
    """
    A project is a high level container for a given build project.  A project 
    can contain a history of builds
    """
    domain = models.ForeignKey(Domain) 
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=512, null=True, blank=True)
    # the optional project id in a different server (e.g. the build server)
    project_id = models.CharField(max_length=20, null=True, blank=True)
    
    @property
    def downloads(self):
        '''Get all the downloads associated with this project, across
           builds.'''
        return BuildDownload.objects.filter(build__project=self)
    
    def get_non_released_builds(self):
        '''Get all non-released builds for this project'''
        return self.builds.exclude(status="release").order_by('-package_created')
    
    def get_released_builds(self):
        '''Get all released builds for a project'''
        return self.builds.filter(status="release").order_by('-released')
        
    def get_latest_released_build(self):
        '''Gets the latest released build for a project, based on the 
           released date.'''
        releases = self.get_released_builds()
        if releases:
           return releases[0]
    
    def get_latest_jar_url(self):
        '''Get the URL for the latest released jar file, empty if no builds
           have been released'''
        build = self.get_latest_released_build()
        if build:
            return reverse('get_latest_buildfile',
                           args=(self.id,
                                  build.get_jar_filename()))
        return None
    
    def get_latest_jad_url(self):
        '''Get the URL for the latest released jad file, empty if no builds
           have been released'''
        build = self.get_latest_released_build()
        if build:
            return reverse('get_latest_buildfile',
                            args=(self.id,
                                  build.get_jad_filename()))
        return None
                                             
    def get_buildURL(self):
        """Hard coded build url for our build server"""
        return 'http://build.dimagi.com:250/viewType.html?buildTypeId=bt%s' % self.project_id
        
    def num_builds(self):
        '''Get the number of builds associated with this project'''
        return self.builds.all().count()
    
    def __unicode__(self):
        return unicode(self.name)


BUILD_STATUS = (    
    ('build', 'Standard Build'),    
    # CZUE: removed extraneous build types to make this as simple as possible
    # we may want to reintroduce these down the road when we really sort
    # out our processes
    # ('alpha', 'Alpha'),
    # ('beta', 'Beta'),
    # ('rc', 'Release Candidate'),    
    ('release', 'Release'),   
)


class ProjectBuild(models.Model):
    '''When a jad/jar is built, it should correspond to a unique ReleasePackage
    With all corresponding meta information on release info and build 
    information such that it can be traced back to a url/build info in source 
    control.'''    
    project = models.ForeignKey(Project, related_name="builds")
    
    # we have it as a User instead of ExtUser here because we want our 
    # build server User to be able to push to multiple omains
    uploaded_by = models.ForeignKey(User, related_name="builds_uploaded") 
    status = models.CharField(max_length=64, choices=BUILD_STATUS, default="build")
    
    # the teamcity build number
    build_number = models.PositiveIntegerField()
    # the source control revision number       
    revision_number = models.CharField(max_length=255, null=True, blank=True)
    
    # the "release" version.  e.g. 2.0.1
    version = models.CharField(max_length=20, null=True, blank=True)
    
    package_created = models.DateTimeField()    
    
    jar_file = models.FilePathField(_('JAR File Location'), 
                                    match='.*\.jar$', 
                                    recursive=True,
                                    path=BUILDFILES_PATH, 
                                    max_length=255)
    
    jad_file = models.FilePathField(_('JAD File Location'), 
                                    match='.*\.jad$',
                                    recursive=True, 
                                    path=BUILDFILES_PATH, 
                                    max_length=255)
    
    description = models.CharField(max_length=512, null=True, blank=True)

    # release info
    released = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey(User, null=True, blank=True, related_name="builds_released")
    
    def __unicode__(self):
        return "%s build: %s" % (self.project, self.build_number)

    def get_jar_download_count(self):
        return len(self.downloads.filter(type="jar"))
    
    def get_jad_download_count(self):
        return len(self.downloads.filter(type="jad"))
    
    
    def save(self):
        """Override save to provide some simple enforcement of uniqueness to the build numbers
        generated by the submission of the build"""        
        if ProjectBuild.objects.filter(project=self.project).filter(build_number=self.build_number).count() > 0 and self.id == None:
                raise Exception ("Error, the build number must be unique for this project build: " + str(self.build_number) + " project: " + str(self.project.id))
        else:            
            super(ProjectBuild, self).save()
    
    def get_jar_filename(self):
        '''Returns the name (no paths) of the jar file'''
        return os.path.basename(self.jar_file)
    
    def get_jad_filename(self):
        '''Returns the name (no paths) of the jad file'''
        return os.path.basename(self.jad_file)
    
    def get_jar_filestream(self):
        
        try:
            fin = open(self.jar_file,'r')
            return fin
        except Exception, e:
            logging.error("Unable to open jarfile", extra={"exception": e, 
                                                           "jar_file": self.jar_file, 
                                                           "build_number": self.build_number,
                                                           "project_id": self.project.id})
    def get_jad_filestream(self):        
        try:
            fin = open(self.jad_file,'r')
            return fin
        except Exception, e:
            logging.error("Unable to open jadfile", extra={"exception": e, 
                                                           "jad_file": self.jad_file, 
                                                           "build_number": self.build_number,
                                                           "project_id": self.project.id})
    def get_jad_contents(self):
        '''Returns the contents of the jad as text.'''
        file = self.get_jad_filestream()
        lines = []
        for line in file:
            lines.append(line.strip())
        return "<br>".join(lines)
        
    
    def get_jar_downloadurl(self):
        """do a reverse to get the urls for the given project/buildnumber for the direct download"""
        return reverse('get_buildfile',
                       args=(self.project.id,
                               self.build_number, 
                                os.path.basename(self.jar_file)))
        
    def get_jad_downloadurl(self):
        """do a reverse to get the urls for the given project/buildnumber for the direct download"""
        return reverse('get_buildfile', 
                       args=(self.project.id,
                               self.build_number, 
                                os.path.basename(self.jad_file)))
    
    def get_buildURL(self):
        """Hard coded build url for our build server"""
        return 'http://build.dimagi.com:250/viewLog.html?buildTypeId=bt%s&buildNumber=%s' % \
                (self.project.project_id, self.build_number)
    
    def set_jadfile(self, filename, filestream):
        """Simple utility function to save the uploaded file to the right location and set the property of the model"""        
        try:
            new_file_name = os.path.join(self._get_destination(), filename)
            fout = open(new_file_name, 'w')
            fout.write( filestream.read() )
            fout.close()
            self.jad_file = new_file_name 
        except Exception, e:
            logging.error("Error, saving jadfile failed", extra={"exception":e, "jad_filename":filename})
        

    def set_jarfile(self, filename, filestream):
        """Simple utility function to save the uploaded file to the right location and set the property of the model"""
        try:
            new_file_name = os.path.join(self._get_destination(), filename)
            fout = open(new_file_name, 'wb')
            fout.write( filestream.read() )
            fout.close()
            self.jar_file = new_file_name
        except Exception, e:
            logging.error("Error, saving jarfile failed", extra={"exception":e, "jar_filename":filename})
        
    
    def _get_destination(self):
        """The directory this build saves its data to.  Defined in
           the config and then /xforms/<project_id>/<build_id>/ is 
           appended.  If it doesn't exist, the directory is 
           created by this method."""
        destinationpath = os.path.join(BUILDFILES_PATH,
                                           str(self.project.id),
                                           str(self.build_number))
        if not os.path.exists(destinationpath):
            os.makedirs(destinationpath)        
        return destinationpath
    
    def validate_jar(self):
        '''Validates this build's jar file'''
        validate_jar(self.jarfile)
        
    def extract_and_link_xforms(self):
        '''Extracts all xforms from this build's jar and creates
           references on disk and model objects for them.'''
        xforms = extract_xforms(self.jar_file, self._get_destination())
        for form in xforms:
            form_model = BuildForm.objects.create(build=self, file_location=form)
        
        
    def release(self, user):
        '''Release a build, by setting its status as such.'''
        if self.status == "release":
            raise BuildError("Tried to release an already released build!")
        else:
            self.status = "release"
            self.released = datetime.now()
            self.released_by = user
            self.save()
      
class BuildForm(models.Model):
    """Class representing the location of a single build's xform on
       the file system."""
    
    build = models.ForeignKey(ProjectBuild, related_name="xforms")
    file_location = models.FilePathField(_('Xform Location'), 
                                         recursive=True, 
                                         path=BUILDFILES_PATH, 
                                         max_length=255)
    
    def get_file_name(self):
        '''Get a readable file name for this xform'''
        return os.path.basename(self.file_location)
    
    def __unicode__(self):
        return "%s: %s" % (self.build, self.get_file_name())
    
  
BUILD_FILE_TYPE = (    
    ('jad', '.jad file'),    
    ('jar', '.jar file'),   
)

class BuildDownload(models.Model):    
    """Represents an instance of a download of a build file.  Included are the
       type of file, the build id, and the request log.""" 

    type = models.CharField(max_length=3, choices=BUILD_FILE_TYPE)
    build = models.ForeignKey(ProjectBuild, related_name="downloads")
    log = models.ForeignKey(RequestLog, unique=True)
    
    def __unicode__(self):
        return "%s download for build %s.  Request: %s" %\
                (self.type, self.build, self.log)
     