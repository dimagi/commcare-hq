"""
Server layout:
    ~/services/
        This contains two subfolders
            /apache/
            /supervisor/
        which hold the configurations for these applications
        for each environment (staging, demo, etc) running on the server.
        Theses folders are included in the global /etc/apache2 and
        /etc/supervisor configurations.

    ~/www/
        This folder contains the code, python environment, and logs
        for each environment (staging, demo, etc) running on the server.
        Each environment has its own subfolder named for its evironment
        (i.e. ~/www/staging/logs and ~/www/demo/logs).
"""
import pdb
import uuid
from fabric.context_managers import settings, cd
from fabric.operations import require, local

import os, sys

from fabric.api import run, roles, execute, task, sudo, env
from fabric.contrib import files, console
from fabric import utils
import posixpath
from collections import defaultdict


PROJECT_ROOT = os.path.dirname(__file__)
RSYNC_EXCLUDE = (
    '.DS_Store',
    '.git',
    '*.pyc',
    '*.example',
    '*.db',
    )
env.project = 'commcare-hq'
env.code_repo = 'git://github.com/dimagi/commcare-hq.git'
env.home = "/home/cchq"


env.roledefs = {
        'couch': [],
        'pg': [],
        'rabbitmq': [],
        'django_celery': [],
        'django_app': [],
        'formsplayer': [],
        'lb': [],
        'staticfiles': [],
    }

@task
def _setup_path():
    # using posixpath to ensure unix style slashes. See bug-ticket: http://code.fabfile.org/attachments/61/posixpath.patch
    env.root = posixpath.join(env.home, 'www', env.environment)
    env.log_dir = posixpath.join(env.home, 'www', env.environment, 'log')
    env.code_root = posixpath.join(env.root, 'code_root')
    env.project_root = posixpath.join(env.code_root, env.project)
    env.project_media = posixpath.join(env.code_root, 'media')
    env.virtualenv_root = posixpath.join(env.root, 'python_env')
    env.services = posixpath.join(env.home, 'services')

@task
def _set_apache_user():
    if what_os() == 'ubuntu':
        env.apache_user = 'www-data'
    elif what_os() == 'redhat':
        env.apache_user = 'apache'

@roles('lb')
def setup_apache_dirs():
    sudo('mkdir -p %(services)s/apache' % env, user=env.sudo_user)

@roles('django_celery', 'django_app')
def setup_dirs():
    """ create (if necessary) and make writable uploaded media, log, etc. directories """
    run('mkdir -p %(log_dir)s' % env)
    run('chmod a+w %(log_dir)s' % env)
    run('mkdir -p %(services)s/supervisor' % env)
    #execute(setup_apache_dirs)

@task
def staging():
    """ use staging environment on remote host"""
    env.code_branch = 'develop'
    env.sudo_user = 'commcare-hq'
    env.environment = 'staging'
    env.server_port = '9002'
    env.server_name = 'noneset'
    env.hosts = ['192.168.56.1']
    env.settings = '%(project)s.localsettings' % env
    env.host_os_map = None
    env.db = '%s_%s' % (env.project, env.environment)
    _setup_path()
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
    env.hosts = ['220.226.209.83']
    env.environment = 'india'
    env.user = prompt("Username: ", default=env.user)
    env.service_manager = "supervisor"
    env.make_bootstrap_command = 'python manage.py make_bootstrap'


@task
def production():
    """ use production environment on remote host"""
    env.code_branch = 'newprod'
    env.sudo_user = 'cchq'
    env.environment = 'production'
    env.server_port = '9010'

    #env.hosts = []
    env.roledefs = {
        'couch': ['hqdb.internal.commcarehq.org'],
        'pg': ['hqdb.internal.commcarehq.org'],
        'rabbitmq': ['hqdb.internal.commcarehq.org'],
        #'sofabed': ['hqdb.internal.commcarehq.org'], #todo, right now group it with celery
        'django_celery': ['hqdb.internal.commcarehq.org'],
        'django_app': ['hqdjango1.internal.commcarehq.org', 'hqdjango0.internal.commcarehq.org'],
        'formsplayer': ['hqdjango0.internal.commcarehq.org'],
        'lb': [], #todo on apache level config
        'staticfiles': ['hqproxy0.internal.commcarehq.org'],
    }

    if env.roles == []:
        env.roles = env.roledefs.keys()
        #if the command line is set for the role in question, do nothing
    env.server_name = 'commcare-hq-production'
    env.settings = '%(project)s.localsettings' % env
    env.host_os_map = None # e.g. 'ubuntu' or 'redhat'.  Gets autopopulated by what_os() if you don't know what it is or don't want to specify.
    env.db = '%s_%s' % (env.project, env.environment)


    env.jython_home = '/usr/local/lib/jython'
    _setup_path()



