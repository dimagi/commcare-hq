User Domain List
---------------- 

**Purpose:**
    Look up the list of domains that the authenticated web user is a member of.

**Authentication:**
    For more information, please review Authentication.

**URL:**

.. code-block:: text

    https://www.commcarehq.org/api/v0.5/user_domains/

**Sample Response:**

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
