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
	
	 

== Setting up the Dimagi Form Designer ==

1. Setup FormDesigner
    - download latest zip form build server (FormDesigner project): http://build.dimagi.com:250/   
    - serve it somewhere statically via something like apache or nginx
2. Setup XEP (Xform Exchange Protocol) Server
    - download standalone_xep_edit_server from github: https://github.com/dimagi/standalone-xep-edit-server
    - Configure
        - couch db settings
        - XEP settings (look at localsettings.py.example in that project for tiops)
     - run syncdb and runserver where you are serving it 
3. Configure xep_hq_server 
    - in localsettings point EDITOR_URL to your XEP server above (the right addresss is 
      http(s)://<xepservername>:<port>/xep/initiate
    
    
    	 