@task
def install_packages():
    """Install packages, given a list of package names"""
    require('environment', provided_by=('staging', 'production'))
    packages_list = ''
    installer_command = ''
    if what_os() == 'ubuntu':
        packages_list = 'apt-packages.txt'
        installer_command = 'apt-get install -y'
    elif what_os() == 'redhat':
        packages_list = 'yum-packages.txt'
        installer_command = 'yum install -y'
        return
    packages_file = posixpath.join(PROJECT_ROOT, 'requirements', packages_list)
    with open(packages_file) as f:
        packages = f.readlines()
    sudo("%s %s" % (installer_command, " ".join(map(lambda x: x.strip('\n\r'), packages))))


@task
def upgrade_packages():
    """
    Bring all the installed packages up to date.
    This is a bad idea in RedHat as it can lead to an
    OS Upgrade (e.g RHEL 5.1 to RHEL 6).
    Should be avoided.  Run install packages instead.
    """
    require('environment', provided_by=('staging', 'production'))
    if what_os() == 'ubuntu':
        sudo("apt-get update -y")
        sudo("apt-get upgrade -y")
    else:
        return #disabled for RedHat (see docstring)

@task
def what_os():
    with settings(warn_only=True):
        require('environment', provided_by=('staging','production'))
        if env.host_os_map is None:
            #prior use case of setting a env.remote_os did not work when doing multiple hosts with different os! Need to keep state per host!
            env.host_os_map = defaultdict(lambda: '')
        if env.host_os_map[env.host_string] == '':
            print 'Testing operating system type...'
            if(files.exists('/etc/lsb-release',verbose=True) and files.contains(text='DISTRIB_ID=Ubuntu', filename='/etc/lsb-release')):
                remote_os = 'ubuntu'
                print 'Found lsb-release and contains "DISTRIB_ID=Ubuntu", this is an Ubuntu System.'
            elif(files.exists('/etc/redhat-release',verbose=True)):
                remote_os = 'redhat'
                print 'Found /etc/redhat-release, this is a RedHat system.'
            else:
                print 'System OS not recognized! Aborting.'
                exit()
            env.host_os_map[env.host_string] = remote_os
        return env.host_os_map[env.host_string]

@roles('pg','django_celery','django_app')
@task
def setup_server():
    """Set up a server for the first time in preparation for deployments."""
    require('environment', provided_by=('staging', 'production'))
    # Install required system packages for deployment, plus some extras
    # Install pip, and use it to install virtualenv
    install_packages()
    sudo("easy_install -U pip", user=env.sudo_user)
    sudo("pip install -U virtualenv", user=env.sudo_user)
    upgrade_packages()
    execute(create_db_user)
    execute(create_db)


@roles('pg')
def create_db_user():
    """Create the Postgres user."""
    require('environment', provided_by=('staging', 'production'))
    sudo('createuser -D -A -R %(sudo_user)s' % env, user='postgres')


@roles('pg')
def create_db():
    """Create the Postgres database."""
    require('environment', provided_by=('staging', 'production'))
    sudo('createdb -O %(sudo_user)s %(db)s' % env, user='postgres')


@task
def bootstrap():
    """Initialize remote host environment (virtualenv, deploy, update) """
    require('root', provided_by=('staging', 'production'))
    run('mkdir -p %(root)s' % env, shell=False)
    execute(clone_repo)
    execute(update_code)
    execute(create_virtualenv)
    execute(update_requirements)
    execute(setup_dirs)
    execute(update_services)
    execute(fix_locale_perms)


