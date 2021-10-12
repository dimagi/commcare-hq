Architecture
==============

.. note::
    Everything related to SSO on CommCare HQ can be found in `corehq.apps.sso`

We have four primary models in our current SSO architecture, which is
based on the SAML 2.0 protocol.


IdentityProvider
----------------

The `IdentityProvider` model is responsible for storing all the certificate
information for a given Identity Provider (IdP), like Azure AD.

It is also linked to a `BillingAccount`. This link determines what project spaces
fall under the jurisdiction of the `IdentityProvider`. Any project space that has
a `Subscription` linked to the `BillingAccount` `owner` will automatically trust
the authentication information provided when a user is logged in with SSO.

.. note::
    While the project spaces subscribed under an `IdentityProvider`'s `BillingAccount`
    automatically trust the IdP's authentication of a user, a user who signs
    into CommCare HQ with SSO via that IdP will not automatically gain access
    to that project space.

    Authorization is still managed within CommCare HQ, and a user has to be
    invited to a project in order to have access to that project.

    However, SSO allows a user to login to HQ without the need for going through
    the usual sign-up process.


AuthenticatedEmailDomain
------------------------

A user on CommCare HQ is tied to an `IdentityProvider` based on the email domain
of their username. An **email domain** is the portion of an email address that
follows the `@` sign.

We tie email domains to `IdentityProviders` with the `AuthenticatedEmailDomain`
model.

If a user's email domain matches an `AuthenticatedEmailDomain`, during the
SSO login process they will be directed to the login workflow determined by
the active `IdentityProvider` associated with the `AuthenticatedEmailDomain`.

.. note::
    A user will only be forced to use SSO at login and sign up if
    `ENFORCE_SSO_LOGIN` in `localsettings` is set to `True`. Otherwise, they
    will be able to login with a username and password (if they created an
    account originally this way) or by visiting the `IdentityProvider`'s
    login URL (see the `get_login_url` method).


UserExemptFromSingleSignOn
--------------------------

Even if the `ENFORCE_SSO_LOGIN` flag in `localsettings` is set to `True`, we
still need to allow certain users the ability to always login to CommCare HQ
with their username and password. Generally, these users are one or two
enterprise admins (or other special users).

We require at least one user to be exempt from SSO login in the event that
the `IdentityProvider` is mis-configured or the certificate expires and a user
needs to gain access to their enterprise console to fix the situation.


TrustedIdentityProvider
-----------------------

Project spaces that are not associated with the `BillingAccount` tied to a given
`IdentityProvider` **do not** automatically trust users who have authenticated
with that `IdentityProvider`.

In order for a user to access a project space that is outside of their
`IdentityProvider`'s jurisdiction, an admin of that project space must first
agree to trust the `IdentityProvider` associated with that user.

This trust can either be established from the Web Users list or when inviting
a web user that is using SSO to the project.

Once a trust is established, any user authenticating with that `IdentityProvider`
who is also a member of the project space can now access the project space as if
they had logged in with a username and password.
