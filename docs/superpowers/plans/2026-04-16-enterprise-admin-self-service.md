# Enterprise Admin Self-Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Enterprise Admins view, add, and remove other Enterprise Admins for their account from the Enterprise Console, gated behind a `FeatureRelease` toggle, so the workflow no longer requires a CC Ops ticket.

**Architecture:** Three server-side Django views (GET list, POST add, POST remove) on a new URL in `corehq.apps.enterprise`, mutating the existing `BillingAccount.enterprise_admin_emails` field. Mirrors the existing `enterprise_permissions` feature (server-side forms, full-page redirects, Django `messages`). A new `FeatureRelease` toggle gates views and sidebar.

**Tech Stack:** Django, Bootstrap 5, crispy-forms, `corehq/toggles`, `pytest`+`Django TestCase`, the existing `@require_enterprise_admin` decorator, `BillingAccount`, `IdentityProvider`.

**Reference spec:** `docs/superpowers/specs/2026-04-16-enterprise-admin-self-service-design.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `corehq/toggles/__init__.py` | modify | Register `ENTERPRISE_ADMIN_SELF_SERVICE` `FeatureRelease` toggle |
| `corehq/apps/enterprise/forms.py` | modify | Add `_get_sso_email_domains` helper and `EnterpriseAdminForm` |
| `corehq/apps/enterprise/views.py` | modify | Add `enterprise_admins`, `add_enterprise_admin`, `remove_enterprise_admin` views |
| `corehq/apps/enterprise/urls.py` | modify | Add three URL patterns |
| `corehq/apps/enterprise/templates/enterprise/enterprise_admins.html` | create | Main page template (list + add form) |
| `corehq/apps/enterprise/templates/enterprise/partials/enterprise_admins_table.html` | create | List-table partial |
| `corehq/tabs/tabclasses.py` | modify | Register sidebar tab entry |
| `corehq/apps/enterprise/tests/test_enterprise_admins.py` | create | All tests for this feature |

---

## Task 1: Register the `ENTERPRISE_ADMIN_SELF_SERVICE` toggle

**Files:**
- Modify: `corehq/toggles/__init__.py` (append near other `FeatureRelease` declarations)

- [ ] **Step 1: Add the toggle declaration**

Append the following to `corehq/toggles/__init__.py`, after the last existing toggle declaration (use `grep -n "^[A-Z_]* =" corehq/toggles/__init__.py | tail -1` to find the bottom; we want to add near the end of the declarations, alphabetically location does not matter for this codebase):

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

- [ ] **Step 2: Sanity-check it loads**

Run:
```
uv run python -c "from corehq import toggles; print(toggles.ENTERPRISE_ADMIN_SELF_SERVICE.slug)"
```
Expected output: `enterprise_admin_self_service`

- [ ] **Step 3: Commit**

```
git add corehq/toggles/__init__.py
git commit -m "Add ENTERPRISE_ADMIN_SELF_SERVICE feature release toggle"
```

---

## Task 2: Add `_get_sso_email_domains` helper

The form will need the union of authenticated email domains across all active `IdentityProvider`s attached to the billing account. Build it test-first.

**Files:**
- Modify: `corehq/apps/enterprise/forms.py`
- Test: `corehq/apps/enterprise/tests/test_enterprise_admins.py` (create)

- [ ] **Step 1: Create the test file with a failing test for the helper**

Create `corehq/apps/enterprise/tests/test_enterprise_admins.py`:

```python
from django.test import TestCase

from corehq.apps.accounting.tests import generator as accounting_gen
from corehq.apps.enterprise.forms import _get_sso_email_domains
from corehq.apps.sso.models import (
    AuthenticatedEmailDomain,
    IdentityProvider,
    IdentityProviderType,
)


def _make_idp(account, slug, is_active=True, domains=None):
    idp = IdentityProvider.objects.create(
        owner=account,
        slug=slug,
        name=slug,
        idp_type=IdentityProviderType.ENTRA_ID,
        is_active=is_active,
    )
    for d in (domains or []):
        AuthenticatedEmailDomain.objects.create(
            email_domain=d, identity_provider=idp,
        )
    return idp


class GetSsoEmailDomainsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.account = accounting_gen.billing_account(
            'admin@example.com', 'contact@example.com',
            is_customer_account=True,
        )

    def test_no_idp_returns_empty_set(self):
        self.assertEqual(_get_sso_email_domains(self.account), set())

    def test_idp_without_domain_rows_returns_empty_set(self):
        _make_idp(self.account, slug='idp-a')
        self.assertEqual(_get_sso_email_domains(self.account), set())

    def test_single_idp_with_domains(self):
        _make_idp(self.account, slug='idp-b', domains=['foo.com', 'bar.com'])
        self.assertEqual(
            _get_sso_email_domains(self.account),
            {'foo.com', 'bar.com'},
        )

    def test_multiple_active_idps_union_domains(self):
        _make_idp(self.account, slug='idp-c', domains=['foo.com'])
        _make_idp(self.account, slug='idp-d', domains=['baz.com'])
        self.assertEqual(
            _get_sso_email_domains(self.account),
            {'foo.com', 'baz.com'},
        )

    def test_inactive_idp_is_excluded(self):
        _make_idp(self.account, slug='idp-e', is_active=False,
                  domains=['inactive.com'])
        _make_idp(self.account, slug='idp-f', domains=['active.com'])
        self.assertEqual(
            _get_sso_email_domains(self.account),
            {'active.com'},
        )

    def test_domains_returned_lowercased(self):
        _make_idp(self.account, slug='idp-g', domains=['Mixed.Case.COM'])
        self.assertEqual(
            _get_sso_email_domains(self.account),
            {'mixed.case.com'},
        )
```

- [ ] **Step 2: Run the test and confirm it fails**

Run:
```
uv run pytest --reusedb=1 corehq/apps/enterprise/tests/test_enterprise_admins.py::GetSsoEmailDomainsTests -v
```
Expected: `ImportError` — `_get_sso_email_domains` does not exist in `corehq/apps/enterprise/forms.py`.

- [ ] **Step 3: Implement the helper**

Add to the top of `corehq/apps/enterprise/forms.py` (after existing imports, add the new imports near the top; the helper itself goes above the existing `EnterpriseSettingsForm` class):

New imports (add to the existing import block):
```python
from corehq.apps.sso.models import IdentityProvider
```

Helper (add above `class EnterpriseSettingsForm(...)`):
```python
def _get_sso_email_domains(account):
    """
    Returns the set of lowercased email domains that are configured as
    authenticated SSO email domains for any active identity provider
    associated with the given BillingAccount. Empty set means no
    SSO-based domain restriction applies.
    """
    idps = IdentityProvider.objects.filter(owner=account, is_active=True)
    return {d.lower() for idp in idps for d in idp.get_email_domains()}
```

- [ ] **Step 4: Run the test and confirm it passes**

Run:
```
uv run pytest --reusedb=1 corehq/apps/enterprise/tests/test_enterprise_admins.py::GetSsoEmailDomainsTests -v
```
Expected: all six tests pass.

- [ ] **Step 5: Commit**

```
git add corehq/apps/enterprise/forms.py corehq/apps/enterprise/tests/test_enterprise_admins.py
git commit -m "Add _get_sso_email_domains helper for enterprise admin form"
```

---

## Task 3: Add `EnterpriseAdminForm`

**Files:**
- Modify: `corehq/apps/enterprise/forms.py`
- Modify: `corehq/apps/enterprise/tests/test_enterprise_admins.py`

- [ ] **Step 1: Append form tests to the existing test file**

Append to `corehq/apps/enterprise/tests/test_enterprise_admins.py`:

```python
from corehq.apps.enterprise.forms import EnterpriseAdminForm


class EnterpriseAdminFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.account = accounting_gen.billing_account(
            'admin@example.com', 'contact@example.com',
            is_customer_account=True,
        )
        cls.account.enterprise_admin_emails = ['existing@example.com']
        cls.account.save()

    def _bind(self, email):
        return EnterpriseAdminForm({'email': email}, account=self.account)

    def test_valid_email_passes(self):
        form = self._bind('new@example.com')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['email'], 'new@example.com')

    def test_email_is_lowercased(self):
        form = self._bind('MixedCase@Example.com')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['email'], 'mixedcase@example.com')

    def test_invalid_email_format_rejected(self):
        form = self._bind('not-an-email')
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_duplicate_email_rejected(self):
        form = self._bind('existing@example.com')
        self.assertFalse(form.is_valid())
        self.assertIn('already', form.errors['email'][0])

    def test_duplicate_is_case_insensitive(self):
        form = self._bind('EXISTING@example.com')
        self.assertFalse(form.is_valid())

    def test_no_sso_allows_any_domain(self):
        form = self._bind('someone@anywhere.com')
        self.assertTrue(form.is_valid(), form.errors)

    def test_sso_restricts_email_domain(self):
        _make_idp(self.account, slug='idp-sso', domains=['corp.com'])
        form = self._bind('someone@other.com')
        self.assertFalse(form.is_valid())
        self.assertIn('not permitted', form.errors['email'][0])

    def test_sso_allows_matching_domain(self):
        _make_idp(self.account, slug='idp-sso-ok', domains=['corp.com'])
        form = self._bind('someone@corp.com')
        self.assertTrue(form.is_valid(), form.errors)

    def test_sso_without_domain_rows_allows_any_email(self):
        _make_idp(self.account, slug='idp-no-domains')
        form = self._bind('someone@unrestricted.com')
        self.assertTrue(form.is_valid(), form.errors)
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run:
```
uv run pytest --reusedb=1 corehq/apps/enterprise/tests/test_enterprise_admins.py::EnterpriseAdminFormTests -v
```
Expected: `ImportError` — `EnterpriseAdminForm` does not exist.