@roles('django_celery', 'django_app')
def create_virtualenv():
    """ setup virtualenv on remote host """
    require('virtualenv_root', provided_by=('staging', 'production'))
    with settings(warn_only=True):
        run('rm -rf %(virtualenv_root)s' % env)
    args = '--clear --distribute --no-site-packages'
    run('virtualenv %s %s' % (args, env.virtualenv_root))


@roles('django_celery', 'django_app')
def clone_repo():
    """ clone a new copy of the git repository """
    with settings(warn_only=True):
        with cd(env.root):
            if not files.exists(env.code_root):
                run('git clone %(code_repo)s %(code_root)s' % env)
            with cd(env.code_root):
                run('git submodule init')


@roles('django_celery','django_app', 'staticfiles')
@task
def update_code():
    with cd(env.code_root):
	run('git pull')
        run('git checkout %(code_branch)s' % env)
        run('git submodule sync')
        run('git submodule update --init --recursive')

@roles('django_celery','django_app', 'staticfiles')
@task
def deploy():
    """ deploy code to remote host by checking out the latest via git """
    require('root', provided_by=('staging', 'production'))
    run('echo ping!') #hack/workaround for delayed console response
    if env.environment == 'production':
        if not console.confirm('Are you sure you want to deploy production?', default=False): utils.abort('Production deployment aborted.')
    with settings(warn_only=True):
        execute(services_stop)
    try:
        execute(update_code)
        execute(update_services)
        execute(migrate)
        execute(collectstatic)
        #execute(touch_apache)
    finally:
        # hopefully bring the server back to life if anything goes wrong
        execute(services_stop)
        execute(services_start)


@task
@roles('django_celery', 'django_app','staticfiles')
def update_requirements():
    """ update external dependencies on remote host """
    require('code_root', provided_by=('staging', 'production'))
    update_code()
    requirements = posixpath.join(env.code_root, 'requirements')
    #with cd(requirements):
    with cd(env.code_root):
        cmd = ['%(virtualenv_root)s/bin/pip install -U ' % env]
        cmd += ['--requirement %s' % posixpath.join(requirements, 'prod-requirements.txt')]
        cmd += ['--requirement %s' % posixpath.join(requirements, 'requirements.txt')]
        print ' '.join(cmd)
        run(' '.join(cmd), shell=False, pty=False)


@roles('lb')
def touch_apache():
    """ touch apache and supervisor conf files to trigger reload. Also calls supervisorctl update to load latest supervisor.conf """
    require('code_root', provided_by=('staging', 'production'))
    apache_path = posixpath.join(posixpath.join(env.services, 'apache'), 'apache.conf')
    sudo('touch %s' % apache_path, user=env.sudo_user)



@roles('django_celery', 'django_app','staticfiles')
def touch_supervisor():
    """ touch apache and supervisor conf files to trigger reload. Also calls supervisorctl update to load latest supervisor.conf """
    require('code_root', provided_by=('staging', 'production'))
    supervisor_path = posixpath.join(posixpath.join(env.services, 'supervisor'), 'supervisor.conf')
    sudo('touch %s' % supervisor_path, user=env.sudo_user)
    _supervisor_command('update')


@roles('django_celery', 'django_app', 'formsplayer')
@task
def update_services():
    """ upload changes to services such as nginx """
    with settings(warn_only=True):
        execute(services_stop)
    #remove old confs from directory first
    services_dir =  posixpath.join(env.services, u'supervisor', 'supervisor_*.conf')
    run('rm -f %s' % services_dir)
    execute(upload_and_set_supervisor_config)
    execute(services_start)
    netstat_plnt()

@roles('lb')
def configtest():
    """ test Apache configuration """
    require('root', provided_by=('staging', 'production'))
    run('apache2ctl configtest')

@roles('lb')
def apache_reload():
    """ reload Apache on remote host """
    require('root', provided_by=('staging', 'production'))
    if what_os() == 'redhat':
        sudo('/etc/init.d/httpd reload')
    elif what_os() == 'ubuntu':
        sudo('/etc/init.d/apache2 reload')


