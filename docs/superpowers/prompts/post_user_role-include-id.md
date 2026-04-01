# Context
Currently, CRUD actions on Role models go through the follow four URLS.
```
    url(r'^roles/save/$', post_user_role, name='post_user_role'),
    url(r'^roles/new/$', EditRoleView.as_view(), name='create_role'),
    url(r'^roles/edit/(?P<role_id>[ \w-]+)', EditRoleView.as_view(), name=EditRoleView.urlname),
    url(r'^roles/delete/$', delete_user_role, name='delete_user_role'),

```

`save` is used both to create a UserRole and to update one.
`delete` is used to delete a UserRole model.
`new` and `edit` are URLs that show the user a UI on which they can submit requests to create and update a role, respectively.

# Goal
I want any use of these URLs that affects an existing UserRole to have the role_id in the URL.

To accomplish this:
- Replace the `save` URL with a `create` URL (no role_id) and an `update` URL that has a role_id in the URL.
- Replace the `post_user_role` function with two functions: `create_user_role` and `update_user_role`.
- Update the `delete` URL to include a role_id.
- Make the POST body no longer contain an `_id` field, as this now comes from the URL.
- Make sure all URLs (including the edit url) have a trailing `/`.
