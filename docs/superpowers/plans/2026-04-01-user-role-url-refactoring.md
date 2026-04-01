# User Role URL Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Include `role_id` in all URLs that affect an existing UserRole, splitting the save endpoint into separate create/update endpoints.

**Architecture:** Split `post_user_role` into `create_user_role` and `update_user_role` views, update `delete_user_role` to accept `role_id` from the URL, update `_update_role_from_view` and `_delete_user_role` helper signatures to accept `role_id` as a kwarg, and update all JavaScript callers and templates.

**Tech Stack:** Python/Django (views, URLs), JavaScript (Alpine.js in edit_role.js, Knockout.js in roles.js), Django templates

---

### Task 1: Update `_update_role_from_view` helper signature

**Files:**
- Modify: `corehq/apps/users/views/role.py:174-214`
- Test: `corehq/apps/users/tests/test_views.py:126-212`

- [ ] **Step 1: Update tests for `_update_role_from_view` to use `role_id` kwarg**

In `corehq/apps/users/tests/test_views.py`, update the test calls. The import at line 41 stays the same. Change the tests that pass `_id` in `role_data` to pass `role_id` as a kwarg instead:

In `test_update_role` (line 175-189), replace:
```python
    def test_update_role(self):
        role_data = deepcopy(self.BASE_JSON)
        role_data["_id"] = self.role.get_id
        role_data["name"] = "role1"  # duplicate name during update is OK for now
        role_data["default_landing_page"] = None
        role_data["is_non_admin_editable"] = True
        role_data["permissions"] = get_default_available_permissions(
            edit_reports=True, view_report_list=["report1"]
        )
        updated_role = _update_role_from_view(self.domain, role_data)
```
with:
```python
    def test_update_role(self):
        role_data = deepcopy(self.BASE_JSON)
        role_data["name"] = "role1"  # duplicate name during update is OK for now
        role_data["default_landing_page"] = None
        role_data["is_non_admin_editable"] = True
        role_data["permissions"] = get_default_available_permissions(
            edit_reports=True, view_report_list=["report1"]
        )
        updated_role = _update_role_from_view(self.domain, role_data, role_id=self.role.get_id)
```

In `test_update_role_for_manage_domain_alerts` (line 191-206), replace:
```python
        role_data['_id'] = self.role.get_id
```
and:
```python
            _update_role_from_view(self.domain, role_data)
```
with (remove the `_id` line and pass `role_id` kwarg):
```python
            _update_role_from_view(self.domain, role_data, role_id=self.role.get_id)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest --reusedb=1 corehq/apps/users/tests/test_views.py::TestUpdateRoleFromView -v`
