Bulk User Resource
==================

Overview
---------
**Purpose**
    This resource is used to get basic user data in bulk, fast.  This is especially useful if you need to get, say, the name and phone number of every user in your domain for a widget.


**Resource name:** ``bulk-user``

**Base URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/bulk-user/

**First version available:** ``v0.5``

Request & Response Details
---------------------------

**Output Values**

Currently, the default fields returned are::

    id
    email
    username
    first_name
    last_name
    phone_numbers

**Sample Output**

.. code-block:: json

   {
       "meta": {
           "limit": 20,
           "next": "?limit=20&offset=20",
           "offset": 0,
           "previous": null,
           "total_count": 304
       },
       "objects": [
           {
               "email": "user1@gmail.com",
               "first_name": "User1",
               "id": "0e478e1f5430c8efad06a2c88f1f5d80",
               "last_name": "",
               "phone_numbers": [],
               "resource_uri": "",
               "username": "user1@gmail.com"
           },
           {
               "email": "user2@gmail.com",
               "first_name": "User2",
               "id": "149a053c07768b097ccc4f6a14d75863",
               "last_name": "Last Name2",
               "phone_numbers": [],
               "resource_uri": "",
               "username": "user2@dimagi.com"
           },
           {
               "..."
           }
       ]
   }


**Supported Parameters**

 * ``q`` - query string
 * ``limit`` - maximum number of results returned
 * ``offset`` - Use with ``limit`` to paginate results
 * ``fields`` - restrict the fields returned to a specified set

**Example query string**::

    ?q=foo&fields=username&fields=first_name&fields=last_name&limit=100&offset=200

This will return the first and last names and usernames of users matching the query "foo".  This request is for the third page of results (200-300)

**Additional notes**
    It is simple to add more fields if there arises a significant use case.

    Potential future plans:
     - Support filtering in addition to querying.
     - Support different types of querying.
     - Add an order_by option