@roles('lb')
def apache_restart():
    """ restart Apache on remote host """
    require('root', provided_by=('staging', 'production'))
    sudo('/etc/init.d/apache2 restart')

@task
def netstat_plnt():
    """ run netstat -plnt on a remote host """
    require('hosts', provided_by=('production', 'staging'))
    sudo('netstat -plnt')

@roles('django_app', 'django_celery')
def services_start():
    ''' Start the gunicorn servers '''
    require('environment', provided_by=('staging', 'demo', 'production'))
    _supervisor_command('update')
    _supervisor_command('start  %(project)s-%(environment)s*' % env)

@roles('django_app', 'django_celery')
def services_stop():
    ''' Stop the gunicorn servers '''
    require('environment', provided_by=('staging', 'demo', 'production'))
    _supervisor_command('stop  %(project)s-%(environment)s*' % env)

@roles('django_app', 'django_celery')
def services_restart():
    ''' Start the gunicorn servers '''
    require('environment', provided_by=('staging', 'demo', 'production'))
    _supervisor_command('restart  %(project)s-%(environment)s:%(project)s-%(environment)s-server' % env)

@roles('django_app')
def migrate():
    """ run south migration on remote environment """
    require('code_root', provided_by=('production', 'demo', 'staging'))
    with cd(env.code_root):
        run('%(virtualenv_root)s/bin/python manage.py syncdb --noinput' % env)
        run('%(virtualenv_root)s/bin/python manage.py migrate --noinput' % env)


@roles('staticfiles',)
@task
def collectstatic():
    """ run collectstatic on remote environment """
    require('code_root', provided_by=('production', 'demo', 'staging'))
    update_code() #not wrapped in execute because we only want the staticfiles machine to run it
    with cd(env.code_root):
        run('%(virtualenv_root)s/bin/python manage.py make_bootstrap' % env)
        run('%(virtualenv_root)s/bin/python manage.py collectstatic --noinput' % env)

@task
def reset_local_db():
    """ Reset local database from remote host """
    require('code_root', provided_by=('production', 'staging'))
    if env.environment == 'production':
        utils.abort('Local DB reset is for staging environment only')
    question = 'Are you sure you want to reset your local '\
               'database with the %(environment)s database?' % env
    sys.path.append('.')
    if not console.confirm(question, default=False):
        utils.abort('Local database reset aborted.')
    local_db = loc['default']['NAME']
    remote_db = remote['default']['NAME']
    with settings(warn_only=True):
        local('dropdb %s' % local_db)
    local('createdb %s' % local_db)
    host = '%s@%s' % (env.user, env.hosts[0])
    local('ssh -C %s sudo -u commcare-hq pg_dump -Ox %s | psql %s' % (host, remote_db, local_db))
@task
def fix_locale_perms():
    """ Fix the permissions on the locale directory """
    require('root', provided_by=('staging', 'production'))
    _set_apache_user()
    locale_dir = '%s/commcare-hq/locale/' % env.code_root
    run('chown -R %s %s' % (env.sudo_user, locale_dir))
    sudo('chgrp -R %s %s' % (env.apache_user, locale_dir), user='root')
    run('chmod -R g+w %s' % (locale_dir))

@task
def commit_locale_changes():
    """ Commit locale changes on the remote server and pull them in locally """
    fix_locale_perms()
    with cd(env.code_root):
        run('-H -u %s git add commcare-hq/locale' % env.sudo_user)
        run('-H -u %s git commit -m "updating translation"' % env.sudo_user)
    local('git pull ssh://%s%s' % (env.host, env.code_root))

def _upload_supervisor_conf_file(filename):
    upload_dict = {}
    upload_dict["template"] = posixpath.join(os.path.dirname(__file__), 'services', 'templates', filename)
    upload_dict["destination"] = '/var/tmp/%s.blah' % filename
    upload_dict["enabled"] =  posixpath.join(env.services, u'supervisor/%s' % filename)
    upload_dict["main_supervisor_conf_dir"] = '/etc'

    files.upload_template(upload_dict["template"], upload_dict["destination"], context=env, use_sudo=True)
    sudo('chown -R %s %s' % (env.sudo_user, upload_dict["destination"]))
    #sudo('chgrp -R %s %s' % (env.apache_user, upload_dict["destination"]))
    sudo('chmod -R g+w %(destination)s' % upload_dict)
    sudo('mv -f %(destination)s %(enabled)s' % upload_dict)

