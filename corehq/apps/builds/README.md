Syncing local HQ instance with an Android Phone
===========================

If you would like to use a url or barcode scanner to download the application
to your phone here is what you need to setup.

### Make sure your local django application is accessible over the network

The django server will need to be running on an ip address instead of localhost.
To do this, run the application using the following command, substituting your
local IP address.

`./manage.py runserver 192.168.1.5:8000`

Try accessing this url from the browser on your phone to make sure it works.

### Make CommCare use this IP address

The url an application was created on gets stored for use by the app builder
during site creation. This means if you created a site and application
previously, while using a 'localhost:8000' url, you will have to make a code
tweak to have the app builder behave properly.

The easiest way to check this is to see what url is shown below the barcode on
the deploy screen.

If it is currently displaying a `localhost:8000/a/yourapp/...` url then open
`localsettings.py` and set `BASE_ADDRESS = "192.168.1.5:8000"` substituting
`192.168.1.5` with your local IP address.

### Try it out

With this set up, you should be able to scan the barcode from your phone to
download and install your own locally built CommCare application!


Adding CommCare (J2ME) Builds to CommCare HQ
=====================================

Following is a manual process to find and import a build. Alternatively, you can run
`./manage.py commcare_build_importer` to do the same without leaving your console.
This will run you through all the builds and let you import the build you need.

* First you need to get the CommCare build off the Dimagi build server:
    1. Go here http://jenkins.dimagi.com/view/CommCare%20Mobile/ 
    2. Pick the branch you want and click on the link (e.g. "commcare-mobile-2.19")
    3. Pick a build (probably the first one in the table on the left) and write down
       the build number (under "#"). This will be referenced as `$build_number`
       below
    4. Click on that row
    5. Select the "Environment Variables" tab and write down the VERSION (all
       the way at the bottom of the table.) This will
       be referenced as `$version` below
    6. Go back, and select "Build Artifacts" -> "application" -> "posttmp" -> "artifacts.zip".   If you use the commandline option below,
       note the path of the downloaded file. This will be
       referenced as `$build_path`.
       If you use the web UI, copy the download URL. This will be called `build_url`.

You now have two options for how to install it.

* Command line:
    * `cd` into the commcare-hq root directory, and run the following command:
      `python manage.py add_commcare_build $build_path $version $build_number`
* Web UI
    * Go to `/builds/edit_menu/` and follow the instructions at the bottom for adding your build.

Now make sure the build is available in the app settings.  Go to `/builds/edit_menu/`, then add the version and a label. You can also set the default here to be the version you've added.

Finally, in order to get full permissions on a J2ME phone, you need to set up jar signing. To do so, you will need
acquire a code signing certificate (from e.g. Thawte).

* To enable jar signing, put your certificate information in localsettings.py as follows:

<!-- language: lang-py -->

    JAR_SIGN = dict(
        key_store = "/PATH/TO/KEY_STORE",
        key_alias = "KEY",
        store_pass = "*****",
        key_pass = "*****",
    )

* If you don't need this, skip this step by commenting out the code entirely:

<!-- language: lang-py -->

    #JAR_SIGN = dict(
    #    key_store = "/PATH/TO/KEY_STORE",
    #    key_alias = "KEY",
    #    store_pass = "*****",
    #    key_pass = "*****",
    #)

You're done!
