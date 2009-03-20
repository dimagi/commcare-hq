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

import sys, os, select
import paramiko

debug = True

hostport = 22

def make_archive(path, target_filename):
    print "Making archive %s : %s" % (path, target_filename)    
    tar = tarfile.open(target_filename, "w:gz")
    tar.add(path)
    tar.close()
    print "archive created successfully"

def putfile(t,filename):
    pass

def run(t, cmd):
    'Open channel on transport, run command, capture output and return'
    global debug
    out = ''

    if debug: print 'DEBUG: Running cmd:', cmd
    chan = t.open_session()
    
    #chan.setblosesscking(0)

    try:
        chan.exec_command(cmd)
    except SSHException:
        print "Error running remote command, yo", SSHException        
        sys.exit(1)
    

    ### Read when data is available
#    while select.select([chan,], [], []):
#        x = chan.recv(1024)
#        if not x: break
#        out += x
#        select.select([],[],[],.1)
#
#    if debug: print 'DEBUG: cmd results:', out
    chan.close()
    return out


def do_deploy(hostname, username, password, target_abs_path, target_deploy_path, build_number, revision_number):
    ### Unbuffered sys.stdout
    #COMMCARE VARS
    #CCHQ_BUILD_NUMBER=-1
    #CCHQ_REVISION_NUMBER=-1
    #CCHQ_BUILD_DATE=''
    
    
    #make the archive    
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    archive_to_deploy = os.path.join('../../../','deploy-b%s-rev%s.tar.gz' % (build_number, revision_number))
    
    basedir = os.path.basename(os.path.abspath('../../'))    
    curdir = os.getcwd()
    os.chdir('../../../')
    make_archive(basedir,os.path.basename(archive_to_deploy))
    os.chdir(curdir)
    
    
    sys.stdout = os.fdopen(1, 'w', 0)    
    if debug:
        print 'DEBUG: Writing log to ssh-cmd.log'
        paramiko.util.log_to_file('ssh-cmd.log')
    
    ### Open SSH transport
    
    transport = paramiko.Transport((hostname, hostport))
    transport.connect(username=username, password=password)
    
    print "starting sftp session"
    sftp = paramiko.SFTPClient.from_transport(transport)
    basename = os.path.basename(archive_to_deploy)
    sftp.put(archive_to_deploy,target_abs_path + "/builds/" + basename)
    sftp.close()
    
    print "sftp file transferred, remoting in to deploy archive"    
    
    #print run(transport, 'cd %s' %(target_abs_path))
    print run(transport, 'rm -rf %s/%s' % (target_abs_path,target_deploy_path)) 
    print run(transport,'gunzip %s/%s' % (target_abs_path+"/builds",basename))
    print run(transport,'tar -xf %s/%s' % (target_abs_path+"/builds",basename[0:-3]))    
    
    print run(transport,'echo CCHQ_BUILD_DATE=\\"`date`\\" >> %s/projects/cchq_main/settings.py' % (basedir))
    print run(transport,'echo CCHQ_BUILD_NUMBER=%s >> %s/projects/cchq_main/settings.py' % (build_number,basedir))
    print run(transport,'echo CCHQ_REVISION_NUMBER=%s >> %s/projects/cchq_main/settings.py' % (revision_number,basedir))
    
    print run(transport,'touch %s/projects/cchq_main/media/version.txt' % (basedir))
    print run(transport,'echo CCHQ_BUILD_DATE=\\"`date`\\" >> %s/projects/cchq_main/media/version.txt' % (basedir))
    print run(transport,'echo CCHQ_BUILD_NUMBER=%s >> %s/projects/cchq_main/media/version.txt' % (build_number,basedir))
    print run(transport,'echo CCHQ_REVISION_NUMBER=%s >> %s/projects/cchq_main/media/version.txt' % (revision_number,basedir))
    
    
    print run(transport,'mkdir %s/projects/cchq_main/%s' % (basedir, 'xform-data'))
    print run(transport,'mkdir %s/projects/cchq_main/%s' % (basedir, 'schemas'))    
     
    print run(transport,'chmod 777 %s/projects/cchq_main/' % (basedir))
    print run(transport,'chmod -R 777 %s/projects/cchq_main/' % (basedir))
    print run(transport,'chmod 777 %s/projects/cchq_main/cchq.db' % (basedir))
    print run(transport,'rm -rf /var/commcarehq-test')
    
    
    print run(transport,'ln -s /usr/lib/python2.5/site-packages/django/contrib/admin/media/ %s' % (basedir + "/projects/cchq_main/media/admin-media"))
        
    print run(transport,'mv %s %s/%s' % (basedir,target_abs_path,target_deploy_path))
    print run(transport,'cd %s/%s/projects/cchq_main;python manage.py syncdb;python manage.py graph_models -a -g -o media/fullgraph.png' % (target_abs_path,target_deploy_path))    
    print run(transport,'gzip %s' % (target_abs_path+"/builds/"+basename[0:-3]))
    
    
    print run(transport,'sudo /etc/init.d/apache2 restart')
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
                     <remote deploy dir> - '/var/django-sites
                     <remote deploypath> - 'commcarehq-test'
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
            
    do_deploy(hostname, username, password, target_abs_path,target_url_path,build_number,revision_number)
