#todo
#zip up the files (duh)
#scp it to the remote machine
#ssh to remote machine
#blow away old location
#unzip and redeploy it over there
#drop in the build number and revision number?

#get username, password, hostname, location from environmental variables

import os
import sys
import tarfile
import gzip
import logging
import sys
import os
import select
import shutil
try:
    import paramiko
except:
    #commenting out this log because we don't actually use it and it's confusing to see on the build server.
    pass
    #logging.error("Paramiko not installed - you need it for remote ssh deployment")
import socket

import subprocess
from subprocess import PIPE

debug = True

hostport = 22

def make_archive(path, target_filename):
    """for a given path, generate the tarball for distribution"""
    print "Making archive %s : %s" % (path, target_filename)    
    tar = tarfile.open(target_filename, "w:gz")
    tar.add(path)
    tar.close()
    print "archive created successfully"

def run(t, cmd):
    'Open channel on transport, run command, capture output and return'
    global debug
    out = ''

    if debug: print 'DEBUG: Running cmd:', cmd
    chan = t.open_session()
    chan.setblocking(1)   

    try:
        chan.exec_command(cmd)
    except SSHException:
        print "Error running remote command, yo", SSHException        
        sys.exit(1)

    ### Read when data is available
    while True:
        r,w,e = select.select([chan,], [], [])
        if chan in r:
            try:
                x = chan.recv(1024)
                if len(x) == 0:
                    print "EOF"
                    break;
                out += x
            except socket.timeout:
                pass

    if debug: print 'DEBUG: cmd results:', out
    chan.close()
    return out


