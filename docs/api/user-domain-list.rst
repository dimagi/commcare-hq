User Domain List
================

Overview
--------

**Purpose**
    Look up the list of domains that the authenticated web user is a member of.

**Authentication**
    For more information, please review  `API Authentication <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2279637003/CommCare+API+Overview#API-Authentication>`_.

**Base URL**

.. code-block:: text

    https://www.commcarehq.org/api/user_domains/v1/

**Method**
    GET

Request & Response Details
---------------------------

**Sample Response**

.. code-block:: json

    {
      "meta": {
        "limit": 20,
        "next": null,
        "offset": 0,
        "previous": null,
        "total_count": 16
      },
      "objects": [
        {
          "domain_name": "dimagi",
          "project_name": "dimagi"
        },
        {
          "domain_name": "commcare",
          "project_name": "commcare"
        },
        {
          "domain_name": "demo",
          "project_name": "My Demo Project"
        }
      ]
    }
