Local Setup
===========

.. note::
    Before you begin, please understand that if you are trying to use SAML
    authentication from `localhost`, it will likely fail on the round-trip
    handshake, as it is not a public server.


Pre-Requisites
--------------

First, ensure that you have accounting admin privileges
(see `add_operations_user` management command)


Create a Project
~~~~~~~~~~~~~~~~

1. Navigate to *+ Add Project*
2. Project Name: `sparrow`
3. (Click) **Create Project**


Create an Enterprise Software Plan
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Navigate to *Accounting --> Software Plans*.
2. (Click) **+ Add New Software Plan**
    - Name: `Sparrow Test Flight`
    - Edition: `Enterprise`
    - [x] Is customer software plan
    - (Click) **Create Software Plan**
3. Navigate to *Roles and Features* tab.
    - Role: `Enterprise Plan (enterprise_plan_v0)`
    - Add Features
        - Choose `User Advanced` --> (Click) **Add Feature**
        - Choose `SMS Advanced` --> (Click) **Add Feature**
    - Add Products
        - Choose `CommCare Advanced` --> (Click) **Add Product**
    - (Click) **Update Plan Version**
4. Navigate to *Version Summary* tab.
    - **Observe**: `Sparrow Test Flight (v1)` details look ok.


Update the Billing Account for Initial Project
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Navigate to *Accounting --> Billing Accounts*.
    - Report Filters
        - (Click) **Apply**
2. Navigate to account named `Account for Project sparrow`.
3. On to *Account* tab.
    - Name: `Sparrow Inc`
    - Client Contact Emails:
        - `client@example.edu`
        - `admin@example.edu`
    - Dimagi Contact Email: `user@example.org`
    - [x] Account is Active
    - [x] Is Customer Billing Account
    - Enterprise Admin Emails:
        - `admin@example.edu`
4. Navigate to *Subscriptions* tab.
    - (Click) **Edit** (should be only one existing subscription)
5. Navigate to *Upgrade/Downgrade* tab.
    - Edition: `Enterprise`
    - New Software Plan: `Sparrow Test Flight (v1)`
    - Note: `Upgrade.` *(or suitable upgrade note)*
    - (Click) **Change Subscription**


Add more projects to this subscription
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Add a new project.
    1. Navigate to *+ Add Project*
    2. Project Name: `song-sparrow`
    3. (Click) **Create Project**
2. Navigate to *Accounting --> Subscriptions*.
    - Report Filters
        - Project Space: `song-sparrow`
        - (Click) **Apply**
    - Locate subscription for the project (should be only one)
    - (Click) **Edit**
3. Navigate to the *Upgrade/Downgrade* tab.
    - Edition: `Enterprise`
    - New Software Plan: `Sparrow Test Flight (v1)`
    - Note: `Upgrade.` *(or suitable upgrade note)*
    - (Click) **Change Subscription**
4. Navigate to the *Subscription* tab.
    - Transfer Subscription To: `Sparrow Inc`
    - (Click) **Update Subscription**
5. Repeat...


Configure an Identity Provider
------------------------------

1. Navigate to *Accounting --> Identity Providers (SSO)*.
2. (Click) **+ Add New Identity Provider**

    - Billing Account Owner: `Sparrow Inc`
    - Public Name: `Azure AD for Sparrow Inc`
    - Slug for SP Endpoints: `sparrow`
    - (Click) **Create Identity Provider**

3. Navigate to *Authenticated Email Domains* tab.

    - @: `example.edu`
    - (Click) **Add Email Domain**

3. Navigate to *SSO Exempt Users* tab.

    - `admin@example.edu`
    - (Click) **Add User**

4. Navigate to *Identity Provider* tab.

    - [x] Allow Enterprise Admins to edit SSO Enterprise Settings
    - (Click) **Update Configuration**
    - (Click) *Edit Enterprise Settings* (below "Allow..." checkbox)
    - *Configure IdP settings...*
