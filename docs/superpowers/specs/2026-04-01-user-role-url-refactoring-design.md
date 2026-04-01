# User Role URL Refactoring: Include role_id in URLs

## Goal

Any URL that affects an existing UserRole should include the `role_id` in the URL path, rather than relying on `_id` in the POST body. This improves auditability and follows REST conventions.

## Current State

```
roles/save/                        -> post_user_role (create + update)
roles/new/                         -> EditRoleView (create form)
roles/edit/<role_id>               -> EditRoleView (edit form, no trailing slash)
roles/delete/                      -> delete_user_role (role_id in POST body)
```

## Target State

```
roles/create/                      -> create_user_role (create only)
roles/update/<role_id>/            -> update_user_role (update only)
roles/new/                         -> EditRoleView (create form, unchanged)
roles/edit/<role_id>/              -> EditRoleView (edit form, trailing slash added)
roles/delete/<role_id>/            -> delete_user_role (role_id from URL)
```

## Changes

### 1. URLs (`corehq/apps/users/urls.py`)

Replace:
```python
url(r'^roles/save/$', post_user_role, name='post_user_role'),
url(r'^roles/edit/(?P<role_id>[ \w-]+)', EditRoleView.as_view(), name=EditRoleView.urlname),
url(r'^roles/delete/$', delete_user_role, name='delete_user_role'),
```

With:
```python
url(r'^roles/create/$', create_user_role, name='create_user_role'),
url(r'^roles/update/(?P<role_id>[ \w-]+)/$', update_user_role, name='update_user_role'),
url(r'^roles/edit/(?P<role_id>[ \w-]+)/$', EditRoleView.as_view(), name=EditRoleView.urlname),
url(r'^roles/delete/(?P<role_id>[ \w-]+)/$', delete_user_role, name='delete_user_role'),
```

### 2. View Functions (`corehq/apps/users/views/role.py`)

**Split `post_user_role` into two functions:**

- `create_user_role(request, domain)` — calls `_update_role_from_view(domain, role_data)` with no `role_id`
- `update_user_role(request, domain, role_id)` — calls `_update_role_from_view(domain, role_data, role_id=role_id)`

Both retain the same decorators as `post_user_role`: `@json_error`, `@domain_admin_required`, `@require_POST`, `@use_bootstrap5`.

**Update `_update_role_from_view` signature:**

```python
def _update_role_from_view(domain, role_data, role_id=None):
```

- When `role_id` is provided, fetch the existing role by `couch_id` (replacing the current `_id`-from-data logic).
- When `role_id` is `None`, create a new role.
- Stop reading `_id` from `role_data`.

**Update `delete_user_role`:**

- Accept `role_id` from URL kwargs instead of POST body.
- Pass `role_id` to `_delete_user_role(domain, role_id)` (changing that helper's signature too).

**Update `_delete_user_role` signature:**

```python
def _delete_user_role(domain, role_id):
```

- Fetch role using `role_id` param directly instead of `role_data["_id"]`.
- Role name for error messages can come from the fetched role object.

### 3. JavaScript

**`edit_role.js` — `saveRole` function:**

- For new roles: POST to `create_user_role` URL (no role_id needed).
- For existing roles: POST to `update_user_role` URL with `role._id`.
- Strip `_id` from the JSON body before sending (it now comes from the URL).
- The `initialPageData.reverse` calls need both URL names registered.

**`roles.js` / `roles_and_permissions.js` — delete:**

- Change `deleteUrl` from a single static URL to a per-role URL that includes `role._id`.
- The `saveOptions` function should build the URL using the role being deleted.
- The POST body no longer needs to contain `_id`.
- The response from delete no longer needs to return `_id` (but can for backward compat).

### 4. Template / Initial Page Data

The `edit_role.html` template (or its view context) must register both `create_user_role` and `update_user_role` URL names so `initialPageData.reverse()` works in JavaScript.

The roles list page must register `delete_user_role` with a placeholder role_id so JavaScript can construct per-role delete URLs.

### 5. Tests (`corehq/apps/users/tests/test_views.py`)

Update `TestUpdateRoleFromView` and `TestDeleteRole` test classes to use the new URL patterns and pass `role_id` in the URL rather than the POST body.

## Out of Scope

- No changes to the UserRole model itself.
- No changes to `ListRolesView` or the `roles/` list URL.
- No changes to `roles/new/` (create form URL stays the same).
- No changes to role permission logic.
