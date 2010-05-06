import os, sys
import logging
import traceback
from django.conf import settings
from datetime import datetime
import time

# make things easier so people don't have to install pygments
try:
    from pygments import highlight
    from pygments.lexers import HtmlLexer
    from pygments.formatters import HtmlFormatter
    pygments_found=True
except ImportError:
    pygments_found=False
    
from zipstream import ZipStream
try:
    from cStringIO import StringIO    
except:
    from StringIO import StringIO
    
    
from django.db import models
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse

from domain.models import Domain
from django.contrib.auth.models import User
from hq.utils import build_url
from requestlogger.models import RequestLog
from xformmanager.models import FormDefModel
from xformmanager.manager import XFormManager

from buildmanager import xformvalidator
from buildmanager.jar import validate_jar, extract_xforms
from buildmanager.exceptions import BuildError

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

UNKNOWN_IP = "0.0.0.0"

BUILD_STATUS = (    
    ('build', 'Standard Build'),    
    ('release', 'Release'),   
)


class ProjectBuild(models.Model):
    '''When a jad/jar is built, it should correspond to a unique ReleasePackage
       With all corresponding meta information on release info and build 
       information such that it can be traced back to a url/build info in source 
       control.'''    
    project = models.ForeignKey(Project, related_name="builds")
    
    uploaded_by = models.ForeignKey(User, related_name="builds_uploaded") 
    status = models.CharField(max_length=64, choices=BUILD_STATUS, default="build")
    
    build_number = models.PositiveIntegerField(help_text="the teamcity build number")
    
    revision_number = models.CharField(max_length=255, null=True, blank=True, 
                                       help_text="the source control revision number")
    
    version = models.CharField(max_length=20, null=True, blank=True,
                               help_text = 'the "release" version.  e.g. 2.0.1')
    
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
        return "%s build: %s. jad: %s, jar: %s" %\
                (self.project, self.build_number, self.jad_file, self.jar_file)
    
    def __str__(self):
        return unicode(self).encode('utf-8')

    def get_display_string(self):
        '''Like calling str() but with a url attached'''
        return "%s\nurl on server: %s" % (str(self),
                           build_url(reverse('show_build', 
                                             args=(self.id,)))) 
        
    def get_jar_download_count(self):
        return len(self.downloads.filter(type="jar"))
    
    def get_jad_download_count(self):
        return len(self.downloads.filter(type="jad"))
    
    @property
    def upload_information(self):
        '''Get the upload request information associated with this, 
           if it is present.'''
        try:
            return BuildUpload.objects.get(build=self).log
        except BuildUpload.DoesNotExist:
            return None
    
    def save(self):
        """Override save to provide some simple enforcement of uniqueness to the build numbers
        generated by the submission of the build"""        
        if ProjectBuild.objects.filter(project=self.project).filter(build_number=self.build_number).count() > 0 and self.id == None:
                raise Exception ("Error, the build number must be unique for this project build: " + str(self.build_number) + " project: " + str(self.project.id))
        else:            
            super(ProjectBuild, self).save()
    
    def get_jar_size(self):
        return os.path.getsize(self.jar_file)
    
    def get_jad_size(self):
        return os.path.getsize(self.jad_file)
    
    def get_jar_filename(self):
        '''Returns the name (no paths) of the jar file'''
        return os.path.basename(self.jar_file)
    
    def get_jad_filename(self):
        '''Returns the name (no paths) of the jad file'''
        return os.path.basename(self.jad_file)
    
    def get_zip_filename(self):
        '''Returns the name (no paths) of the zip file, which will include the version number infromation'''
        fname = os.path.basename(self.jar_file)
        basename = os.path.splitext(fname)[0]
        zipfilename = basename + "-build" + str(self.build_number) + ".zip"
        
        return zipfilename
    
    def get_jar_filestream(self):
        try:
            fin = open(self.jar_file,'r')
            return fin
        except Exception, e:
            logging.error("Unable to open jarfile", extra={"exception": e, 
                                                           "jar_file": self.jar_file, 
                                                           "build_number": self.build_number,
                                                           "project_id": self.project.id})
    
    def get_jad_filestream(self, mode='r'):        
        try:
            fin = open(self.jad_file, mode)
            return fin
        except Exception, e:
            logging.error("Unable to open jadfile", extra={"exception": e, 
                                                           "jad_file": self.jad_file, 
                                                           "build_number": self.build_number,
                                                           "project_id": self.project.id})
            
            
    def get_zip_filestream(self):
        try:
            zpath = str(os.path.dirname(self.jar_file) + "/")                        
            buf = StringIO()            
            zp = ZipStream(zpath)
            for data in zp:                                
                buf.write(data)
                #print data
            buf.flush()
            buf.seek(0)
            return buf.read()
        except Exception, e:            
            logging.error("Unable to open create ZipStream", extra={"exception": e,                                                           
                                                           "build_number": self.build_number,
                                                           "project_id": self.project.id})
    def get_jad_contents(self):
        '''Returns the contents of the jad as text.'''
        file = self.get_jad_filestream()
        lines = []
        for line in file:
            lines.append(line.strip())
        return "<br>".join(lines)
    
    def get_jad_properties(self):
        '''Reads the properties of the jad file and returns a dict'''
        file = self.get_jad_filestream()
        sep = ': '
        proplines = [line.strip() for line in file.readlines() if line.strip()]
        
        jad_properties = {}
        for propln in proplines:
            i = propln.find(sep)
            if i == -1:
                pass #log error?
            (propname, propvalue) = (propln[:i], propln[i+len(sep):])
            jad_properties[propname] = propvalue
        return jad_properties
    
    def write_jad(self, properties):
        '''Write a property dictionary back to the jad file'''
        ordered = ['MIDlet-Name', 'MIDlet-Version', 'MIDlet-Vendor', 'MIDlet-Jar-URL', 
                   'MIDlet-Jar-Size', 'MIDlet-Info-URL', 'MIDlet-1']
        for po in ordered:
          if po not in properties.keys():
            pass #log error -- required property is missing?
        unordered = [propname for propname in properties.keys() if propname not in ordered]
      
        ordered.extend(sorted(unordered))
        proplines = ['%s: %s\n' % (propname, properties[propname]) for propname in ordered]
      
        file = self.get_jad_filestream('w')
        file.write(''.join(proplines))
        file.close()
    
    def add_jad_properties(self, propdict):
        '''Add properties to the jad file'''
        props = self.get_jad_properties()
        props.update(propdict)
        self.write_jad(props)
    
    def get_xform_html_summary(self):
        '''This is used by the view.  It is pretty cool, but perhaps misplaced.'''
        to_return = []
        for form in self.xforms.all():
            try:
                to_return.append(form.get_link())
            except Exception, e:
                # we don't care about this
                pass
        if to_return:
            return "<br>".join(to_return)
        else:
            return "No X-Forms found"
    
    def get_zip_downloadurl(self):
        """do a reverse to get the urls for the given project/buildnumber for the direct zipfile download"""
        
        return reverse('get_buildfile',
                       args=(self.project.id,
                               self.build_number, 
                                self.get_zip_filename()))
    
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
    
    def validate_jar(self, include_xforms=False):
        '''Validates this build's jar file.  By default, does NOT validate
           the jar's xforms.'''
        validate_jar(self.jar_file, include_xforms)
        
    def validate_xforms(self):
        '''Validates this build's xforms.'''
        errors = []
        for form in self.xforms.all():
            try:
                xformvalidator.validate(form.file_location)
            except Exception, e:
                errors.append(e)
        if errors:
            raise BuildError("Problem validating xforms for %s!" % self, errors)
        
        
    def check_and_release_xforms(self):
        '''Checks this build's xforms against the xformmanager and releases
           them, if they pass compatibility tests'''
        errors = []
        to_skip = []
        to_register = []
        for form in self.xforms.all():
            try:
                formdef = xformvalidator.validate(form.file_location)
                modelform = FormDefModel.get_model(formdef.target_namespace,
                                                   self.project.domain, 
                                                   formdef.version)
                if modelform:
                    # if the model form exists we must ensure it is compatible
                    # with the version we are trying to release
                    existing_formdef = modelform.to_formdef()
                    differences = existing_formdef.get_differences(formdef)
                    if differences.is_empty():
                        # this is all good
                        to_skip.append(form)
                    else:
                        raise BuildError("""Schema %s is not compatible with %s.  
                                            Because of the following differences: 
                                            %s
                                            You must update your version number!"""
                                         % (existing_formdef, formdef, differences))
                else:
                    # this must be registered
                    to_register.append(form)
            except Exception, e:
                errors.append(e)
        if errors:
            raise BuildError("Problem validating xforms for %s!" % self, errors)
        # finally register
        manager = XFormManager()
        # TODO: we need transaction management
        for form in to_register:
            try:
                formdefmodel = manager.add_schema(form.get_file_name(),
                                                  form.as_filestream(),
                                                  self.project.domain)
                
                upload_info = self.upload_information
                if upload_info:
                    formdefmodel.submit_ip = upload_info.ip
                    user = upload_info.user
                else:
                    formdefmodel.submit_ip = UNKNOWN_IP
                    user = self.uploaded_by
                formdefmodel.uploaded_by = user
                formdefmodel.bytes_received =  form.size
                formdefmodel.form_display_name = form.get_file_name()
                formdefmodel.save()                
            except Exception, e:
                # log the error with the stack, otherwise this is hard to track down
                info = sys.exc_info()
                logging.error("Error registering form in build manager: %s\n%s" % \
                              (e, traceback.print_tb(info[2])))
                errors.append(e)
        if errors:
            raise BuildError("Problem registering xforms for %s!" % self, errors)
        
    def set_jad_released(self):
        '''Set the appropriate 'release' properties in the jad'''
        self.add_jad_properties({
          'Build-Number': '*' + str(self.get_release_number()), #remove * once we get a real build number
          'Released-on': time.strftime('%Y-%b-%d %H:%M', time.gmtime())
        })
        
    #FIXME!
    def get_release_number(self):
        '''return an incrementing build number per released build, unique across all builds for a given commcare project'''
        import random
        return random.randint(1000, 9999) #return a high random number until we get the incrementing plugged in
        
    def release(self, user):
        '''Release a build.  This does a number of things:
           1. Validates the Jar.  The specifics of this are still in flux but at the very
              least it should be extractable, and there should be at least one xform.
           2. Ensures all the xforms have valid xmlns, version, and uiversion attributes
           3. Checks if xforms with the same xmlns and version are registered already
              If so: ensures the current forms are compatible with the registered forms
              If not: registers the forms
           4. Updates the build status to be released, sets the released and 
              released_by properties
           This method will raise an exception if, for any reason above, the build cannot
           be released.'''
        if self.status == "release":
            raise BuildError("Tried to release an already released build!")
        else:
            # TODO: we need transaction management.  Any of these steps can raise exceptions
            self.validate_jar()
            self.validate_xforms()
            self.check_and_release_xforms()
            self.set_jad_released()
            self.status = "release"
            self.released = datetime.now()
            self.released_by = user
            self.save()
            logging.error("%s just released build %s!  We just thought you might want to be keeping tabs..." %
                          (user, self.get_display_string()))
            
