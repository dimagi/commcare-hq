import os
from datetime import datetime

from hq.tests.util import create_user_and_domain
from buildmanager.models import Project, ProjectBuild

def setup_build_objects(jar_file_name="dummy.jar", jad_file_name="dummy.jad"):
    '''A little utility to setup a domain, user, project and build for 
       future tests.  Lets you specify a jar you want to use, and 
       defaults to dummy versions'''
    user, domain = create_user_and_domain() 
    project = Project.objects.create(domain=domain, name="Project", 
                                     description="Project Description")
    path = os.path.dirname(__file__)
    path_to_data = os.path.join(path, "data")
    jarfile = os.path.join(path_to_data , jar_file_name)
    jadfile = os.path.join(path_to_data , jad_file_name)
    build = ProjectBuild(project=project, 
                         build_number=1, 
                         status="release",
                         package_created=datetime.now(),
                         uploaded_by = user,
                         jar_file=jarfile,
                         jad_file=jadfile)
    build.save()
    return (user, domain, project, build)