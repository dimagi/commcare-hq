import os
from datetime import datetime

from hq.tests.util import create_user_and_domain
from buildmanager.models import Project, ProjectBuild

def setup_build_objects(jar_file_name="dummy.jar", jad_file_name="dummy.jad",
                        build_number=1, status="release"):
    '''A little utility to setup a domain, user, project and build for 
       future tests.  Lets you specify a jar you want to use, and 
       defaults to dummy versions'''
    user, domain = create_user_and_domain() 
    project = Project.objects.create(domain=domain, name="Project", 
                                     description="Project Description")
    build = create_build(user, domain, project, status, jar_file_name, jad_file_name, build_number)
    return (user, domain, project, build)


def create_build(user, domain, project, status="release", 
                 jar_file_name="dummy.jar", jad_file_name="dummy.jad",
                 build_number=1): 
                 
    path = os.path.dirname(__file__)
    path_to_data = os.path.join(path, "data")
    jarfile = os.path.join(path_to_data , jar_file_name)
    jadfile = os.path.join(path_to_data , jad_file_name)
    build = ProjectBuild(project=project, 
                         build_number=build_number, 
                         status=status,
                         package_created=datetime.now(),
                         uploaded_by = user,
                         jar_file=jarfile,
                         jad_file=jadfile)
    build.save()
    return build