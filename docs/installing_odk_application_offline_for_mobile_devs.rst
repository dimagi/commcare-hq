Installing ODK Application Offline for Mobile Devs
==================================================

.. Think this page should be mostly/entirely obsolete since Offline
.. Install got implemented, yes? If no one disagrees I can type up some
.. new instructions

.. NOTE:: As of version 2.13, Offline install is now built-in to
          CommCareODK. Details are at 
          `Installing CommCareODK Android`_.

#. Navigate to your application on CommCareHQ
#. Click "Deploy"
#. On the deployment page, select "View Source Files" (need to be
   super/power user to do this)
#. Download every resource file there (by right clicking) into a folder
   on your machine, creating the necessary folder structure (default,
   en, modules-X, etc)
#. Copy this folder into your commcare-odk/assets folder in your Eclipse
   environment
#. Uninstall CommCareODK from your device and push the most recent
   version from your dev env. Note that this creates an APK file in
   commcare-odk/bin which you can then give to other people to install
   both your build and your app.
#. On CommCareODK, click ""Enter URL" from the home screen
#. From the selector, choose "Raw." This will pre-populate the field
   with jr://asset/test/profile.ccpr
#. Change this path to point to the profile.xml/profile.ccpr of your
   folder
#. Select "Start Install"

If your app has multimedia you will have to add it separately:

#. Follow the process above. After pressing "Start Install," you should
   get an error about your media not being found. This error should
   reference the file path where CommCare is looking for your media.
#. In CommCare, go to your application and select "Multimedia" from the
   left menu. From here, download the multimedia zip file.
#. Connect your phone to your computer and turn on USB mode so you can
   transfer files.
#. Move the multimedia files onto your phone, based on where the error
   message is looking for them.
#. Go back to CommCare, which should automatically finish installing. If
   it doesn't, re-try the installation.

 
.. _Installing CommCareODK Android: <https://confluence.dimagi.com/display/commcarepublic/Installing+CommCareODK+Android>