def do_local_deploy(target_abs_path, target_deploy_path, build_number, revision_number):
    #make the archive    
    #git revision numbers are nasty looking: b9cfdebe87d6-05/27/2009 16:03:43, so let's escape them    
    revision_number = revision_number.replace(' ', '_')
    revision_number = revision_number.replace(':', '')
    revision_number = revision_number.replace('/', '-')
    
    #chdir to where this deploy is    
    os.chdir(os.path.dirname(os.path.abspath(__file__)))    
    #create the archive in the root directory where both rapidsms and commcarehq reside
    archive_to_deploy = os.path.join('../../../','deploy-rev%s.tar.gz' % (revision_number))
    
    #get the basedir that these reside in.  this could be arbitrary
    basedir = os.path.basename(os.path.abspath('../../')) #49120312421 or commcare-/hq   
    curdir = os.getcwd()
    
    #go down to that level to actual make archive
    print "cwd: " + os.getcwd()
    os.chdir('../../../')
    print "archive to deploy: " + archive_to_deploy    
    print "cwd: " + os.getcwd()
    
    
    make_archive(basedir,os.path.basename(archive_to_deploy))
    
    print "chdir back to original directory"
    os.chdir(curdir)
    print "cwd: " + os.getcwd()
    
    archive_filename = os.path.basename(archive_to_deploy)
    print "*************************"
    print "Finished archiving.  Transporting file: " + archive_filename + " to: " + target_abs_path    

    shutil.move(archive_to_deploy, target_abs_path + archive_filename)
    
    p = subprocess.Popen(['/var/django-sites/builds/rsdeploy.sh', 'deploy-rev%s' % (revision_number), basedir, target_deploy_path], shell=False, stdout=subprocess.PIPE,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        
    p.stdin.flush()
    p.stdin.close()
    
    output = p.stdout.read()    
    error = p.stderr.read()  
    
    print "Command output: " + output
    print "Command Errors: " + error
    


def do_deploy(hostname, username, password, target_abs_path, target_deploy_path, build_number, revision_number):
   
    #we are starting in commcare-hq/utilities/build because we are operating off of the build.xml
    #make the archive    
    #git revision numbers are nasty looking: b9cfdebe87d6-05/27/2009 16:03:43, so let's escape them    
    revision_number = revision_number.replace(' ', '_')
    revision_number = revision_number.replace(':', '')
    revision_number = revision_number.replace('/', '-')
    
    os.chdir(os.path.dirname(os.path.abspath(__file__)))    
    #create the archive in the root directory where both rapidsms and commcarehq reside
    archive_to_deploy = os.path.join('../../../','deploy-rev%s.tar.gz' % (revision_number))
    
    #get the basedir that these reside in.  this could be arbitrary
    basedir = os.path.basename(os.path.abspath('../../')) #49120312421 or commcare-/hq   
    curdir = os.getcwd()
    
    #go down to that level to actuall make archive
    print "cwd: " + os.getcwd()
    os.chdir('../../../')
    print "archive to deploy: " + archive_to_deploy    
    print "cwd: " + os.getcwd()    
    make_archive(basedir,os.path.basename(archive_to_deploy))
    os.chdir(curdir)
    print "cwd: " + os.getcwd()
        
    sys.stdout = os.fdopen(1, 'w', 0)    
    if debug:
        print 'DEBUG: Writing log to ssh-cmd.log'
        paramiko.util.log_to_file('ssh-cmd.log')
    
    ### Open SSH transport    
    transport = paramiko.Transport((hostname, hostport))
    transport.connect(username=username, password=password)
    
    print "starting sftp session"
    
    sftp = paramiko.SFTPClient.from_transport(transport)
    archive_filename = os.path.basename(archive_to_deploy)
    print "transporting file: " + archive_filename + " to: " + target_abs_path    
    
    sftp.put(archive_to_deploy,target_abs_path + archive_filename)
    sftp.close()
    
    print "sftp file transferred, remoting in to deploy archive"    
    
    print run(transport,'/var/django-sites/builds/rsdeploy.sh  deploy-rev%s %s %s' % (revision_number,basedir, target_deploy_path))
    
#    #print run(transport, 'cd %s' %(target_abs_path))
#    print run(transport,'sudo /etc/init.d/apache2 stop')
#    
#    print run(transport, 'rm -rf %s/%s' % (target_abs_path,target_deploy_path)) 
#    print run(transport,'gunzip %s/%s' % (target_abs_path+"/builds",basename))
#    print run(transport,'tar -xf %s/%s' % (target_abs_path+"/builds",basename[0:-3]))    
#
##    print run(transport,'echo CCHQ_BUILD_DATE=\\"`date`\\" >> %s/projects/cchq_main/settings.py' % (basedir))
##    print run(transport,'echo CCHQ_BUILD_NUMBER=%s >> %s/projects/cchq_main/settings.py' % (build_number,basedir))
##    print run(transport,'echo CCHQ_REVISION_NUMBER=%s >> %s/projects/cchq_main/settings.py' % (revision_number,basedir))
#    
#    
#    print run(transport,'touch %s/projects/cchq_main/media/version.txt' % (basedir))
#    print run(transport,'echo CCHQ_BUILD_DATE=\\"`date`\\" >> %s/projects/cchq_main/media/version.txt' % (basedir))
#    print run(transport,'echo CCHQ_BUILD_NUMBER=%s >> %s/projects/cchq_main/media/version.txt' % (build_number,basedir))
#    print run(transport,'echo CCHQ_REVISION_NUMBER=%s >> %s/projects/cchq_main/media/version.txt' % (revision_number,basedir))
#    
#    print run(transport,'rm -rf %s/projects/cchq_main/%s' % (basedir, 'xform-data'))
#    print run(transport,'rm -rf %s/projects/cchq_main/%s' % (basedir, 'media'))
#    
#    print run(transport,'mkdir %s/projects/cchq_main/%s' % (basedir, 'xform-data'))
#    print run(transport,'mkdir %s/projects/cchq_main/%s' % (basedir, 'media'))
#    #print run(transport,'mkdir %s/projects/cchq_main/%s' % (basedir, 'schemas'))    
#     
#    print run(transport,'chmod 777 %s/projects/cchq_main/' % (basedir))
#    print run(transport,'chmod -R 777 %s/projects/cchq_main/' % (basedir))
#    print run(transport,'chmod 777 %s/projects/cchq_main/cchq.db' % (basedir))    
#    
#    print run(transport,'ln -s /usr/lib/python2.5/site-packages/django/contrib/admin/media/ %s' % (basedir + "/projects/cchq_main/media/admin-media"))
#        
#    print run(transport,'mv %s %s/%s' % (basedir,target_abs_path,target_deploy_path))
#    print run(transport,'cd %s/%s/projects/cchq_main;python manage.py reset_db --noinput;python manage.py syncdb --noinput;python manage.py graph_models -a -g -o media/fullgraph.png' % (target_abs_path,target_deploy_path))    
#    print run(transport,'gzip %s' % (target_abs_path+"/builds/"+basename[0:-3]))
#    
#    
#    print run(transport,'sudo /etc/init.d/apache2 start')
    try:
        transport.close()
    except:
        pass
    print "Finished deployment"


if __name__ == "__main__":
    
    try:       
        hostname = os.environ['DEPLOY_HOST']
        username = os.environ['DEPLOY_USERNAME']
        password = os.environ['DEPLOY_PASSWORD']
        
        target_abs_path = os.environ['DEPLOY_ABS_PATH']
        target_url_path = os.environ['DEPLOY_URL_PATH']
    
        build_number= os.environ['BUILD_NUMBER']
        revision_number= os.environ['REVISION_NUMBER']
    except:
        #no environmental variables, check to see if the arguments are there in the cmdline
        if len(sys.argv) != 8:
            print """\tUsage: 
                deploy.py
                     <remote host> 
                     <remote username> 
                     <remote password> 
                     <remote deploy dir> - '/var/django-sites/builds/ #trailing slash is necessary!
                     <remote deploypath> - 'commcarehq_test' #underscores only.  The database name and directory name and stuff will be based upon this
                     <build number> 
                     <revision number>
                    """                    
            sys.exit(1)
        else:
            hostname = sys.argv[1]
            username = sys.argv[2]
            password = sys.argv[3]
            
            target_abs_path = sys.argv[4]
            target_url_path = sys.argv[5]
        
            build_number= sys.argv[6]
            revision_number= sys.argv[7]      
            
    #do_deploy(hostname, username, password, target_abs_path,target_url_path,build_number,revision_number)
    do_local_deploy(target_abs_path,target_url_path,build_number,revision_number)