@roles('django_celery')
def upload_celery_supervisorconf():
    _upload_supervisor_conf_file('supervisor_celery.conf')

@roles('django_celery')
def upload_sofabed_supervisorconf():
    _upload_supervisor_conf_file('supervisor_sofabed.conf')

@roles('django_app')
def upload_djangoapp_supervisorconf():
    _upload_supervisor_conf_file('supervisor_django.conf')

@roles('formsplayer')
def upload_formsplayer_supervisorconf():
    _upload_supervisor_conf_file('supervisor_formsplayer.conf')

def upload_and_set_supervisor_config():
    """Upload and link Supervisor configuration from the template."""
    require('environment', provided_by=('staging', 'demo', 'production'))
    _set_apache_user()
    execute(upload_celery_supervisorconf)
    execute(upload_sofabed_supervisorconf)
    execute(upload_djangoapp_supervisorconf)
    execute(upload_formsplayer_supervisorconf)

    #regenerate a brand new supervisor conf file from scratch.
    #Set the line in the supervisord config file that points to our project's supervisor directory with conf files
    replace_dict = {}
    replace_dict["main_supervisor_conf_dir"] = '/etc'
    replace_dict["tmp"] = posixpath.join('/','var','tmp', "supervisord_%s.tmp" % uuid.uuid4().hex)

    #create brand new one
    sudo("echo_supervisord_conf > %(tmp)s" % replace_dict)
    files.uncomment(replace_dict['tmp'], "^;\[include\]", use_sudo=True, char=';')
    files.sed(replace_dict["tmp"], ";files = relative/directory/\*\.ini", "files = %s/supervisor/*.conf" % env.services, use_sudo=True)
    #sudo('mv -f %(tmp)s %(main_supervisor_conf_dir)s/supervisord.conf' % replace_dict)
    sudo('cp -f %(tmp)s %(main_supervisor_conf_dir)s/supervisord.conf' % replace_dict)
    _supervisor_command('update')

@roles('lb')
def upload_apache_conf():
    """Upload and link Supervisor configuration from the template."""
    require('environment', provided_by=('staging', 'demo', 'production'))
    _set_apache_user()
    template = posixpath.join(os.path.dirname(__file__), 'services', 'templates', 'apache.conf')
    destination = '/var/tmp/apache.conf.temp'
    files.upload_template(template, destination, context=env, use_sudo=True)
    enabled =  posixpath.join(env.services, u'apache/%(environment)s.conf' % env)
    sudo('chown -R %s %s' % (env.sudo_user, destination))
    sudo('chgrp -R %s %s' % (env.apache_user, destination))
    sudo('chmod -R g+w %s' % destination)
    sudo('mv -f %s %s' % (destination, enabled))
    if what_os() == 'ubuntu':
        sudo('a2enmod proxy')  #loaded by default in redhat
        sudo('a2enmod proxy_http') #loaded by default in redhat

    sites_enabled_dirfile = ''
    if what_os() == 'ubuntu':
        sites_enabled_dirfile = '/etc/apache2/sites-enabled/%(project)s.conf' % env
    elif what_os() == 'redhat':
        sites_enabled_dirfile = '/etc/httpd/conf.d/%(project)s.conf' % env
    with settings(warn_only=True):
        if files.exists(sites_enabled_dirfile):
            sudo('rm %s' % sites_enabled_dirfile)

    sudo('ln -s %s/apache/%s.conf %s' % (env.services, env.environment, sites_enabled_dirfile))
    apache_reload()

@roles('django_celery', 'django_app')
def _supervisor_command(command):
    require('hosts', provided_by=('staging', 'production'))
    if what_os() == 'redhat':
        cmd_exec = "/usr/bin/supervisorctl"
    elif what_os() == 'ubuntu':
        cmd_exec = "/usr/local/bin/supervisorctl"
    run('sudo %s %s' % (cmd_exec, command))