- [ ] **Step 3: Implement the form**

Add to `corehq/apps/enterprise/forms.py` immediately below the `_get_sso_email_domains` helper:

```python
class EnterpriseAdminForm(forms.Form):
    email = forms.EmailField(label=gettext_lazy("Email"))

    def __init__(self, *args, account, **kwargs):
        super().__init__(*args, **kwargs)
        self.account = account

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if self.account.has_enterprise_admin(email):
            raise ValidationError(
                _("This user is already an enterprise administrator."),
            )
        sso_domains = _get_sso_email_domains(self.account)
        if sso_domains and email.rsplit("@", 1)[-1] not in sso_domains:
            raise ValidationError(
                _(
                    "This email domain is not permitted. Enterprise admins "
                    "must use an email at one of: %(domains)s"
                ),
                params={"domains": ", ".join(sorted(sso_domains))},
            )
        return email
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run:
```
uv run pytest --reusedb=1 corehq/apps/enterprise/tests/test_enterprise_admins.py::EnterpriseAdminFormTests -v
```
Expected: all nine tests pass.

- [ ] **Step 5: Commit**

```
git add corehq/apps/enterprise/forms.py corehq/apps/enterprise/tests/test_enterprise_admins.py
git commit -m "Add EnterpriseAdminForm"
```

---

## Task 4: GET view, URL, and minimal template

Wire up the read-only list page. Subsequent tasks add mutation.

**Files:**
- Modify: `corehq/apps/enterprise/views.py`
- Modify: `corehq/apps/enterprise/urls.py`
- Create: `corehq/apps/enterprise/templates/enterprise/enterprise_admins.html`
- Create: `corehq/apps/enterprise/templates/enterprise/partials/enterprise_admins_table.html`
- Modify: `corehq/apps/enterprise/tests/test_enterprise_admins.py`

- [ ] **Step 1: Append view tests to the test file**

Append to `corehq/apps/enterprise/tests/test_enterprise_admins.py`:

```python
from datetime import date, timedelta

from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse

from corehq import toggles
from corehq.apps.accounting.tests.generator import generate_domain_subscription
from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser


class _EnterpriseAdminViewTestBase(TestCase):
    """Shared fixture: a customer billing account, a linked domain, an
    existing enterprise admin WebUser, and the toggle enabled for that
    domain. Subclasses add behavior-specific fixtures."""

    @classmethod
    def setUpTestData(cls):
        cls.domain_name = 'ent-admin-test'
        cls.domain = create_domain(cls.domain_name)
        cls.account = accounting_gen.billing_account(
            'admin@example.com', 'contact@example.com',
            is_customer_account=True,
        )
        plan_version = accounting_gen.subscribable_plan_version(
            edition=SoftwarePlanEdition.ENTERPRISE,
        )
        start = date.today()
        generate_domain_subscription(
            cls.account, cls.domain,
            date_start=start,
            date_end=start + timedelta(days=365),
            plan_version=plan_version,
            is_active=True,
        )
        cls.admin_user = WebUser.create(
            cls.domain_name, 'admin-user@example.com', 'pw',
            None, None, is_admin=True,
        )
        cls.account.enterprise_admin_emails = [cls.admin_user.username]
        cls.account.save()

    def setUp(self):
        toggles.ENTERPRISE_ADMIN_SELF_SERVICE.set(
            self.domain_name, True, toggles.NAMESPACE_DOMAIN,
        )
        self.addCleanup(
            toggles.ENTERPRISE_ADMIN_SELF_SERVICE.set,
            self.domain_name, False, toggles.NAMESPACE_DOMAIN,
        )
        self.client = Client()
        self.client.login(
            username=self.admin_user.username, password='pw',
        )

    @classmethod
    def tearDownClass(cls):
        cls.admin_user.delete(cls.domain_name, deleted_by=None)
        cls.domain.delete()
        super().tearDownClass()

    @property
    def list_url(self):
        return reverse('enterprise_admins', args=[self.domain_name])


