CommCareHQ is a server-side tool to help manage community health workers.
It seamlessly integrates with CommCare mobile and CommCare ODK, as well as
providing generic domain management and form data-collection functionality.

Key Components:
 - CommCare application builder
 - OpenRosa compliant xForms designer
 - SMS integration 
 - Domain/user/CHW management
 - Xforms data collection
 - Case management
 - Over-the-air (ota) restore of user and cases
 - Integrated web and email reporting

Basic Project Structure:

submodules/
    submodule reference to the meat of the code (which lives in many other packages, particularly core-hq)

libs/
	Third party libs (presumably python) that you'll need to reference
	
scripts/
	Any helper scripts you'll want to write to deal with data and or other things.  This stuff should probably run outside the scope of the python environment
	
== Installing CommCare HQ ==

# In command line

git clone git@github.com:dimagi/commcare-hq.git
cd commcare-hq
git submodule init
git submodule update
pip install -r requirements.txt    # see note below
./manage.py syncdb    # (say no to setting up admin account)
./manage.py migrate
./manage.py createsuperuser
./manage.py runserver

# In browser

go to: localhost:8000/admin
login as the superuser you set up
click on Sites, then add Site
add a site with domain name = "localhost:8000"
logout

to test go to localhost:8000 or localhost:8000/login

To create a domain and user without going through the signup, use

./manage.py bootstrap <domain> <user> <password>

# note about requirements.txt

If an import isn't working it may well be because we aren't specifying all versions in the requirements.txt and you have
an old version. If you figure out this problem and figure out what version we *should* be using, feel free to add it to
requirements.txt as ">=ver.si.on" like so:
    couchdbkit>=0.5.2
(Use == for exact version instead of lower bound.)

== Setting up the Dimagi Form Designer ==

1. Setup FormDesigner
    - download latest zip form build server (FormDesigner project): http://build.dimagi.com:250/   
    - serve it somewhere statically via something like apache or nginx
2. Setup XEP (Xform Exchange Protocol) Server
    - download standalone_xep_edit_server from github: https://github.com/dimagi/standalone-xep-edit-server
    - Configure
        - couch db settings
        - XEP settings (look at localsettings.py.example in that project for tips)
     - run syncdb and runserver where you are serving it 
3. Configure xep_hq_server 
    - in localsettings point EDITOR_URL to your XEP server above (the right addresss is 
      http(s)://<xepservername>:<port>/xep/initiate
