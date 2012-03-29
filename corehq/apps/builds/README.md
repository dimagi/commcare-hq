Adding CommCare Builds to CommCare HQ
=====================================

* First you need to get the CommCare build off the Dimagi build server:
    1. Go here http://build.dimagi.com:250/ and click [Login as a Guest User](http://build.dimagi.com:250/guestLogin.html?guest=1)
    2. Pick the branch you want and click on the link (e.g. "CommCare 1.3")
    3. Pick a build (probably the first one in the table) and write down the build number (under "#"). This will be referenced as `$build_number` below
    4. Click on "Success" in that row (under "Results")
    5. Select the "Build Parameters" tab and write down the version (all the way at the bottom in the "Environment Variables" table. This will be referenced as `$version` below
    6. Select the "Artifacts" tab and click on "Download all (.zip)" on the right hand side. Note the path of the downloaded file. This will be referenced as `$build_path` below
* Now `cd` into the commcare-hq root directory, and run the following command:
  `python manage.py add_commcare_build $build_path $version $build_number`

You're done. In order to get full permissions on a J2ME phone, you need to set up jar signing. To do so, you will need
acquire a code signing certificate (from e.g. Thawte).

* To enable jar signing, put your certificate information in localsettings.py as follows:

<!-- language: lang-py -->

    JAR_SIGN = dict(
        key_store = "/PATH/TO/KEY_STORE",
        key_alias = "KEY",
        store_pass = "*****",
        key_pass = "*****",
    )

* To skip this step, comment out the code entirely:

<!-- language: lang-py -->

    #JAR_SIGN = dict(
    #    key_store = "/PATH/TO/KEY_STORE",
    #    key_alias = "KEY",
    #    store_pass = "*****",
    #    key_pass = "*****",
    #)
