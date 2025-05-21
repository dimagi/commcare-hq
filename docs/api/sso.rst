Single Sign On
==============

Overview
--------

**Purpose**
    Validate login credentials and get the user profile for a mobile worker or a web user.

Endpoint Specifications
-----------------------

**Base URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/sso/v1/

**Authentication**
    Post a URL-encoded username and password, such as:

.. code-block:: text

    username=MY_USERNAME&password=MY_PASSWORD

If your credentials are correct, the output will be identical to the `List User API <list-mobile-workers.rst>`_ or `List Web User API <list-webusers.rst>`_ , as appropriate.
