Common CommCare Mobile Dev Workspace Build Errors
=================================================

.. NOTE:: This page will be serve as a troubleshooting guide for common
          CommCaredev environment errors and issues


Common, Utility Solutions
-------------------------

Make sure you clean your workspace; this will resolve many issues

Make sure you refresh your packages after pulls and pushes

If you are having issues getting your Nokia emulator to run, clear out
the \*.db files in the appdb folder of the phone

Good, old fashioned restart of Eclipse, your phone, and adb


Error type: Multiple dex files
------------------------------


Examples
~~~~~~~~

Unable to execute dex: Multiple dex files define

Conversion to Dalvik format failed: Unable to execute dex: Multiple dex
files define


What this bug means
~~~~~~~~~~~~~~~~~~~

This error occurs when multiple instances of a library are present in a
package or application. For example, the CommCareODK.apk application has
two commcare-libraries.jar files in its path when you try to build it.


Resolving this error
~~~~~~~~~~~~~~~~~~~~

You must ensure that the ODK application only has each library on its
path once.

This can be due to a library being in both the project's lib and libs
folder - simply delete the .jar from the libs folder

Often this issue is introduced due to the opendatakit.collect project
Exporting the library. Go to that project's build path, select the
"Order and Exports" tab, and make sure that none of the imported .jar
files are checked; only opendatakit.collect specific folders should be
exported


Error type: Activity not started
--------------------------------


Example
~~~~~~~

Starting: Intent { act=android.intent.action.MAIN
cat=[android.intent.category.LAUNCHER]
cmp=org.commcare.dalvik/.activities.CommCareHomeActivity }

ActivityManager: Warning: Activity not started, its current task has
been brought to the front


What this bug means
~~~~~~~~~~~~~~~~~~~

The application was already running on your device and you haven't made
any changes to your code since.


Resolution
~~~~~~~~~~

Just open the application via your phone, since the code is already up
to date. You might need to save your changes, or clean, and run again if
you're certain you've made changes.


Error type: Signature Mismatch
------------------------------


What this bug means
~~~~~~~~~~~~~~~~~~~

The application was already running on your device with a different
signing key: usually, this means you installed a play store or build
server version of CommCareODK, and are trying to push your local code.
These have separate keys, so can't be upgraded over each other.


Resolution
~~~~~~~~~~

Uninstall the version currently on your phone and run your code again


Error type: Eclipse hanging on "Launching Application"
------------------------------------------------------


Example
~~~~~~~

Failed to install commcare-odk.apk on device '015d1884b53c1613': timeout


What this bug means
~~~~~~~~~~~~~~~~~~~

This means Eclipse is having trouble communicating with your device.
This can be due to a number of things, but if you're setup for USB
debugging properly this usually has to do with the adb


Resolution
~~~~~~~~~~

Close Eclipse. From the command line, run adb kill-server then adb
start-server (you'll need adb-tools on your path to do this). Then
restart Eclipse.


Error type: Source not found
----------------------------


What this bug means
~~~~~~~~~~~~~~~~~~~

This isn't actually a runtime bug, but rather a debug issue. It means
Eclipse tried to step through some portion of the code that you don't
have the source for. (For example, if you're using the commcare- and
javarosa-libraries.jar instead of the source code)


Resolution
~~~~~~~~~~

Either attach the source code to these jars (I have no experience doing
this, though Eclipse seems to provide tools) or don't run in Debug.


Error type: stlLoadLibs or stlport\_shared
------------------------------------------


What this bug means
~~~~~~~~~~~~~~~~~~~

One of the Android libraries requires that your SQL libs be in a libs
folder (rather than just in your lib folder) in the commcare-odk package


Resolution
~~~~~~~~~~

Copy the armeabi folder from lib into a new folder called libs in your
commcare-odk package


Error type: Cannot import com.google.android
--------------------------------------------


What this bug means
~~~~~~~~~~~~~~~~~~~

Problems with Google-related code


Resolution
~~~~~~~~~~

Make sure that the correct Google APIs are installed:

-  In Eclipse, go to the Android SDK Manager (button in top toolbar with
   an Android robot)
-  Make sure all of the below are installed

   -  Android SDK Tools (most recent version)
   -  Android SDK Build Tools (most recent version)
   -  SDK Platform (all versions)
   -  Google APIs (all versions)
   -  Android Support Library
   -  Google Play Services

Also make sure that you're targeting the correct API version:

-  In Eclipse's package manager, right-click on a project and go
   to *Properties*
-  Under *Android*, make sure that *Google APIs* is checked, API
   level 15