class EnterpriseAdminsGetViewTests(_EnterpriseAdminViewTestBase):

    def test_admin_can_load_page(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.admin_user.username)

    def test_toggle_disabled_returns_404(self):
        toggles.ENTERPRISE_ADMIN_SELF_SERVICE.set(
            self.domain_name, False, toggles.NAMESPACE_DOMAIN,
        )
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 404)

    def test_non_admin_user_gets_404(self):
        outsider = WebUser.create(
            self.domain_name, 'outsider@example.com', 'pw',
            None, None,
        )
        self.addCleanup(outsider.delete, self.domain_name, deleted_by=None)
        self.client.login(username=outsider.username, password='pw')
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run:
```
uv run pytest --reusedb=1 corehq/apps/enterprise/tests/test_enterprise_admins.py::EnterpriseAdminsGetViewTests -v
```
Expected: `NoReverseMatch` — `enterprise_admins` URL is not defined.

- [ ] **Step 3: Add the URL patterns (placeholders for all three routes)**

Edit `corehq/apps/enterprise/urls.py`. Two edits:

1. The file already has a `from corehq.apps.enterprise.views import (...)` block with names sorted alphabetically. Add these three new names into that block, keeping the alphabetical sort (`add_enterprise_admin` near the top, `enterprise_admins` with the other `enterprise_*` names, `remove_enterprise_admin` near the existing `remove_enterprise_permissions_domain`):

```python
    add_enterprise_admin,
    # ... existing names here ...
    enterprise_admins,
    # ... existing names here ...
    remove_enterprise_admin,
```

2. Add inside `domain_specific = [...]` (place the new entries next to the existing `permissions/` routes for locality):
```python
    url(r'^admins/$', enterprise_admins, name='enterprise_admins'),
    url(r'^admins/add/$', add_enterprise_admin, name='add_enterprise_admin'),
    url(r'^admins/remove/$', remove_enterprise_admin,
        name='remove_enterprise_admin'),
```

- [ ] **Step 4: Add the three view stubs**

Edit `corehq/apps/enterprise/views.py`. Add the following at the top of the file with the other `import` statements:

```python
import logging
```

Add these to the existing `from corehq...` import block (re-using the existing import style in the file):

```python
from corehq import toggles
from corehq.apps.enterprise.forms import (
    EnterpriseAdminForm,
    _get_sso_email_domains,
)
```

Near the top of the module (above the first view function), add the module-level logger:

```python
enterprise_admin_logger = logging.getLogger(__name__)
```

Add these three view functions to the file (near the other `enterprise_*` view functions, e.g. after `remove_enterprise_permissions_domain`):

```python
@use_bootstrap5
@toggles.ENTERPRISE_ADMIN_SELF_SERVICE.required_decorator()
@require_enterprise_admin
def enterprise_admins(request, domain):
    account = request.account
    sso_domains = _get_sso_email_domains(account)
    form = EnterpriseAdminForm(account=account)
    context = get_page_context(
        page_url=reverse('enterprise_admins', args=(domain,)),
        page_title=_('Enterprise Administrators'),
        page_name=_('Enterprise Administrators'),
        domain=domain,
        section=Section(
            _('Enterprise Console'),
            reverse('platform_overview', args=(domain,)),
        ),
    )
    context.update({
        'admin_emails': sorted(account.enterprise_admin_emails),
        'sso_domains': sorted(sso_domains),
        'form': form,
        'current_user_email': request.couch_user.username,
    })
    return render(request, 'enterprise/enterprise_admins.html', context)


@toggles.ENTERPRISE_ADMIN_SELF_SERVICE.required_decorator()
@require_enterprise_admin
@require_POST
def add_enterprise_admin(request, domain):
    return HttpResponseRedirect(
        reverse('enterprise_admins', args=[domain]),
    )


@toggles.ENTERPRISE_ADMIN_SELF_SERVICE.required_decorator()
@require_enterprise_admin
@require_POST
def remove_enterprise_admin(request, domain):
    return HttpResponseRedirect(
        reverse('enterprise_admins', args=[domain]),
    )
```

