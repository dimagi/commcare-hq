toggle
======

Simple couchdb-backed django app for doing user-level toggles.

Is designed to be _simple_ and _fast_ (automatically caches all toggles).

To use, make sure `toggle` is in your `INSTALLED_APPS` and `COUCHDB_DATABASES`.

To create a toggle:

```
./manage.py make_toggle mytogglename user1@example.com user2@example.com
```

To toggle a feature in code:

```python

if toggle_enabled('mytogglename', someuser.username):
    do_toggled_work()
else:
    do_normal_work()
```
