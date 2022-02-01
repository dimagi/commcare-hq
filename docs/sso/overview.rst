General Overview
================

What is SSO?
------------

Single sign-on (SSO) defines a scheme for authenticating a user with a single
username and password across several related, but independent, applications.

.. note::
    Pay attention the difference between **authentication** and **authorization**.

    **Authentication** is the process used to identify whether the credentials a user provides are valid

    **Authorization** is the process used to determine the set of permissions to grant a user
    that determines what they can view or edit on the system.


Types of Protocols
------------------

Two of the most common types of protocols for SSO in web applications are
OIDC (OpenID Connect) and SAML (Security Assertion Markup Language).

CommCare HQ currently uses SAML 2.0 to handle SSO handshake procedures. It is
a very mature and secure protocol and is the standard for most enterprise
applications.

OIDC is an authentication layer built on top of OAuth 2.0. When compared to SAML
it is considered a less mature protocol, but offers the pros of being lightweight
and mobile + API friendly. However, not all Identity Providers support OIDC,
while all of them likely support SAML. In the future we may consider OIDC
support if necessary.


How Does SSO Work?
------------------

SSO is based on a trust relationship between an application, the Service
Provider (SP) and an Identity Provider (IdP). CommCare HQ in this case acts as
the Service Provider.

To create this trust, x509 certificates are exchanged between the IdP and the SP.
The IdP uses the certificate to securely sign (and sometimes encrypt) identity
information that it sends back to the SP in the form of a token. Because the SP
knows the IdP's public certificate, it knows that the information it receives
is coming from a trusted source and knows it's safe to login the user based on
the username that it receives in the token.