Expected: FAIL — `_update_role_from_view` does not accept `role_id` kwarg yet (it will actually accept it as `**kwargs` noise, but the behavior will be wrong since it won't find the role without `_id` in data). The `test_update_role` test should fail because the role won't be found/updated.

- [ ] **Step 3: Update `_update_role_from_view` to accept `role_id` kwarg**

In `corehq/apps/users/views/role.py`, replace lines 174-195:
```python
def _update_role_from_view(domain, role_data):
    landing_page = role_data["default_landing_page"]
    if landing_page:
        validate_landing_page(domain, landing_page)

    if (
        not domain_has_privilege(domain, privileges.RESTRICT_ACCESS_BY_LOCATION)
        and not role_data['permissions']['access_all_locations']
    ):
        # This shouldn't be possible through the UI, but as a safeguard...
        role_data['permissions']['access_all_locations'] = True

    if "_id" in role_data:
        try:
            role = UserRole.objects.by_couch_id(role_data["_id"])
        except UserRole.DoesNotExist:
            role = UserRole()
        else:
            if role.domain != domain:
                raise Http404()
    else:
        role = UserRole()
```
with:
```python
def _update_role_from_view(domain, role_data, role_id=None):
    landing_page = role_data["default_landing_page"]
    if landing_page:
        validate_landing_page(domain, landing_page)

    if (
        not domain_has_privilege(domain, privileges.RESTRICT_ACCESS_BY_LOCATION)
        and not role_data['permissions']['access_all_locations']
    ):
        # This shouldn't be possible through the UI, but as a safeguard...
        role_data['permissions']['access_all_locations'] = True

    if role_id is not None:
        try:
            role = UserRole.objects.by_couch_id(role_id)
        except UserRole.DoesNotExist:
            raise Http404()
        if role.domain != domain:
            raise Http404()
    else:
        role = UserRole()
```

Note two behavior changes:
1. Uses `role_id` kwarg instead of `role_data["_id"]`.
2. When `role_id` is provided but the role doesn't exist, raises `Http404` instead of silently creating a new role. This is correct — an update to a nonexistent role should 404.

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest --reusedb=1 corehq/apps/users/tests/test_views.py::TestUpdateRoleFromView -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add corehq/apps/users/views/role.py corehq/apps/users/tests/test_views.py
git commit -m "Update _update_role_from_view to accept role_id kwarg

Replace the pattern of reading '_id' from role_data dict with an
explicit role_id keyword argument. Also raises Http404 instead of
silently creating a new role when given a nonexistent role_id."
```

---

### Task 2: Update `_delete_user_role` helper signature

**Files:**
- Modify: `corehq/apps/users/views/role.py:233-260`
- Test: `corehq/apps/users/tests/test_views.py:215-246`

- [ ] **Step 1: Update tests for `_delete_user_role` to pass `role_id` as a string arg**

In `corehq/apps/users/tests/test_views.py`, update `TestDeleteRole` (lines 215-246). Replace all calls from `_delete_user_role(self.domain, {"_id": role.get_id, ...})` to `_delete_user_role(self.domain, role.get_id)`:

```python
class TestDeleteRole(TestCase):
    domain = 'test-role-delete'

    def test_delete_role(self):
        role = UserRole.create(self.domain, 'test-role')
        _delete_user_role(self.domain, role.get_id)
        self.assertFalse(UserRole.objects.filter(pk=role.id).exists())

    def test_delete_role_not_exist(self):
        with self.assertRaises(Http404):
            _delete_user_role(self.domain, "missing")

    def test_delete_role_with_users(self):
        self.user_count_mock.return_value = 1
        role = UserRole.create(self.domain, 'test-role')
        with self.assertRaisesRegex(InvalidRequestException, "It has one user"):
            _delete_user_role(self.domain, role.get_id)

    def test_delete_commcare_user_default_role(self):
        role = UserRole.create(self.domain, 'test-role', is_commcare_user_default=True)
        with self.assertRaisesRegex(InvalidRequestException, "default role for Mobile Users"):
            _delete_user_role(self.domain, role.get_id)

    def test_delete_role_wrong_domain(self):
        role = UserRole.create("other-domain", 'test-role')
        with self.assertRaises(Http404):
            _delete_user_role(self.domain, role.get_id)

    def setUp(self):
        user_count_patcher = patch('corehq.apps.users.views.role.get_role_user_count', return_value=0)
        self.user_count_mock = user_count_patcher.start()
        self.addCleanup(user_count_patcher.stop)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest --reusedb=1 corehq/apps/users/tests/test_views.py::TestDeleteRole -v`
Expected: FAIL — `_delete_user_role` still expects a dict with `_id` key.

- [ ] **Step 3: Update `_delete_user_role` to accept `role_id` string**

In `corehq/apps/users/views/role.py`, replace lines 233-260:
```python
def _delete_user_role(domain, role_data):
    try:
        role = UserRole.objects.by_couch_id(role_data["_id"], domain=domain)
    except UserRole.DoesNotExist:
        raise Http404

    if role.is_commcare_user_default:
        raise InvalidRequestException(_(
            "Unable to delete role '{role}'. "
            "This role is the default role for Mobile Users and can not be deleted.",
        ).format(role=role_data["name"]))

    user_count = get_role_user_count(domain, role_data["_id"])
    if user_count:
        raise InvalidRequestException(ngettext(
            "Unable to delete role '{role}'. "
            "It has one user and/or invitation still assigned to it. "
            "Remove all users assigned to the role before deleting it.",
            "Unable to delete role '{role}'. "
            "It has {user_count} users and/or invitations still assigned to it. "
            "Remove all users assigned to the role before deleting it.",
            user_count,
        ).format(role=role_data["name"], user_count=user_count))

    copy_id = role.couch_id
    role.delete()
    # return removed id in order to remove it from UI
    return {"_id": copy_id}
```
with:
```python
def _delete_user_role(domain, role_id):
    try:
        role = UserRole.objects.by_couch_id(role_id, domain=domain)
    except UserRole.DoesNotExist:
        raise Http404

    if role.is_commcare_user_default:
        raise InvalidRequestException(_(
            "Unable to delete role '{role}'. "
            "This role is the default role for Mobile Users and can not be deleted.",
        ).format(role=role.name))

    user_count = get_role_user_count(domain, role_id)
    if user_count:
        raise InvalidRequestException(ngettext(
            "Unable to delete role '{role}'. "
            "It has one user and/or invitation still assigned to it. "
            "Remove all users assigned to the role before deleting it.",
            "Unable to delete role '{role}'. "
            "It has {user_count} users and/or invitations still assigned to it. "
            "Remove all users assigned to the role before deleting it.",
            user_count,
        ).format(role=role.name, user_count=user_count))

    copy_id = role.couch_id
    role.delete()
    # return removed id in order to remove it from UI
    return {"_id": copy_id}
```

Key changes: second parameter is now `role_id` (a string) instead of `role_data` (a dict). Error messages use `role.name` (from the fetched model) instead of `role_data["name"]`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest --reusedb=1 corehq/apps/users/tests/test_views.py::TestDeleteRole -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add corehq/apps/users/views/role.py corehq/apps/users/tests/test_views.py
git commit -m "Update _delete_user_role to accept role_id string

Replace the role_data dict parameter with a plain role_id string.
Error messages now use role.name from the fetched model instance."
```

---

### Task 3: Split `post_user_role` into `create_user_role` and `update_user_role` views

**Files:**
- Modify: `corehq/apps/users/views/role.py:149-171`

- [ ] **Step 1: Replace `post_user_role` with two new view functions**

In `corehq/apps/users/views/role.py`, replace lines 145-171:
```python
# If any permission less than domain admin were allowed here, having that
# permission would give you the permission to change the permissions of your
# own role such that you could do anything, and would thus be equivalent to
# having domain admin permissions.
@json_error
@domain_admin_required
@require_POST
@use_bootstrap5
def post_user_role(request, domain):
    if not domain_has_privilege(domain, privileges.ROLE_BASED_ACCESS):
        return JsonResponse({})
    role_data = json.loads(request.body.decode('utf-8'))

    try:
        role = _update_role_from_view(domain, role_data)
    except ValueError as e:
        return JsonResponse({
            "message": str(e)
        }, status=400)

    response_data = role.to_json()
    if role.is_commcare_user_default:
        response_data["preventRoleDelete"] = True
    else:
        user_count = get_role_user_count(domain, role.couch_id)
        response_data['preventRoleDelete'] = user_count > 0
    return JsonResponse(response_data)
```
with:
```python
# If any permission less than domain admin were allowed here, having that
# permission would give you the permission to change the permissions of your
# own role such that you could do anything, and would thus be equivalent to
# having domain admin permissions.
@json_error
@domain_admin_required
@require_POST
@use_bootstrap5
def create_user_role(request, domain):
    if not domain_has_privilege(domain, privileges.ROLE_BASED_ACCESS):
        return JsonResponse({})
    role_data = json.loads(request.body.decode('utf-8'))

    try:
        role = _update_role_from_view(domain, role_data)
    except ValueError as e:
        return JsonResponse({
            "message": str(e)
        }, status=400)

    response_data = role.to_json()
    return JsonResponse(response_data)


@json_error
@domain_admin_required
@require_POST
@use_bootstrap5
def update_user_role(request, domain, role_id):
    if not domain_has_privilege(domain, privileges.ROLE_BASED_ACCESS):
        return JsonResponse({})
    role_data = json.loads(request.body.decode('utf-8'))

    try:
        role = _update_role_from_view(domain, role_data, role_id=role_id)
    except ValueError as e:
        return JsonResponse({
            "message": str(e)
        }, status=400)

    response_data = role.to_json()
    if role.is_commcare_user_default:
        response_data["preventRoleDelete"] = True
    else:
        user_count = get_role_user_count(domain, role.couch_id)
        response_data['preventRoleDelete'] = user_count > 0
    return JsonResponse(response_data)
```

Note: `create_user_role` does not include `preventRoleDelete` since a newly created role can never have users assigned to it.

- [ ] **Step 2: Update `delete_user_role` to accept `role_id` from URL**

In the same file, replace the `delete_user_role` view (lines 217-230):
```python
@domain_admin_required
@require_POST
@use_bootstrap5
def delete_user_role(request, domain):
    if not domain_has_privilege(domain, privileges.ROLE_BASED_ACCESS):
        return JsonResponse({})
    role_data = json.loads(request.body.decode('utf-8'))

    try:
        response_data = _delete_user_role(domain, role_data)
    except InvalidRequestException as e:
        return JsonResponse({"message": str(e)}, status=400)

    return JsonResponse(response_data)
```
with:
```python
@domain_admin_required
@require_POST
@use_bootstrap5
def delete_user_role(request, domain, role_id):
    if not domain_has_privilege(domain, privileges.ROLE_BASED_ACCESS):
        return JsonResponse({})

    try:
        response_data = _delete_user_role(domain, role_id)
    except InvalidRequestException as e:
        return JsonResponse({"message": str(e)}, status=400)

    return JsonResponse(response_data)
```

- [ ] **Step 3: Run linter**

Run: `source .venv/bin/activate && ruff check corehq/apps/users/views/role.py`
Expected: No errors (or only pre-existing ones).

- [ ] **Step 4: Commit**

```bash
git add corehq/apps/users/views/role.py
git commit -m "Split post_user_role into create_user_role and update_user_role

create_user_role handles new role creation (no role_id).
update_user_role handles editing existing roles (role_id in URL).
delete_user_role now accepts role_id from URL kwargs."
```

---

### Task 4: Update URL patterns

**Files:**
- Modify: `corehq/apps/users/urls.py:154-158`

- [ ] **Step 1: Update URL imports**

In `corehq/apps/users/urls.py`, find the import of `post_user_role` and replace it with imports of the two new functions. Search for the import line (it will be near the top of the file among other imports from `corehq.apps.users.views.role`):

Replace:
```python
    post_user_role,
```
with:
```python
    create_user_role,
    update_user_role,
```

- [ ] **Step 2: Update URL patterns**

In `corehq/apps/users/urls.py`, replace lines 155-158:
```python
    url(r'^roles/save/$', post_user_role, name='post_user_role'),
    url(r'^roles/new/$', EditRoleView.as_view(), name='create_role'),
    url(r'^roles/edit/(?P<role_id>[ \w-]+)', EditRoleView.as_view(), name=EditRoleView.urlname),
    url(r'^roles/delete/$', delete_user_role, name='delete_user_role'),
```
with:
```python
    url(r'^roles/create/$', create_user_role, name='create_user_role'),
    url(r'^roles/update/(?P<role_id>[ \w-]+)/$', update_user_role, name='update_user_role'),
    url(r'^roles/new/$', EditRoleView.as_view(), name='create_role'),
    url(r'^roles/edit/(?P<role_id>[ \w-]+)/$', EditRoleView.as_view(), name=EditRoleView.urlname),
    url(r'^roles/delete/(?P<role_id>[ \w-]+)/$', delete_user_role, name='delete_user_role'),
```

Note: trailing `/$` added to the `edit` URL pattern, and `role_id` capture group added to `delete`.

- [ ] **Step 3: Run linter**

Run: `source .venv/bin/activate && ruff check corehq/apps/users/urls.py`
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add corehq/apps/users/urls.py
git commit -m "Update role URL patterns to include role_id

- Replace roles/save/ with roles/create/ and roles/update/<role_id>/
- Add role_id to roles/delete/<role_id>/
- Add trailing slash to roles/edit/<role_id>/"
```

---

### Task 5: Update templates to register new URL names

**Files:**
- Modify: `corehq/apps/users/templates/users/edit_role.html:6-7`
- Modify: `corehq/apps/users/templates/users/roles_and_permissions.html:7`

- [ ] **Step 1: Update `edit_role.html` template**

In `corehq/apps/users/templates/users/edit_role.html`, replace lines 6-7:
```html
  {% registerurl "post_user_role" domain %}
  {% registerurl "edit_role" domain '---' %}
```
with:
```html
  {% registerurl "create_user_role" domain %}
  {% registerurl "update_user_role" domain '---' %}
  {% registerurl "edit_role" domain '---' %}
```

The `'---'` placeholder allows JavaScript to construct URLs with real role IDs by replacing the placeholder.

- [ ] **Step 2: Update `roles_and_permissions.html` template**

In `corehq/apps/users/templates/users/roles_and_permissions.html`, replace line 7:
```html
  {% registerurl "delete_user_role" domain %}
```
with:
```html
  {% registerurl "delete_user_role" domain '---' %}
```

The `'---'` placeholder is now needed because the URL includes `role_id`.

- [ ] **Step 3: Commit**

```bash
git add corehq/apps/users/templates/users/edit_role.html corehq/apps/users/templates/users/roles_and_permissions.html
git commit -m "Register new role URL names in templates

Update registerurl tags for the renamed create/update endpoints
and add placeholder arg for delete URL (now includes role_id)."
```

---

### Task 6: Update `edit_role.js` to use new URLs

**Files:**
- Modify: `corehq/apps/users/static/users/js/edit_role.js:830-857`

- [ ] **Step 1: Update the `saveRole` function**

In `corehq/apps/users/static/users/js/edit_role.js`, replace the `saveRole` function (lines 830-857):
```javascript
            self.saveRole = () => {
                self.isSaving = true;
                const isNewRole = !self.role._id;
                $.ajax({
                    method: 'POST',
                    url: initialPageData.reverse("post_user_role"),
                    data: JSON.stringify(self.role, null, 2),
                    dataType: 'json',
                    success: (response) => {
                        if (isNewRole && response._id) {
                            window.location.href = initialPageData.reverse("edit_role", response._id);
                        } else {
                            setTimeout(() => {
                                self.isSaving = false;
                                self.isDirty = false;
                            }, 500);
                        }
                    },
                    error: (response) => {
                        self.isSaving = false;
                        let message = gettext("An error occurred, please try again.");
                        if (response.responseJSON && response.responseJSON.message) {
                            message = response.responseJSON.message;
                        }
                        self.roleError = message;
                    },
                });
            };
```
with:
```javascript
            self.saveRole = () => {
                self.isSaving = true;
                const isNewRole = !self.role._id;
                const url = isNewRole
                    ? initialPageData.reverse("create_user_role")
                    : initialPageData.reverse("update_user_role", self.role._id);
                $.ajax({
                    method: 'POST',
                    url: url,
                    data: JSON.stringify(self.role, null, 2),
                    dataType: 'json',
                    success: (response) => {
                        if (isNewRole && response._id) {
                            window.location.href = initialPageData.reverse("edit_role", response._id);
                        } else {
                            setTimeout(() => {
                                self.isSaving = false;
                                self.isDirty = false;
                            }, 500);
                        }
                    },
                    error: (response) => {
                        self.isSaving = false;
                        let message = gettext("An error occurred, please try again.");
                        if (response.responseJSON && response.responseJSON.message) {
                            message = response.responseJSON.message;
                        }
                        self.roleError = message;
                    },
                });
            };
```

- [ ] **Step 2: Run JS linter**

Run: `npx eslint corehq/apps/users/static/users/js/edit_role.js`
Expected: No new errors.

- [ ] **Step 3: Commit**

```bash
git add corehq/apps/users/static/users/js/edit_role.js
git commit -m "Update edit_role.js to use separate create/update URLs

POST to create_user_role for new roles, update_user_role for existing."
```

---

### Task 7: Update `roles.js` and `roles_and_permissions.js` for delete URL with role_id

**Files:**
- Modify: `corehq/apps/users/static/users/js/roles.js:59-71`
- Modify: `corehq/apps/users/static/users/js/roles_and_permissions.js:60`

- [ ] **Step 1: Update `roles_and_permissions.js` initialization**

In `corehq/apps/users/static/users/js/roles_and_permissions.js`, replace line 60:
```javascript
        deleteUrl: url("delete_user_role"),
```
with:
```javascript
        deleteUrlTemplate: url("delete_user_role"),
```

This is just a rename to clarify that it's a URL template with a placeholder, not a final URL.

- [ ] **Step 2: Update `roles.js` delete handler**

In `corehq/apps/users/static/users/js/roles.js`, replace the `modalDeleteButton` section (lines 59-73):
```javascript
    self.modalDeleteButton = {
        state: ko.observable(),
        saveOptions: function () {
            return {
                url: o.deleteUrl,
                type: 'post',
                data: JSON.stringify(self.roleBeingDeleted()),
                dataType: 'json',
                success: function (data) {
                    self.removeRole(data);
                    self.unsetRoleBeingDeleted();
                },
            };
        },
    };
```
with:
```javascript
    self.modalDeleteButton = {
        state: ko.observable(),
        saveOptions: function () {
            var role = self.roleBeingDeleted();
            return {
                url: o.deleteUrlTemplate.replace('---', role._id),
                type: 'post',
                dataType: 'json',
                success: function (data) {
                    self.removeRole(data);
                    self.unsetRoleBeingDeleted();
                },
            };
        },
    };
```

Key changes: URL is constructed per-role by replacing the `'---'` placeholder with the role's `_id`. The POST body (`data`) is removed since the role_id now comes from the URL.

- [ ] **Step 3: Run JS linter**

Run: `npx eslint corehq/apps/users/static/users/js/roles.js corehq/apps/users/static/users/js/roles_and_permissions.js`
Expected: No new errors.

- [ ] **Step 4: Commit**

```bash
git add corehq/apps/users/static/users/js/roles.js corehq/apps/users/static/users/js/roles_and_permissions.js
git commit -m "Update role delete JS to include role_id in URL

Construct delete URL per-role using placeholder replacement.
Remove role data from POST body since role_id is now in the URL."
```

---

### Task 8: Clean up old references and verify end-to-end

**Files:**
- Modify: `corehq/apps/users/urls.py` (verify no remaining `post_user_role` references)
- Modify: `corehq/apps/users/views/role.py` (remove old `post_user_role` if any import aliases remain)

- [ ] **Step 1: Search for any remaining references to `post_user_role`**

Run: `source .venv/bin/activate && ruff check corehq/apps/users/ && grep -r "post_user_role" corehq/apps/users/`
Expected: No matches. If any remain, update them.

- [ ] **Step 2: Run the full test suite for the users app role tests**

Run: `source .venv/bin/activate && pytest --reusedb=1 corehq/apps/users/tests/test_views.py::TestUpdateRoleFromView corehq/apps/users/tests/test_views.py::TestDeleteRole -v`
Expected: All tests PASS.

- [ ] **Step 3: Run the linter on all changed files**

Run: `source .venv/bin/activate && ruff check corehq/apps/users/views/role.py corehq/apps/users/urls.py`
Expected: No errors.

- [ ] **Step 4: Commit any cleanup (if needed)**

Only commit if Step 1 found remaining references that needed updating.
