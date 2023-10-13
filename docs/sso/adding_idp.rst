Adding a New Identity Provider Type
===================================

.. note::
    These instructions are for adding a new Identity Provider Type / Service (e.g. Okta, OneLogin, Azure AD, etc.).
    To add a new active Identity Provider, you can follow the steps in Local Setup or in our SSO Enterprise Guides
    on Confluence.


Before Beginning
----------------

What Protocol will be used?
~~~~~~~~~~~~~~~~~~~~~~~~~~~

As of the writing of this documentation, there are only two protocols used for SSO (`SAML` and `OIDC`/`OAuth2`). We
support both. Of the two, `OIDC` is generally easier to implement than `SAML` but the Identity Provider you wish to add
may have a preference for one over the other. For instance, Azure AD's workflows clearly prefer `SAML`.

Another thing to note about protocol choice is that `OIDC` is generally easier to test locally, while `SAML` requires
testing on a publicly accessible machine like `staging`.


Steps for Adding the IdP Type
-----------------------------

1. Make model changes and add migrations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You should add the new `IdentityProviderType` to `corehq.apps.sso.models` and create a migration for the `sso` app.
Then you should add the `IdentityProviderType` to the appropriate protocol in `IdentityProviderProtocol`'s
`get_supported_types()` method.


2. Test out the new provider type locally or on staging
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note::
    It is important to consider how we will support this new Identity Provider in the long term. Once a new IdP Type is
    added, we will need to ensure that we can properly do regression tests during QA for any changed SSO code. In order
    to do this, it's best to ensure that we are able to setup a developer/test account with the Identity Provider.

You can follow the steps in Local Setup of this section to add the new Identity Provider. The biggest challenge
will likely be determining where to obtain all the requirements necessary to set up the connection in the Provider's UI.
For instance, with `OIDC` you need to take note of where the `Issuer URL`, `Client ID`, and `Client Secret`
are in the UI. Some Identity Providers are more challenging to find these than others!

.. note::
    Pay attention to the language and field order of our forms in comparison with what a user might encounter in the
    Identity Provider's UI. It might be appropriate to change the order of certain fields, sections and/or language
    for the Enterprise Admin SSO forms to match what the user sees in their provider's UI.

Now you can activate the `IdentityProvider`. It's easiest to use `dimagi.org` as the email domain to map users to,
as this is a domain alias for our email accounts (e.g. emails from foo@dimagi.com will also go to foo@dimagi.org).
Please do NOT use `dimagi.com`!

If you are doing tests on staging, take note you will likely have to deactivate and remove the email domain from
another Identity Provider (like Azure AD or One Login) that previously used this email domain for QA. Also, if you plan
to test on staging, the `Dimagi SSO` enterprise account mapped to the `dimagi-sso-1`, `dimagi-sso-2`, and `dimagi-sso-3`
domains will be ready to test this new IdP.

3. Log in as an SSO user
~~~~~~~~~~~~~~~~~~~~~~~~

With the new `IdentityProvider` configured and active, you can now log in as an SSO user from the login screen. During this
test you can identify any additional code changes that need to be made. For instance, a new `OIDC` IdentityProvider might
not send the expected `user_data` through, so changes might need to be made where that data is accessed
(see `corehq.apps.sso.views.oidc`). A new `SAML` provider might require changes to `get_saml2_config()` that are specific
to its requirements (see `corehq.apps.sso.configuration`), but make sure that the existing `IdentityProvider`'s configurations
remain unchanged.

4. Walk through workflows with our technical writer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once you have verified that your changes are correctly logging in users and not throwing any errors, it's time to proceed
to setting up a meeting with a technical writer so that the setup process with the new Identity Provider can be
appropriately documented on Confluence for our Enterprise partners. Another goal of this meeting should be to document
any steps for the QA team to follow when setting up the Identity Provider.

5. Initiate QA
~~~~~~~~~~~~~~

Now it's time to initiate QA on `staging` for the new `IdentityProviderType`. In your QA request, be sure to include the
new setup information as documented by our technical writer and any credentials or sign up steps for QA to obtain a
developer account.

6. Determine whether a penetration test is required
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If the only code changes required were language updates and adding a new `IdentityProviderType` this step can be skipped.
However, if you needed to update something like the `SAML` configuration, code in the `SSOBackend`, or
areas where authentication / user verification currently happens, then it might be a good idea to schedule a penetration
test with our security firm.

7. Pilot test with the Enterprise Partner on Production
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once QA is complete and our security firm has verified that no vulnerabilities exist (if applicable), it is time to
onboard our Enterprise Partner in the production environment. This will involve using the Login Enforcement option and
the "SSO Test Users" feature that you will find in the `Edit Identity Provider` form. When Login Enforcement is set to
`Test`, then only the `SSO Test Users` listed will be required to login with SSO from the homepage. This is a great way
for the Enterprise partner to test their setup and processes without immediately forcing all users under their email
domain to sign in with SSO.
