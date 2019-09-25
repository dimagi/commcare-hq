# Linking Domains

* Ability to sync models between two domains (master domain -> linked domain)
* Can be within the same HQ instance or between remote instances.

# Remote linking

### On 'master domain':

```
DomainLink.link_domains('https://url.of.linked.hq/a/linked_domain_name', 'master_domain_name')
```

This gets used as a permissions check during remote requests to ensure
that the remote domain is allowed to sync from this domain.

### On 'linked domain'

```
remote_details = RemoteLinkDetails(
    url_base='https://url.of.master.hq',
    username='username@email.com',
    api_key='api key for username'
)
DomainLink.link_domains('linked_domain_name', 'master_domain_name', remote_details)
```

### Pulling changes from master

On remote HQ, enable `linked_domains` feature flag and navigate to `project settings > Linked Projects` page which has a UI to pull changes from master domain for custom data fields for Location, User and Product models, user roles and feature flags/previews.

Linked apps can be setup between linked domains by running `link_app_to_remote` command on linked domain.

# Linked Applications

Linked applications predate linked domains. Now that linked domains exist, when you link an app, the linked domain record is automatically created.

## Pulling changes from master
A linked app can be pulled if its master app has a higher released version than the current version of the linked app. Pulling a linked app is similar but not identical to copying an app.

When a linked/downstream app is pulled from its master/upstream app:
- The linked app's version will be set to the master app's version.
- The two apps will have **different** ids.
- Corresponding modules in the master and linked app will have the **same** unique ids.
- Corresponding forms in the master and linked app will have **different** unique ids.
- Corresponding forms in the master and linked app will have the **same** XMLNS.

## Exclusions
A few fields are **not** copied from the master app to the linked app. They include basic metadata (doc type, name, date created, comment, etc) and some build-related fields (build profiles and practice mobile workers). For the full list, see [excluded_fields in overwrite_app](https://github.com/dimagi/commcare-hq/blob/47b197378fc196ff25a88dc5b2c56a389aaec85f/corehq/apps/app_manager/views/utils.py#L165-L169).

## Overrides
A small number of settings can be overridden in a linked app. App settings can be tagged with the `supports_linked_app` flag to make them appear on the linked app's settings page. However, because linked app versions are tied to master versions, linked app versions do not increment on their own when a change is made. This makes the following workflow necessary for settings overrides:
- Pull master app
- Make any changes to linked app
- Make build of linked app
Once the build is made, even after making additional changes, it's no longer possible to make a new build of the linked app until the next pull from master.
