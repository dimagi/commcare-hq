# Enterprise Admin Self-Service — Design

Date: 2026-04-16
Source spec: `enterprise-administration.md`

## Summary

Enterprise Administrators currently cannot view or change the list of
administrators for their account — they have to file an Ops ticket.
This design adds a self-service page to the Enterprise Console where
enterprise admins can see the current admin list and add or remove
admins themselves.

The underlying data (`BillingAccount.enterprise_admin_emails`) does not
change. This design is entirely a new UI and a small set of views that
mutate the existing field.

## Goals

- Enterprise admins can see the current list of admins for their
  account without opening an Ops ticket.
- Enterprise admins can add or remove admins self-service.
- Behavior stays consistent with the existing accounting-admin form
  (any valid email can be added) with one extra constraint for
  SSO-configured accounts.
- No changes to the data model.

## Non-Goals

- No email notifications (new admins are not emailed on addition).
- No audit trail beyond a single `logging.info` line per action.
- No changes to how SSO or billing accounts are provisioned.
- No REST/JSON API.
- No changes to the existing accounting-admin form used by Ops.
- No automatic rollout — the `FeatureRelease` toggle is enabled per
  domain on request until GA.

## Architecture

A new page in the Enterprise Console at a new URL and sidebar tab,
backed by three views on `BillingAccount.enterprise_admin_emails`:

| Component | Location | Role |
|---|---|---|
| `enterprise_admins` view (GET) | `corehq/apps/enterprise/views.py` | Renders the admin list and add form |
| `add_enterprise_admin` view (POST) | same | Validates and appends an email |
| `remove_enterprise_admin` view (POST) | same | Validates and removes an email |
| `EnterpriseAdminForm` | `corehq/apps/enterprise/forms.py` | Email-format and SSO-domain validation |
| `_get_sso_email_domains` helper | same or a `utils.py` | Union of active IdPs' authenticated email domains |
| `enterprise_admins.html` template | `corehq/apps/enterprise/templates/enterprise/` | Page markup (extends `hqwebapp/bootstrap5/base_section.html`) |
| `partials/enterprise_admins_table.html` | same directory | List rows + remove buttons, included from the main template |
| URL routes | `corehq/apps/enterprise/urls.py` | Three new patterns |
| Sidebar tab entry | `corehq/tabs/tabclasses.py` (near the existing `Enterprise Permissions` entry, ~line 1930) | Adds the tab to the `Manage Enterprise` section |

All three views are gated by `@require_enterprise_admin`, which
already admits both enterprise admins (per
`BillingAccount.has_enterprise_admin`) and users holding the
`ACCOUNTING_ADMIN` privilege.

### Relationship to `enterprise_permissions`

This design follows the same overall shape as the existing
`enterprise_permissions` feature: server-side form submissions,
full-page redirects, Django `messages` for feedback, a main template
that `includes` a list-table partial, and no HTMX/JSON.

Two intentional deviations from that feature's exact implementation:

- **Uses a Django `Form` class** (`EnterpriseAdminForm`) rather than
  inline validation in the view. `enterprise_permissions` validates
  with a single `in` check; this feature has three validation rules
  (format, uniqueness, SSO domain), and a `Form` keeps them in one
  place.
- **Passes the target email in the POST body** rather than capturing
  it in the URL path. `enterprise_permissions` does
  `remove/(?P<target_domain>[ \w-]+)/`; emails contain `@` and `.`
  which make URL-path encoding awkward, so the remove URL is
  `admins/remove/` and `email` is a hidden form input.

Another distinction: the `enterprise_permissions` tab is gated behind
`couch_user.is_superuser` and a feature toggle because the feature is
pre-GA. The new **Enterprise Administrators** tab is intended for
general release and should be gated **only** by whether the account
has an associated `BillingAccount` (and visibility relies on
`require_enterprise_admin` for the view itself).

## Views

Decorator stack (mirroring the `enterprise_permissions` neighbors):

- GET view: `@use_bootstrap5`, `@require_enterprise_admin`.
- POST views: `@require_enterprise_admin`, `@require_POST`.

### `enterprise_admins(request, domain)` — GET

- Resolves the `BillingAccount` for `domain`.
- Computes the SSO email-domain allowlist for the account (see
  "SSO domain check" below). If non-empty, passes it to the template so
  the add form can render a helptext hint.
- Builds a context via `get_page_context(...)` with
  `section=Section(_('Enterprise Console'), reverse('platform_overview', args=(domain,)))`
  so the page has correct breadcrumbs, page title, and navigation
  highlighting (matching `enterprise_permissions`).
- Renders the admin list (from `account.enterprise_admin_emails`), the
  add form, and any pending `messages`.

### `add_enterprise_admin(request, domain)` — POST

