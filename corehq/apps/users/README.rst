Users
=====

Terminology
~~~~~~~~~~~

From a product perspective, there are two types of users:

* Web users administrate projects. They primarily use CommCare HQ, typically on a desktop. Their tasks include building
  applications, viewing reports, exporting data, etc. They manage their own accounts: they may create accounts
  or may create an account by accepting an invitation, but in either case, they log in with their email address
  and set their own password. Web users may use multiple domains and have a "membership" in each domain they access.
* Mobile users collect data. They primarily use CommCare, typically on a mobile device. Their accounts
  are managed by administrators, who create their accounts and set their passwords. On projects that use
  Web Apps, "mobile" users don't use a mobile device. Mobile users are associated with a dingle domain. In code, 
  mobile users are sometimes called "CommCare Users" since they are expected to be doing data entry in CommCare mobile app.

There can be overlap between groups: for example, web users can enter data using web apps or app preview, and mobile
users can be granted access to do tasks in HQ other than data entry. Nonetheless, HQ has assumptions baked in about
how web and mobile users view the system differently. Examples:

* The menu code (``tabclasses.py``) bases some of its logic on whether the current user is web or mobile.
* The classes or users in reports filters (``All Data``, ``Project Data``, etc.) are defined partially based on the web/mobile
  distinction, and the default for reports (``Project Data``) excludes web users because they're assumed to be app builders
  who don't submit "real" data, only test data.

CouchUser Class Hierachy
~~~~~~~~~~~~~~~~~~~~~~~~

``CouchUser``, a subclass of ``Document``, controls the majority of user-related model logic.

Each ``CouchUser`` is associated with a Django user, an instance of ``django.contrib.auth.models.User``.
The fields stored in ``User`` need to be synced between this object and the related couch document. The mixin
``DjangoUserMixin`` defines the django-related fields, and ``CouchUser.get_django_user`` can be used to get the
``User`` asscoaited with a ``CouchUser``.

``CommCareUser`` and ``WebUser`` are subclasses of ``CouchUser`` that add in logic about domain membership - with a single
membership for each ``CommCareUser`` and multiple memberships for ``WebUser``.

User Data
~~~~~~~~~

Users may have arbitrary data associated with them, assigned by the project and then referenced in applications.
This user data is implemented via the ``custom_data_fields`` app, the same way as location and product data.

User data is only relevant to mobile users. However, ``user_data`` is a property of ``CouchUser``
and not ``CommCareUser`` because a legacy feature applied user data to web users. As a result of this,
some web users do have user data saved to their documents.

User data should be accessed via the ``metadata`` property, which takes into account user data profiles.

UserRole and Permissions
~~~~~~~~~~~~~~~~~~~~~~~~

Within a domain, users can be assigned roles to control their access to specific functionality. A ``UserRole`` consists
primarily of a ``Permissions`` object, which is a large set of flags that each maps to a particular feature. Many features
have one flag for view access and another for edit access. Most permissions control access to a specific page or pages,
but some do more unique things, such as controlling a user's access to locations or APIs.

The ``UserRolePresets`` class defines a set of templates available to all projects. In addition to this, projects
can define their own roles.

User roles were created primarily to be used with web users, but roles may also be assigned to mobile users.
