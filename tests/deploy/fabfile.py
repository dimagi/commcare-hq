import os, sys
import uuid

from fabric.api import *
from fabric.contrib import files, console
from fabric import utils
from fabric.decorators import hosts

# globals
#config.project_name = 'project_name'
env.virtualenv_name = 'fab_' + uuid.uuid1().hex
env.project_name = 'testproject'

virtualenv_source = "source /usr/local/bin/virtualenvwrapper.sh"
virtualenv_workon = 'workon %s' % env.virtualenv_name

def _setup_path():    
    env.cwd = os.path.dirname(__file__)
    env.project_root = os.path.join(env.cwd, '..','testproject') #the django testproject root directory   
    env.src_root = os.path.join(env.cwd, '..','..') 
    #env.settings = '%(project_name)s.settings_%(environment)s' % env

def django_tests():
    """Run django tests"""
    cd_project = "cd " + env.project_root
    django_test_cmd = 'python manage.py test'
    
    with cd(env.project_root):    
        run("%s && %s && %s" % (virtualenv_source, virtualenv_workon, django_test_cmd))    

def selenium_tests():
    #setup selenium 
    #create vnc shell?
    #fire up selenium server
    #run selenium tests
    pass
    
def bootstrap():
    """ initialize remote host environment (virtualenv, deploy, update) """    
    #require('root', provided_by=('staging', 'production'))
    #run('mkdir -p %(root)s' % env)
    #run('mkdir -p %s' % os.path.join(env.home, 'www', 'log'))    
    _setup_path()    
    #install_requirements() #install it on local machine    
    create_virtualenv()    
    django_tests()
    clear_virtualenv()

def create_virtualenv():
    """ setup virtualenv on remote host """    
    make_env_cmd = 'mkvirtualenv %s' % env.virtualenv_name # --no-site-packages times out    
    #local("%s;%s" % (virtualenv_source, make_env_cmd), capture=False)
    run("%s && %s" % (virtualenv_source, make_env_cmd))
    
    
def clear_virtualenv():
    remove_command = "rmvirtualenv %s" % env.virtualenv_name
    deactivate = "deactivate"
    run("%s && %s && %s" % (virtualenv_source, deactivate, remove_command))
    

def install_requirements():
    pip_command = 'pip install -U -r requirements.txt'    
    
    with cd(env.src_root):
        #run("%s && %s && %s" % (virtualenv_source, virtualenv_workon, pip_command))                
        run(pip_command)