- [ ] **Step 5: Create the main template**

Create `corehq/apps/enterprise/templates/enterprise/enterprise_admins.html`:

```django
{% extends 'hqwebapp/bootstrap5/base_section.html' %}
{% load crispy_forms_tags %}
{% load i18n %}
{% load hq_shared_tags %}

{% js_entry "hqwebapp/js/bootstrap5/widgets" %}

{% block page_content %}
  <p class="lead">
    {% trans "Enterprise Administrators" %}
  </p>

  <p class="help-block">
    {% blocktrans trimmed %}
      Enterprise Administrators can manage subscriptions, billing, and
      account-level settings for all project spaces in this account.
      See
      <a href="https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143945885/Enterprise+Console#Enterprise-Admins"
         target="_blank">Enterprise Console | Enterprise Admins</a>
      for more on Enterprise Admins.
    {% endblocktrans %}
  </p>

  {% include "enterprise/partials/enterprise_admins_table.html" %}

  <hr>

  <h3>{% trans "Add an Administrator" %}</h3>
  {% if sso_domains %}
    <p class="help-block">
      {% blocktrans trimmed with domains=sso_domains|join:", " %}
        This account uses SSO. New administrators must use an email at
        one of: {{ domains }}.
      {% endblocktrans %}
    </p>
  {% endif %}
  <form method="POST" action="{% url 'add_enterprise_admin' domain %}"
        class="form form-horizontal">
    {% csrf_token %}
    {{ form|crispy }}
    <button type="submit" class="btn btn-primary">
      {% trans "Add Administrator" %}
    </button>
  </form>
{% endblock %}
```

- [ ] **Step 6: Create the partial template**

Create `corehq/apps/enterprise/templates/enterprise/partials/enterprise_admins_table.html`:

```django
{% load i18n %}

{% if admin_emails %}
  <table class="table table-striped table-responsive">
    <thead>
      <tr>
        <th>{% trans "Email" %}</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {% for email in admin_emails %}
        <tr>
          <td class="col-md-10">{{ email }}</td>
          <td class="col-md-2">
            <form method="POST"
                  action="{% url 'remove_enterprise_admin' domain %}"
                  class="form form-horizontal disable-on-submit"
                  onsubmit="return confirm('{% blocktrans with email=email %}Remove {{ email }} as an enterprise administrator?{% endblocktrans %}');">
              {% csrf_token %}
              <input type="hidden" name="email" value="{{ email }}"/>
              <button type="submit" class="btn btn-outline-danger">
                <i class="fa fa-ban"></i> {% trans "Remove" %}
              </button>
            </form>
          </td>
        </tr>
      {% endfor %}
    </tbody>
  </table>
{% else %}
  <div class="alert alert-warning">
    {% trans "There are no enterprise administrators configured for this account." %}
  </div>
{% endif %}
```

- [ ] **Step 7: Run the GET view tests and confirm they pass**

Run:
```
uv run pytest --reusedb=migrate corehq/apps/enterprise/tests/test_enterprise_admins.py::EnterpriseAdminsGetViewTests -v
```
Expected: all three tests pass. (Use `--reusedb=migrate` once to pick up any migrations from the fixtures; subsequent runs can use `--reusedb=1`.)

- [ ] **Step 8: Commit**

```
git add corehq/apps/enterprise/views.py corehq/apps/enterprise/urls.py \
        corehq/apps/enterprise/templates/enterprise/enterprise_admins.html \
        corehq/apps/enterprise/templates/enterprise/partials/enterprise_admins_table.html \
        corehq/apps/enterprise/tests/test_enterprise_admins.py
git commit -m "Add enterprise admins list page"
```

---

## Task 5: Implement `add_enterprise_admin`

**Files:**
- Modify: `corehq/apps/enterprise/views.py`
- Modify: `corehq/apps/enterprise/tests/test_enterprise_admins.py`

- [ ] **Step 1: Append add-view tests**

Append to `corehq/apps/enterprise/tests/test_enterprise_admins.py`:

