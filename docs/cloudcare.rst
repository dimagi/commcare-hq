CloudCare
=========

Offline Cloudcare
-----------------

What is it?
~~~~~~~~~~~

First of all, the "offline" part is a misnomer.
This does not let you use CloudCare completely offline.
We need a new name.

Normal CloudCare requires a round-trip request to the HQ touchforms daemon every time you answer/change a question in a form.
This is how it can handle validation logic and conditional questions with the exact same behavior as on the phone.
On high-latency or unreliable internet this is a major drag.

"Offline" CloudCare fixes this by running a local instance of the touchforms daemon.
CloudCare (in the browser) communicates with this daemon for all matters of maintaining the xform session state.
However, CloudCare still talks directly to HQ for other CloudCare operations, such as initial launch of a form, submitting the completed form, and everything outside a form session (case list/select, etc.).
Also, the local daemon itself will call out to HQ as needed by the form, such as querying against the casedb.
*So you still need internet!*

How does it work?
~~~~~~~~~~~~~~~~~

The touchforms daemon (i.e., the standard JavaRosa/CommCare core with a Jython wrapper) is packaged up as a standalone jar that can be run from pure Java.
This requires bundling the Jython runtime.
This jar is then served as a "Java Web Start" (aka JNLP) application (same as how you download and run WebEx).

When CloudCare is in offline mode, it will prompt you to download the app; once you do the app will auto-launch.
CloudCare will poll the local port the app should be running on, and once its ready, will then initialize the form session and direct all touchforms queries to the local instance rather than HQ.

The app download should persist in a local application cache, so it will not have to be downloaded each time.
The initial download is somewhat beefy (14MB) primarily due to the inclusion of the Jython runtime.
It is possible we may be able to trim this down by removing unused stuff.
When started, the app will automatically check for updates (though there may be a delay before the updates take effect).
When updating, only the components that changed need to be re-downloaded (so unless we upgrade Jython, the big part of the download is a one-time cost).

When running, the daemon creates an icon in the systray.
This is also where you terminate it.

How do I get it?
~~~~~~~~~~~~~~~~

Offline mode for CloudCare is currently hidden until we better decide how to intergrate it, and give it some minimal testing.
To access:

* Go to the main CloudCare page, but don't open any forms
* Open the chrome dev console (``F12`` or ``ctrl+shift+J``)
* Type ``enableOffline()`` in the console
* Note the new 'Use Offline CloudCare' checkbox on the left

