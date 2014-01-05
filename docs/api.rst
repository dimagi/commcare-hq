API
===
.. TODO: describe lucene syntax for ES resources
    Add other resources

Bulk User Resource
~~~~~~~~~~~~~~~~~~
| Resource name: ``bulk_user``
| First version available: ``v0.5``

This resource is used to get basic user data in bulk, fast.  This is especially useful if you need to get, say, the name and phone number of every user in your domain for a widget.

Currently the default fields returned are::

    id
    email
    username
    first_name
    last_name
    phone_numbers

Supported Parameters:
.....................

 * ``q`` - query string
 * ``limit`` - maximum number of results returned
 * ``offset`` - Use with ``limit`` to paginate results
 * ``fields`` - restrict the fields returned to a specified set

Example query string::

    ?q=foo&fields=username&fields=first_name&fields=last_name&limit=100&offset=200

This will return the first and last names and usernames for users matching the query "foo".  This request is for the third page of results (200-300) 

| Additional notes:
| It is simple to add more fields if there arises a significant use case.
| Potential future plans:
    Support filtering in addition to querying.
    Support different types of querying.
    Add an order_by option