```python
class AddEnterpriseAdminViewTests(_EnterpriseAdminViewTestBase):

    @property
    def add_url(self):
        return reverse('add_enterprise_admin', args=[self.domain_name])

    def _reload_account(self):
        self.account.refresh_from_db()
        return self.account

    def test_add_valid_email_appends_lowercased(self):
        response = self.client.post(
            self.add_url, {'email': 'NewAdmin@Example.com'},
        )
        self.assertRedirects(response, self.list_url)
        account = self._reload_account()
        self.assertIn('newadmin@example.com', account.enterprise_admin_emails)

    def test_add_duplicate_email_is_rejected(self):
        response = self.client.post(
            self.add_url, {'email': self.admin_user.username},
        )
        self.assertRedirects(response, self.list_url)
        account = self._reload_account()
        count = account.enterprise_admin_emails.count(self.admin_user.username)
        self.assertEqual(count, 1)
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('already' in m for m in msgs))

    def test_add_invalid_format_is_rejected(self):
        response = self.client.post(self.add_url, {'email': 'not-an-email'})
        self.assertRedirects(response, self.list_url)
        account = self._reload_account()
        self.assertNotIn('not-an-email', account.enterprise_admin_emails)

    def test_add_respects_sso_domain_restriction(self):
        _make_idp(self.account, slug='idp-sso', domains=['corp.com'])
        response = self.client.post(
            self.add_url, {'email': 'x@other.com'},
        )
        self.assertRedirects(response, self.list_url)
        account = self._reload_account()
        self.assertNotIn('x@other.com', account.enterprise_admin_emails)
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('not permitted' in m for m in msgs))

    def test_add_logs_info(self):
        with self.assertLogs(
            'corehq.apps.enterprise.views', level='INFO'
        ) as cap:
            self.client.post(
                self.add_url, {'email': 'logger@example.com'},
            )
        self.assertTrue(
            any('logger@example.com' in line for line in cap.output),
        )

    def test_add_toggle_disabled_returns_404(self):
        toggles.ENTERPRISE_ADMIN_SELF_SERVICE.set(
            self.domain_name, False, toggles.NAMESPACE_DOMAIN,
        )
        response = self.client.post(
            self.add_url, {'email': 'blocked@example.com'},
        )
        self.assertEqual(response.status_code, 404)
        account = self._reload_account()
        self.assertNotIn('blocked@example.com', account.enterprise_admin_emails)
```

- [ ] **Step 2: Run the add tests and confirm they fail**

Run:
```
uv run pytest --reusedb=1 corehq/apps/enterprise/tests/test_enterprise_admins.py::AddEnterpriseAdminViewTests -v
```
Expected: tests fail — the current `add_enterprise_admin` is a stub redirect; no-op on the account.

- [ ] **Step 3: Replace the `add_enterprise_admin` stub with the real implementation**

In `corehq/apps/enterprise/views.py`, replace the stub for `add_enterprise_admin` with:

```python
@toggles.ENTERPRISE_ADMIN_SELF_SERVICE.required_decorator()
@require_enterprise_admin
@require_POST
def add_enterprise_admin(request, domain):
    account = request.account
    redirect = HttpResponseRedirect(
        reverse('enterprise_admins', args=[domain]),
    )
    form = EnterpriseAdminForm(request.POST, account=account)
    if not form.is_valid():
        error = form.errors.get('email', [_('Invalid request.')])[0]
        messages.error(request, error)
        return redirect
    email = form.cleaned_data['email']
    account.enterprise_admin_emails = list(account.enterprise_admin_emails) + [email]
    account.save()
    enterprise_admin_logger.info(
        "Enterprise admin %s added to account %s by %s",
        email, account.id, request.couch_user.username,
    )
    messages.success(
        request,
        _("%(email)s has been added as an enterprise administrator.")
        % {'email': email},
    )
    return redirect
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run:
```
uv run pytest --reusedb=1 corehq/apps/enterprise/tests/test_enterprise_admins.py::AddEnterpriseAdminViewTests -v
```
Expected: all six tests pass.

- [ ] **Step 5: Commit**

```
git add corehq/apps/enterprise/views.py \
        corehq/apps/enterprise/tests/test_enterprise_admins.py