def extract_and_link_xforms(sender, instance, created, **kwargs): 
    '''Extracts all xforms from this build's jar and creates
           references on disk and model objects for them.'''
    # only do this the first time we save, not on updates
    if not created:
        return
    
    try:
        xforms = extract_xforms(instance.jar_file, instance._get_destination())
        for form in xforms:
            form_model = BuildForm.objects.create(build=instance, file_location=form)
        num_created = len(instance.xforms.all())
        if num_created == 0:
            logging.warn("Build %s didn't have any linked xforms!  Why not?!" % instance)
    except Exception, e:
        logging.error("Problem extracting xforms for build: %s, the error is: %s" %\
                      (instance, e))

post_save.connect(extract_and_link_xforms, sender=ProjectBuild)
    
      
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
    
    @property
    def size(self):
        return os.path.getsize(self.file_location)
    
    def get_url(self):
        '''Get the url where you can view this form'''
        return reverse('get_build_xform', args=(self.id,))
        
                       
    def as_filestream(self):
        '''Gets a raw handle to the form as a file stream'''
        try:
            fin = open(self.file_location,'r')
            return fin
        except Exception, e:
            logging.error("Unable to open xform: %s" % self, 
                          extra={"exception": e }) 

    def get_text(self):
        '''Gets the body of the xform, as text'''
        try:
            file = self.as_filestream()
            text = file.read()
            file.close()
            return text
        except Exception, e:
            logging.error("Unable to open xform: %s" % self, 
                          extra={"exception": e }) 

    def to_html(self):
        '''Gets the body of the xform, as pretty printed text'''
        raw_body = self.get_text()
        if pygments_found:
            return highlight(raw_body, HtmlLexer(), HtmlFormatter())
        return raw_body
        
    def get_link(self):
        '''A clickable html displayable version of this for use in templates'''
        return '<a href=%s target=_blank>%s</a>' % (self.get_url(), self.get_file_name())
    
    def __unicode__(self):
        return "%s: %s" % (self.build, self.get_file_name())
    
  
BUILD_FILE_TYPE = (    
    ('jad', '.jad file'),    
    ('jar', '.jar file'),   
)

class BuildUpload(models.Model):    
    """Represents an instance of the upload of a build."""
    build = models.ForeignKey(ProjectBuild, unique=True)
    log = models.ForeignKey(RequestLog, unique=True)
    

class BuildDownload(models.Model):    
    """Represents an instance of a download of a build file.  Included are the
       type of file, the build id, and the request log.""" 

    type = models.CharField(max_length=3, choices=BUILD_FILE_TYPE)
    build = models.ForeignKey(ProjectBuild, related_name="downloads")
    log = models.ForeignKey(RequestLog, unique=True)
    
    def __unicode__(self):
        return "%s download for build %s.  Request: %s" %\
                (self.type, self.build, self.log)
     