- Binds `EnterpriseAdminForm(request.POST, account=account)`.
- On validation success:
  - Append the lowercased email to `account.enterprise_admin_emails`.
  - `account.save()`.
  - `logging.info("Enterprise admin %s added to account %s by %s", ...)`.
  - `messages.success(...)`.
- On failure: `messages.error(...)` with the form error.
- Always redirects to `enterprise_admins`.

### `remove_enterprise_admin(request, domain)` — POST

Reads `email` from POST. All email comparisons are case-insensitive
(lowercased on both sides). `request.couch_user.username` is the acting
user's email — CommCare HQ's convention. In order:

1. If `email.lower() == request.couch_user.username.lower()`:
   `messages.error("You cannot remove yourself as an enterprise administrator.")`.
2. Else if `len(account.enterprise_admin_emails) <= 1`:
   `messages.error("An enterprise account must have at least one administrator.")`.
3. Else if `email` is not in the list (case-insensitive):
   `messages.error("That email is not an enterprise administrator.")`.
4. Otherwise: remove the matching entry (preserving the rest of the
   list), `save()`, `logging.info(...)`, `messages.success(...)`.

Always redirects to `enterprise_admins`.

## Form

```python
class EnterpriseAdminForm(forms.Form):
    email = forms.EmailField()

    def __init__(self, *args, account, **kwargs):
        super().__init__(*args, **kwargs)
        self.account = account

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if self.account.has_enterprise_admin(email):
            raise ValidationError(
                "This user is already an enterprise administrator."
            )
        sso_domains = _get_sso_email_domains(self.account)
        if sso_domains and email.split("@")[-1] not in sso_domains:
            raise ValidationError(
                "This email domain is not permitted. Enterprise admins "
                "must use an email at one of: %(domains)s",
                params={"domains": ", ".join(sorted(sso_domains))},
            )
        return email
```

Case handling: emails are stored lowercased for consistency. Existing
reads (e.g., `has_enterprise_admin`) already do case-insensitive
comparison, so this is backward-compatible with previously-stored
entries.

## SSO Domain Check

```python
def _get_sso_email_domains(account):
    idps = IdentityProvider.objects.filter(owner=account, is_active=True)
    return {d.lower() for idp in idps for d in idp.get_email_domains()}
```

Behavior:

- **No active IdP** → empty set → domain check skipped (permissive).
- **Active IdP with no `AuthenticatedEmailDomain` rows** → empty set →
  domain check skipped.
- **One or more active IdPs with domain rows** → union of all domains
  is the allowlist. The new admin's email domain must match one.

This mirrors the existing SSO login behavior of accepting any
configured authenticated email domain.

## Template & Navigation

`enterprise_admins.html`:

- Extends `hqwebapp/bootstrap5/base_section.html` (matching
  `enterprise_permissions.html`).
- Header: "Enterprise Administrators" rendered with `class="lead"`.
- Intro paragraph including the docs link from the source spec:
  *See [Enterprise Console | Enterprise Admins] for more on Enterprise
  Admins.* Styled as `class="help-block"`.
- Admin list: included partial
  `partials/enterprise_admins_table.html`, a Bootstrap 5 table
  (`class="table table-striped table-responsive"`) with one row per
  email. Each row's "Remove" column contains an inline form with
  `class="form form-horizontal disable-on-submit"`, CSRF token, a
  hidden `email` input, and a submit button. Destructive action uses a
  native `confirm()` dialog (via `onclick`) — no new JS module.
- Add form: `EnterpriseAdminForm` rendered with crispy-forms' `|crispy`
  filter (matching other Bootstrap 5 enterprise templates) and an
  "Add Administrator" submit button. If SSO domain restrictions apply,
  the permitted domains are shown as helptext under the email field.
- Django `messages` surfaced at the top (inherited from base).
- No new JS entry.

Navigation: add a new tab entry in `corehq/tabs/tabclasses.py`
alongside the existing `Enterprise Permissions` entry (~line 1930) in
the `Manage Enterprise` section. Shape:

```python
enterprise_views.append({
    'title': _("Enterprise Administrators"),
    'url': reverse("enterprise_admins", args=[self.domain]),
    'description': _("View and manage enterprise administrators for your account"),
    'subpages': [],
    'show_in_dropdown': False,
})
```

Gating: the entry is added only when the domain is associated with a
`BillingAccount` (typical `enterprise_views` gating — check what the
existing enterprise-console entries use in this file; don't add the
`is_superuser` / feature-toggle gates used by
`enterprise_permissions`, which are pre-GA-only).

## Safety Rails (Remove)

Two guards enforced in `remove_enterprise_admin` (user choice: both):

- **No self-removal.** Protects against an admin accidentally locking
  themselves out of the self-service page.
- **Cannot remove the last admin.** Protects against the exact
  situation this feature is designed to avoid: an account with zero
  enterprise admins has to open an Ops ticket.

