Syncing local HQ instance with an Android Phone
===============================================

No syncing or submitting, easy method
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you would like to use a url or barcode scanner to download the application to

your phone here is what you need to setup. You won't be able to submit or sync

using this method, but it is easier.

Make sure your local django application is accessible over the network
######################################################################

The django server will need to be running on an ip address instead of localhost.

To do this, run the application using the following command, substituting your

local IP address.

``./manage.py runserver 192.168.1.5:8000``

Try accessing this url from the browser on your phone to make sure it works.

Make CommCare use this IP address
#################################

The url an application was created on gets stored for use by the app builder

during site creation. This means if you created a site and application

previously, while using a 'localhost:8000' url, you will have to make a code

tweak to have the app builder behave properly.

The easiest way to check this is to see what url is shown below the barcode on

the deploy screen.

If it is currently displaying a ``localhost:8000/a/yourapp/...`` url then open

``localsettings.py`` and set ``BASE_ADDRESS = "192.168.1.5:8000"`` substituting

``192.168.1.5`` with your local IP address.

Try it out
##########

With this set up, you should be able to scan the barcode from your phone to

download and install your own locally built CommCare application!

Submitting and syncing from your local HQ instance (harder method)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Install nginx
#############

``sudo apt-get install nginx`` or

``brew install nginx``

Install the configuration file
##############################

In ``/etc/nginx/nginx.conf``, at the bottom of the ``http{}`` block, above any other site includes, add the line:

``include /path/to/commcarehq/deployment/nginx/cchq*local*nginx.conf;``

Start nginx
###########

``sudo nginx``

Make sure your local django application is accessible over the network
######################################################################

``./manage.py runserver``

Try accessing ``http://localhost/a/domain`` and see if it works. nginx should

proxy all requests to localhost to your django server. You should also be able

to access ``http://your_ip_address:8000/a/domain`` from a phone or other device on the

same network.

Make Commcare use your local IP address
#######################################

Set the ``BASE_ADDRESS`` setting in ``localsettings.py`` to your IP address (e.g.

``192.168.0.10``), without a port. You'll have to update this if you ever change

networks or get a new IP address.

Rebuild and redeploy your application
#####################################

You'll have to rebuild and redeploy your application to get it to sync.

Adding CommCare (J2ME) Builds to CommCare HQ
=====================================

- Go to `http://HQ_ADDRESS/builds/edit_menu/`
- In the second section `Import a new build from the build server`

   #. In the Version field input the version in `x.y.z` format
   #. Click `Import Build`
- In the first section `Menu Options` add the version to HQ to make sure the build is available in the app settings.

For legacy J2ME builds
^^^^^^^^^^^^^^^^^^^^^^

Finally, in order to get full permissions on a J2ME phone, you need to set up jar signing. To do so, you will need

acquire a code signing certificate (from e.g. Thawte).

To enable jar signing, put your certificate information in localsettings.py as follows:

.. code-block:: python

    JAR_SIGN = dict(

        key_store = "/PATH/TO/KEY_STORE",

        key_alias = "KEY",

        store_pass = "*****",

        key_pass = "*****",

    )

If you don't need this, skip this step by commenting out the code entirely.

You're done!
