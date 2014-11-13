.. export API:

Export API
========== 

.. NOTE:: Exports we will serve via this API have a file size limitation 
          of 10MB. Files larger than this may not successfully download.
          For larger projects we recommend using the 
          `CommCare Data Export Tool`_.

.. NOTE:: This feature (API Access) is only available to CommCare users 
          with a Standard Plan or higher. For more details, see the
          `CommCare Software Plan page`_.


.. _CommCare Data Export Tool: https://confluence.dimagi.com/display/commcarepublic/CommCare+Data+Export+Tool
.. _CommCare Software Plan page: http://www.commcarehq.org/software-plans/


Form Data Export
----------------

For export of form data, head on over to (where you will replace
[domain] with the name of your project domain): ::

    https://www.commcarehq.org/a/[domain]/data/excel_export_data/

where you'll see all of your possible exports, including custom exports
you can configure right there. You can click on any of the Download
buttons to download manually, but to do this programmatically you'll
want the url, so right click and select "Copy Link Address" (or the
equivalent in your browser). That's the url you should start from.

For form exports you can use the following URL parameters: ::

    http://www.commcarehq.org/a/[domain]/reports/export/?export_tag=[form xmlns]&previous_export=[previous export]&format=[format]

+-------------------+----------------------------------------+-----------------------------------------------------------------+
| Parameter         | Value                                  | Examples                                                        |
+===================+========================================+=================================================================+
| export\_tag       | The xmlns of the form to download.     | %22http://openrosa.org/foo/my/form/xmlns%22 (NOTE the           |
|                   |                                        | escaped quotes around the form xmlns. It will not work without  |
|                   |                                        | them.                                                           |
+-------------------+----------------------------------------+-----------------------------------------------------------------+
| previous\_export  | The previous export id (optional)      | abc123fda2b3c2gad5125                                           |
+-------------------+----------------------------------------+-----------------------------------------------------------------+
| format            | Export format (optional)               | csv = csv, xlsx = Excel 2007 (this is the default), xls = Excel |
|                   |                                        | (previous version), html = HTML view, json = JSON dump,         |
|                   |                                        | raw = zipped xmlsubmission files. No other values are allowed.  |
+-------------------+----------------------------------------+-----------------------------------------------------------------+
| include\_errors   | Whether to include errors (duplicates  | True, False (default)                                           |
|                   | or things the server couldn't parse)   |                                                                 |
|                   | (optional)                             |                                                                 |
+-------------------+----------------------------------------+-----------------------------------------------------------------+
| max\_column\_size | The maximum length (in characters)     | any number, the default is 2000                                 |
|                   | that should be used for the column     |                                                                 |
|                   | headers. Headers beyond this size will |                                                                 |
|                   | be truncated.                          |                                                                 |
+-------------------+----------------------------------------+-----------------------------------------------------------------+

The "previous\_export" parameter is optional, but can be used to
download partial data. With each download, CommCareHQ will return this
value in the "X-CommCareHQ-Export-Token" header in the response. You can
save this token and pass it back and only data since your last download
will be returned. This parameter does not work with the raw export
format.

If there is no data the response code will be a 302 redirect to the
export listing page. Custom Export uses a different URL but the same url
params except for export\_tag, which is unnecessary.

Cases, Referrals, and Users Export
----------------------------------

To export your Cases, Referrals, and Users (as 3 CSV files zipped
together) use the following URL: ::

    https://www.commcarehq.org/a/[domain]/reports/download/cases/?format=csv

You can use the following url parameter:

+-------------------+----------------------------------------+-----------------------------------------------------------------+
| Parameter         | Value                                  | Examples                                                        |
+===================+========================================+=================================================================+
| include\_closed   | true/false (defaults to false)         | include\_closed=true                                            |
+-------------------+----------------------------------------+-----------------------------------------------------------------+
| format            | (same as above)                        |                                                                 |
+-------------------+----------------------------------------+-----------------------------------------------------------------+
 

Using with curl from the linux command line
-------------------------------------------

The export URLs support HTTP-Digest authentication in addition to the
normal session-based authentication used on the rest of CommCare HQ.
This makes it easy to access these urls programmatically. For example,
with curl you can use the --digest flag and specify a username with -u
as follows: ::

    $ curl -v --digest -u $USERNAME '$URL' > data.zip
    $ unzip -d data data.zip

Here, you can only use your *web login* to authenticate, as the
individual CHWs do not have permission to see everyone's data. (And
their passwords tend to be far less secure.) Make sure to use the
correct URL parameters described above in your URL. The file will be
saved to the file specified, but the verbose outputs, including headers,
will be printed to the screen. If you want to use the checkpointing
feature (not available for case export), look for a line something like ::

    < X-CommCareHQ-Export-Token: 42776b054d8256c86d1f8ca2da557841

near the bottom. Save the token, and pass it as previous\_export in the
next curl request you make to get only updates.

In order to get this token programmatically, you could redirect stderr
to a file (let's say headers.txt) and then use grep and sed as follows
to strip the other text on that line, and put that in (say) token.txt: ::


    $ curl -v --digest -u $USERNAME '$URL' > data.zip 2> headers.txt
    $ unzip -d data data.zip
    $ grep 'X-CommCareHQ-Export-Token' headers.txt | sed -e 's/< X-CommCareHQ-Export-Token: //'  > token.txt

This will leave you with the a directory with the csv files in the
'data' directory, and the export token (to be used next time) in
token.txt.
