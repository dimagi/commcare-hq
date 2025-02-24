OTA API Restore
===============

CommCare HQ offers a way to see the exact data that is being sent to the phones in the form of the "restore" XML. This can often be useful for troubleshooting issues or when doing advanced app building off of lookup tables and other data structures.

Viewing the Data
----------------

To view the OTA Restore data, open:

``https://www.commcarehq.org/a/[domain]/phone/restore``

Then enter:

``[username]@[domain].commcarehq.org`` and the user's CommCare password.

Understanding the Data Format
-----------------------------

The data will look exactly the same as a normal user registration response but with a list of case blocks following the registration data.

See more details: `User Registration API <https://bitbucket.org/javarosa/javarosa/wiki/UserRegistrationAPI>`_

**Example XML Output**

.. code-block:: xml

    <?xml version='1.0' encoding='UTF-8'?>
    <OpenRosaResponse xmlns="http://openrosa.org/http/response">
        <message>Successfully restored account danny!</message>
        <Sync xmlns="http://commcarehq.org/sync">
            <restore_id>83226e1e05ebe146685b93a9a312efa3</restore_id>
        </Sync>
        <Registration xmlns="http://openrosa.org/user/registration">
            <username>danny</username>
            <password>sha1$13f7c$5b22f7ef1b05b0b81f6009146f5da173baf27761</password>
            <uuid>da77a254-56dd-11e0-a55d-005056aa7fb5</uuid>
            <date>2011-03-25</date>
        </Registration>
        <!-- this is where fixtures (lookup tables, locations, groups, etc.) go -->
        <!-- this is where all the case blocks go -->
    </OpenRosaResponse>

For more information:
- `CaseXML Spec <https://github.com/dimagi/commcare-core/wiki/casexml20>`_
- `Fixtures Spec <https://github.com/dimagi/commcare-core/wiki/fixtures>`_

When the phone receives the case blocks, for example, it applies them all in order to its internal database, thus reconstructing the case list.

Making the Request Programmatically
-----------------------------------

Assuming your domain is called ``DEMO_DOMAIN``, the request must be sent to:

``https://www.commcarehq.org/a/DEMO_DOMAIN/phone/restore/``

using HTTP basic authentication with the CHW's username and password.

**Example cURL Request**

.. code-block:: bash

    curl --basic -u jason@DEMO_DOMAIN.commcarehq.org:1988 \
    https://www.commcarehq.org/a/DEMO_DOMAIN/phone/restore/?version=2.0

In this example, we are on domain "DEMO_DOMAIN", our CHW's username is ``jason``, and his password is 1988. You'll note that the username, instead of being just ``jason`` is the much longer ``jason@demo.commcarehq.org``. This is to distinguish him from any other ``jason``s on any other domain. The format for the full-length username is:  ``{username}@{domain}.commcarehq.org``
