End-to-End Developer Guide
==============================================
  
Audience and Intent
-------------
The audience for this guide is software developers who are seeking to be able to run a full end-to-end software environment for CommCare, including both the CommCare HQ backend and the CommCare Android mobile applicaiton.

Following these steps will allow a developer to replicate full end-to-end functionality of the tools to support addressing issues or creating new functionality. 
  
Prerequisites
-------------

- You have followed the `CommCare HQ "Getting Started" guide <https://github.com/dimagi/commcare-hq/blob/master/DEV_SETUP.md>`_ to set up and run a local instance of CommCare HQ. 
- You have followed the `CommCare Android "Getting Started" guide <https://github.com/dimagi/commcare-android/blob/master/README.md>`_ to set up and succesfully build CommCare Android
- You have an Android Device (or emulator) with a deployed version of CommCare Android from your local development environment
- Your Android Device and CommCareHQ Server are on the same local network

1. Expose CommCare HQ on your local network
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To allow your Android device to communicate with the local CommCare HQ instance, you need to make sure it is exposed and accessible to the local network, which you can configure using nginx. For detailed instructions and advanced tips on exposing your local environment, refer to the `detailed instructions and advanced tips <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/builds/README.rst>`_.

- Install Nginx
- Add the CommCare HQ Nginx config to your Nginx config file:

  - Edit ``/etc/nginx/nginx.conf``
  - At the bottom of the ``http{}`` block, add: ``include /path/to/commcarehq/deployment/nginx/cchq_local_nginx.conf;``

- Start Nginx: ``sudo nginx``
- Set ``BASE_ADDRESS`` in ``localsettings.py`` to your local IP.
- Modify ``cchq_local_nginx.conf`` to use your IP as the ``server_name``
- Reload Nginx config: ``sudo nginx -s reload``

**Confirming Success**

After completing these steps, you should navigate to the local IP address and port for your server on the Android Web Browser. You should see the CommCareHQ login page. If not, your server isn't accessible on the local network, you may need to ensure that ports are open or forwarded in firewalls or network layers. 

**Note on static IP Addresses**

In a local network instalation, your installed applications will be hardcoded to the IP address of the HQ server at the time that the application is built and installed. 

When practical it's recommended to establishing a static internal IP for the HQ server rather than a DHCP assigned address to prevent issues. If your IP address changes, you will need to be ready to create new app builds and perform manual `uninstall/re-installs <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143946239/Installing+CommCare+on+Android+Devices#Uninstall-Your-Application>`_ of the applicaiton on the mobile device. 

2. Create a Mobile Worker and a Test Applicaiton
~~~~~~~~~~~~~~~~~~~~~~~~~

You will need an App and Mobile User in a local project space in order to test the mobile application functionality. Detailed information about your first app can be found in CommCare's `Getting Started Guide <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143954300/Get+Started>`_, but the main steps are highlighted below.
  
**Creating a mobile user account**
- Login to your local CommCare HQ instance, and the default project space you created during server setup
- Go to Users -> Mobile Workers -> Create Mobile Worker
- Enter a username and password for the new mobile worker

**Create and Build a New Application**
- Go to Applications -> New Application
- Click on the Pencil button next to the "Untitled Application" title and give your app a name
- In the left hand pane click "Add..." and choose "Survey" for a basic form module
- Add a Text question to the form and save it
- Click on the App Name to navigate to the release manager 
- Make a new version and Publish your release

3. Install App on CommCare and Test Form Submission
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- On the Android device, open CommCare and scan the QR code to install the app you built in the previous step
- Login to the app using the Mobile Worker credentials you created 
- Press Start, and fill out and submit the form
- Data should be submitted to your local CommCare HQ instance

You've now completed a basic "hello world" form submission workflow with CommCare HQ! You can continue your learning through the `CommCare fundamentals documentation <https://academy.dimagi.com/store>`_ to learn more about app building and data management.
