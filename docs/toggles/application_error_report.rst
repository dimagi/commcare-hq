Application Error Report
========================
This plugin is a useful tool for debugging errors that are preventing mobile users from
successfully submitting a form. This includes things such as:
- A calculation error related to a function that CommCare does not recognize being used
in the calculation.
- Errors related to trying to access data using the incorrect path.

It is important to note that a mobile user will need to sync their application in order for
any mobile error logs to be shown in the Application Error Report. It is therefore good practice
that users sync regularly to ensure that this report is kept up-to-date.

This plugin needs to be enabled on a per-user basis. Once enabled for a user, this report
can be accessed under **Project Reports**

Data will not be sent to this report if the ``SERVER_ENVIRONMENT`` environment setting has
been added to ``NO_DEVICE_LOG_ENVS``. This is true for Dimagi maintained environments where
application errors get sent to Sumologic.