Both produce inline error messages; neither is a silent no-op.

## Validation Rules (Add)

- Email must be a valid format (`EmailField`).
- Email must not already be in the list (case-insensitive).
- If the account has at least one active `IdentityProvider` with at
  least one `AuthenticatedEmailDomain`, the email's domain must be in
  that union.

No check that the email corresponds to an existing `WebUser`. This
matches the current accounting-admin form and preserves the
pre-provisioning workflow.

## Permissions

All three views are wrapped with `@require_enterprise_admin`. This
allows both:

- Users in `BillingAccount.enterprise_admin_emails` for the account.
- Users with the `ACCOUNTING_ADMIN` privilege (Ops).

Ops retains access for debugging; this is not a new restriction.

## Feature Gating (FeatureRelease Toggle)

The entire feature is gated behind a new `FeatureRelease` toggle,
registered in `corehq/toggles/__init__.py`:

```python
ENTERPRISE_ADMIN_SELF_SERVICE = FeatureRelease(
    'enterprise_admin_self_service',
    'Allow Enterprise Admins to view/add/remove other Enterprise Admins '
    'from the Enterprise Console',
    TAG_RELEASE,
    namespaces=[NAMESPACE_USER, NAMESPACE_DOMAIN],
    owner='Danny Roberts',
    help_link=(
        'https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/'
        '2143945885/Enterprise+Console#Enterprise-Admins'
    ),
)
```

Applied in two places:

1. **Views.** All three views stack
   `@toggles.ENTERPRISE_ADMIN_SELF_SERVICE.required_decorator()` above
   `@require_enterprise_admin`, so a direct URL hit on a non-enabled
   domain returns 404. (`required_decorator` raises `Http404` when
   disabled; if the user is a superuser it adds a message with a link
   to the toggle admin.)
2. **Sidebar tab entry.** The tab append in
   `corehq/tabs/tabclasses.py` is wrapped in
   `if toggles.ENTERPRISE_ADMIN_SELF_SERVICE.enabled_for_request(self._request):`
   so the link doesn't appear for domains where the toggle is off.

Default randomness: 0.0 (opt-in only via explicit enablement through
the toggle admin UI). No automatic rollout.

Both `NAMESPACE_USER` and `NAMESPACE_DOMAIN` are included so that a
team member can enable the toggle for their own user to preview the
view without requiring domain-level enablement — useful during
development and internal review. `required_decorator` /
`enabled_for_request` already check both namespaces in order.

Tests cover both states: a domain with the toggle enabled behaves as
specified above; a domain without it sees a 404 on every view and no
tab entry.

## Logging

On each successful add or remove, emit a single `logging.info` line
with the email affected, the account id, and the acting user. No
dedicated audit table, no `AuditCare` entry.

## Testing

Test file: `corehq/apps/enterprise/tests/test_enterprise_admins.py`
(pytest, `pytest-unmagic` fixtures per project convention).

**Fixtures:**

- A `BillingAccount` with `is_customer_billing_account=True`.
- A domain linked to the account.
- An existing enterprise-admin `WebUser`.
- A non-admin `WebUser`.
- An Ops `WebUser` with `ACCOUNTING_ADMIN` privilege.

**Toggle gating:**

- Toggle disabled for the domain → GET and both POST views return 404
  regardless of user role. Tab entry is absent.
- Remaining tests run with the toggle enabled for the test domain (via
  a `toggle_enabled` fixture or equivalent context manager).

**GET `enterprise_admins`:**

- Existing admin sees the list.
- Ops user sees the list.
- Non-admin gets 403 (or redirect, matching the decorator's behavior).

**`add_enterprise_admin`:**

- Valid new email → added (lowercased), redirect, success message.
- Duplicate (any case) → rejected with error.
- Invalid email format → rejected with error.
- SSO with `@foo.com`, adding `x@bar.com` → rejected.
- SSO with `@foo.com`, adding `x@foo.com` → accepted.
- SSO configured but no `AuthenticatedEmailDomain` rows → any valid
  email accepted.
- No SSO configured → any valid email accepted.
- Non-admin user POSTing → 403.
- `logging.info` emitted on success (assert via `caplog`).

**`remove_enterprise_admin`:**

- Normal remove (≥2 admins, not self) → removed, success.
- Remove self → rejected, list unchanged.
- Remove last admin → rejected, list unchanged.
- Remove email not in list → rejected.
- Non-admin user POSTing → 403.
- `logging.info` emitted on success.

## Out of Scope (future work if needed)

- Emailing newly-added admins.
- A dedicated audit trail.
- Requiring the added email to be an existing `WebUser`.
- HTMX-based partial updates.
- Lifting this restriction or giving Ops its own self-service path (Ops
  still uses the accounting-admin form).