git commit -m "Implement add_enterprise_admin view"
```

---

## Task 6: Implement `remove_enterprise_admin`

**Files:**
- Modify: `corehq/apps/enterprise/views.py`
- Modify: `corehq/apps/enterprise/tests/test_enterprise_admins.py`

- [ ] **Step 1: Append remove-view tests**

Append to `corehq/apps/enterprise/tests/test_enterprise_admins.py`:

```python
class RemoveEnterpriseAdminViewTests(_EnterpriseAdminViewTestBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.second_admin = WebUser.create(
            cls.domain_name, 'second-admin@example.com', 'pw',
            None, None, is_admin=True,
        )
        cls.account.enterprise_admin_emails = [
            cls.admin_user.username,
            cls.second_admin.username,
        ]
        cls.account.save()

    @classmethod
    def tearDownClass(cls):
        cls.second_admin.delete(cls.domain_name, deleted_by=None)
        super().tearDownClass()

    @property
    def remove_url(self):
        return reverse('remove_enterprise_admin', args=[self.domain_name])

    def _reload_account(self):
        self.account.refresh_from_db()
        return self.account

    def test_remove_peer_admin(self):
        response = self.client.post(
            self.remove_url, {'email': self.second_admin.username},
        )
        self.assertRedirects(response, self.list_url)
        account = self._reload_account()
        self.assertNotIn(
            self.second_admin.username, account.enterprise_admin_emails,
        )
        self.assertIn(
            self.admin_user.username, account.enterprise_admin_emails,
        )

    def test_remove_self_is_blocked(self):
        response = self.client.post(
            self.remove_url, {'email': self.admin_user.username},
        )
        self.assertRedirects(response, self.list_url)
        account = self._reload_account()
        self.assertIn(
            self.admin_user.username, account.enterprise_admin_emails,
        )
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('yourself' in m for m in msgs))

    def test_remove_last_admin_is_blocked(self):
        # Reduce the admin list to a single entry (the current user, so
        # require_enterprise_admin still passes), then try to remove a
        # different email. The self-removal guard passes (target != self),
        # then the last-admin guard trips.
        self.account.enterprise_admin_emails = [self.admin_user.username]
        self.account.save()

        response = self.client.post(
            self.remove_url, {'email': 'someone-else@example.com'},
        )
        self.assertRedirects(response, self.list_url)
        account = self._reload_account()
        self.assertEqual(
            account.enterprise_admin_emails, [self.admin_user.username],
        )
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('at least one' in m for m in msgs))

    def test_remove_unknown_email_reports_error(self):
        response = self.client.post(
            self.remove_url, {'email': 'ghost@example.com'},
        )
        self.assertRedirects(response, self.list_url)
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(
            any('is not an enterprise administrator' in m for m in msgs),
        )

    def test_remove_is_case_insensitive(self):
        response = self.client.post(
            self.remove_url,
            {'email': self.second_admin.username.upper()},
        )
        self.assertRedirects(response, self.list_url)
        account = self._reload_account()
        self.assertNotIn(
            self.second_admin.username, account.enterprise_admin_emails,
        )

    def test_remove_logs_info(self):
        with self.assertLogs(
            'corehq.apps.enterprise.views', level='INFO',
        ) as cap:
            self.client.post(
                self.remove_url, {'email': self.second_admin.username},
            )
        self.assertTrue(
            any(self.second_admin.username in line for line in cap.output),
        )

    def test_remove_toggle_disabled_returns_404(self):
        toggles.ENTERPRISE_ADMIN_SELF_SERVICE.set(
            self.domain_name, False, toggles.NAMESPACE_DOMAIN,
        )
        response = self.client.post(
            self.remove_url, {'email': self.second_admin.username},
        )
        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run:
```
uv run pytest --reusedb=1 corehq/apps/enterprise/tests/test_enterprise_admins.py::RemoveEnterpriseAdminViewTests -v
```
Expected: tests fail because the current `remove_enterprise_admin` is a no-op redirect.

- [ ] **Step 3: Replace the `remove_enterprise_admin` stub with the real implementation**

In `corehq/apps/enterprise/views.py`, replace the stub for `remove_enterprise_admin` with:

```python
@toggles.ENTERPRISE_ADMIN_SELF_SERVICE.required_decorator()
@require_enterprise_admin
@require_POST
def remove_enterprise_admin(request, domain):
    account = request.account
    redirect = HttpResponseRedirect(
        reverse('enterprise_admins', args=[domain]),
    )
    email = (request.POST.get('email') or '').lower()
    current_user_email = request.couch_user.username.lower()

    if email == current_user_email:
        messages.error(
            request,
            _("You cannot remove yourself as an enterprise administrator."),
        )
        return redirect

    if len(account.enterprise_admin_emails) <= 1:
        messages.error(
            request,
            _("An enterprise account must have at least one administrator."),
        )
        return redirect

    remaining = [
        e for e in account.enterprise_admin_emails if e.lower() != email
    ]
    if len(remaining) == len(account.enterprise_admin_emails):
        messages.error(
            request,
            _("%(email)s is not an enterprise administrator.") % {
                'email': email,
            },
        )
        return redirect

    account.enterprise_admin_emails = remaining
    account.save()
    enterprise_admin_logger.info(
        "Enterprise admin %s removed from account %s by %s",
        email, account.id, request.couch_user.username,
    )
    messages.success(
        request,
        _("%(email)s has been removed as an enterprise administrator.")
        % {'email': email},
    )
    return redirect
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run:
```
uv run pytest --reusedb=1 corehq/apps/enterprise/tests/test_enterprise_admins.py::RemoveEnterpriseAdminViewTests -v
```
Expected: all seven tests pass.

- [ ] **Step 5: Commit**

```
git add corehq/apps/enterprise/views.py \
        corehq/apps/enterprise/tests/test_enterprise_admins.py
