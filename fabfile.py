from fabric.api import *
from fabric.contrib import console, files
from fabric import utils
import os

# these defaults can be overridden if necessary
env.code_repo = 'git://github.com/dimagi/commcare-hq.git'
env.jython_home = "/usr/bin/jython"
env.restart_server = True
env.service_manager = "upstart"

def _join(*args):
    """
    We're deploying on Linux, so hard-code that path separator here.
    """
    return '/'.join(args)

def production():
    """ use production environment on remote host"""
    env.root = root = '/opt/www.commcarehq.org_project'
    env.virtualenv_root = _join(root, 'env/cchq_www')
    env.code_root       = _join(root, 'src/commcare-hq')
    env.pre_code_root   = _join(root, 'src/_commcare-hq')
    env.log_root   = _join(root, 'log')
    env.code_branch = 'master'
    env.sudo_user = 'cchqwww'
    env.hosts = ['10.84.168.241']
    env.environment = 'production'
    env.user = prompt("Username: ", default=env.user)
    env.make_bootstrap_command = 'python manage.py make_bootstrap direct-lessc'

def migration():
    """pull from staging branch into production to do a data migration"""
    production()
    env.code_branch = 'staging'
    env.restart_server = False

def staging():
    """ use staging environment on remote host"""
    env.root = root = '/home/dimagivm/'
    env.virtualenv_root = _join(root, 'cchq')
    env.code_root       = _join(root, 'commcare-hq')
    env.log_root   = _join(root, 'log')
    env.code_branch = 'staging'
    env.sudo_user = 'root'
    env.hosts = ['192.168.7.223']
    env.environment = 'staging'
    env.user = prompt("Username: ", default='dimagivm')
    env.make_bootstrap_command = 'python manage.py make_bootstrap direct-lessc'

def india():
    """Our production server in India."""
    env.root = root = '/home/commcarehq'
    env.virtualenv_root = _join(root, '.virtualenvs/commcarehq')
    env.code_root       = _join(root, 'src/commcare-hq')
    env.pre_code_root   = _join(root, 'src/_commcare-hq')
    env.log_root   = _join(root, 'log')
    env.code_branch = 'master'
    env.sudo_user = 'commcarehq'
    env.hosts = ['220.226.209.82']
    env.environment = 'india'
    env.user = prompt("Username: ", default=env.user)
    env.service_manager = "supervisor"
    env.make_bootstrap_command = 'python manage.py make_bootstrap'

def enter_virtualenv():
    """
    modify path to use virtualenv's python

    usage:

        with enter_virtualenv():
            run('python script.py')

    """
    return prefix('PATH=%(virtualenv_root)s/bin/:$PATH' % env)

def preindex_views():
    with cd(env.pre_code_root):
        update_code()
        with enter_virtualenv():
            sudo('nohup python manage.py sync_prepare_couchdb > preindex_views.out 2> preindex_views.err', user=env.sudo_user)

def update_code():
    sudo('git pull origin master', user=env.sudo_user)
    sudo('git checkout %(code_branch)s' % env, user=env.sudo_user)
    sudo('git pull', user=env.sudo_user)
    sudo('git submodule sync', user=env.sudo_user)
    sudo('git submodule update --init --recursive', user=env.sudo_user)

def upload_upstart_conf():
    """
    Upload and link upstart configuration from the templates.
    """
    require('root', provided_by=('staging', 'production', 'india'))
    template_dir = os.path.join(os.path.dirname(__file__), 'utilities', 'deployment', 'upstart_templates')
    for file in os.listdir(template_dir):
        destination = _join(env.code_root, 'utilities', 'deployment', file)
        template = os.path.join(template_dir, file)
        tmp_destination = "/tmp/%s.tmp" % file
        files.upload_template(template, tmp_destination, context=env)
        sudo('chown -R %(user)s:%(user)s %(file)s' % {"user": env.sudo_user,
                                                      "file": tmp_destination})
        sudo('chmod -R g+w %s' % tmp_destination)
        sudo('mv -f %s %s' % (tmp_destination, destination), user=env.sudo_user)
    
def _supervisor_command(command):
    require('root', provided_by=('staging', 'production', 'india'))
    sudo('supervisorctl %s' % command)
    
def upload_supervisor_conf():
    """
    Upload and link supervisor configuration from the templates.
    """
    require('root', provided_by=('staging', 'production', 'india'))
    file = os.path.join(os.path.dirname(__file__), 'utilities', 'deployment', 'supervisor_templates', "supervisor.conf")
    destination = _join(env.code_root, 'utilities', 'deployment', "supervisor.conf")
    #destination = _join(env.code_root, file)
    tmp_destination = "/tmp/supervisor.conf.tmp"
    files.upload_template(file, tmp_destination, context=env)
    sudo('chown -R %(user)s:%(user)s %(file)s' % {"user": env.sudo_user,
                                                  "file": tmp_destination})
    sudo('chmod -R g+w %s' % tmp_destination)
    sudo('mv -f %s %s' % (tmp_destination, destination), user=env.sudo_user)

def update_env():
    require('root', provided_by=('staging', 'production', 'india'))
    with enter_virtualenv():
        sudo('pip install -r requirements.txt', user=env.sudo_user)
        sudo(env.make_bootstrap_command, user=env.sudo_user)
        sudo('python manage.py sync_finish_couchdb', user=env.sudo_user)
        sudo('python manage.py syncdb --noinput', user=env.sudo_user)
        sudo('python manage.py migrate --noinput', user=env.sudo_user)
        sudo('python manage.py collectstatic --noinput', user=env.sudo_user)
        sudo('rm -f tmp.sh resource_versions.py; python manage.py printstatic > tmp.sh; bash tmp.sh > resource_versions.py', user=env.sudo_user)

def deploy():
    """ deploy code to remote host by checking out the latest via git """
    require('root', provided_by=('staging', 'production', 'india'))
    if env.environment in ('production', 'india'):
        if not console.confirm('Are you sure you want to deploy to {env.environment}? '.format(env=env), default=False) or\
           not console.confirm('Did you run "fab {env.environment} preindex_views"? '.format(env=env), default=False):
            utils.abort('Deployment aborted.')

    with cd(env.code_root):
        update_code()
        update_env()
        # remove all .pyc files in the project
        sudo("find . -name '*.pyc' -delete")
        
    if env.restart_server:
        service_restart()

    if env.post_deploy_url:
        sudo("curl %(post_deploy_url)s" % env)

def service_restart():
    """
    Restart cchq services on remote host.
    """
    require('service_manager', provided_by=('staging', 'production', 'india'))
    assert env.service_manager in ("upstart", "supervisor")
    
    if env.service_manager == "upstart":
        upload_upstart_conf()
        with settings(sudo_user="root"):
            sudo('stop cchq_www', user=env.sudo_user)
            sudo('initctl reload-configuration', user=env.sudo_user)
            sudo('start cchq_www', user=env.sudo_user)
    else:
        # for supervisor we update the templates each time
        upload_supervisor_conf()
        with settings(sudo_user="root"):
            sudo('supervisorctl update', user=env.sudo_user)
            sudo('supervisorctl restart all', user=env.sudo_user)

def service_stop():
    """
    stop cchq_www service on remote host.

    """
    require('root', provided_by=('staging', 'production'))
    with settings(sudo_user="root"):
        sudo('stop cchq_www', user=env.sudo_user)
