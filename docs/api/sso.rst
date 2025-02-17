Single Sign On
--------------

**Purpose:**
    Validate login credentials and get the user profile for a mobile worker or a web user.

**Single Sign On URL:**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/sso/

**Sample URL:**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/sso/

**Authentication:**
    Post a URL-encoded username and password, such as:

.. code-block:: text

    username=MY_USERNAME&password=MY_PASSWORD

If your credentials are correct, the output will be identical to the List User API or List Web User API, as appropriate.