git commit -m "Implement remove_enterprise_admin view"
```

---

## Task 7: Register the sidebar tab

**Files:**
- Modify: `corehq/tabs/tabclasses.py`

- [ ] **Step 1: Add the tab entry**

Edit `corehq/tabs/tabclasses.py`. Locate the `EnterpriseSettingsTab.sidebar_items` property (search for `'Enterprise Permissions'` to find the neighbor entry around line 1930). Add the following block **above** the existing `if self.couch_user.is_superuser:` block that registers the `Enterprise Permissions` tab, and **after** the `manage_sso` block:

```python
        if toggles.ENTERPRISE_ADMIN_SELF_SERVICE.enabled_for_request(self._request):
            enterprise_views.append({
                'title': _("Enterprise Administrators"),
                'url': reverse("enterprise_admins", args=[self.domain]),
                'description': _(
                    "View and manage the administrators for your enterprise account"
                ),
                'subpages': [],
                'show_in_dropdown': False,
            })
```

`toggles` is already imported at the top of this file.

- [ ] **Step 2: Manually verify the tab renders**

Start the local dev server (per project convention) and log in as an enterprise admin on a domain with the toggle enabled. Navigate to the Enterprise Console sidebar; confirm an **Enterprise Administrators** entry appears and links to `/a/<domain>/enterprise/admins/`.

If no dev environment is set up, use the Django shell to verify the URL reverse works:

```
uv run ./manage.py shell -c "from django.urls import reverse; print(reverse('enterprise_admins', args=['anydomain']))"
```
Expected: `/a/anydomain/enterprise/admins/`

- [ ] **Step 3: Commit**

```
git add corehq/tabs/tabclasses.py
git commit -m "Add Enterprise Administrators sidebar tab"
```

---

## Task 8: Full test-suite and lint pass

- [ ] **Step 1: Run the full enterprise admin test module**

Run:
```
uv run pytest --reusedb=1 corehq/apps/enterprise/tests/test_enterprise_admins.py -v
```
Expected: all tests pass.

- [ ] **Step 2: Lint the modified Python files**

Run:
```
uv run ruff check corehq/toggles/__init__.py \
                  corehq/apps/enterprise/forms.py \
                  corehq/apps/enterprise/views.py \
                  corehq/apps/enterprise/urls.py \
                  corehq/apps/enterprise/tests/test_enterprise_admins.py \
                  corehq/tabs/tabclasses.py
```
Fix any reported issues and re-run until clean.

- [ ] **Step 3: Format HTML templates**

Run:
```
npx prettier --write corehq/apps/enterprise/templates/enterprise/enterprise_admins.html \
                     corehq/apps/enterprise/templates/enterprise/partials/enterprise_admins_table.html
```

- [ ] **Step 4: Run the broader enterprise test suite for regression**

Run:
```
uv run pytest --reusedb=1 corehq/apps/enterprise/tests/ -v
```
Expected: all tests pass (no regressions in the other enterprise test files).

- [ ] **Step 5: Commit any formatting / lint fixes**

If Steps 2-3 made changes:
```
git add -u
git commit -m "Lint and format pass for enterprise admin self-service"
```
If not, skip.

---

## Done

At this point the feature is complete:

- `ENTERPRISE_ADMIN_SELF_SERVICE` toggle registered.
- `EnterpriseAdminForm` with email + SSO-domain validation.
- Three views: GET list, POST add, POST remove.
- Two templates (main page + list partial).
- Sidebar tab entry visible when the toggle is on.
- Test coverage for the helper, the form, and all three views including toggle-off, self-removal, last-admin, duplicate, invalid format, and SSO-domain-restricted cases.

Open a draft PR with the "DON'T REVIEW YET" label per project convention.
