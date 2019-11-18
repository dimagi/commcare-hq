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

Linked applications predate linked domains. Now that linked domains exist, when you link an app, the linked domain record is automatically created. A linked/downstream app is tied to one or more master/upstream apps via the `upstream_app_id` and `upstream_version` attributes. 

## Pulling changes from master
A linked app can be pulled if its master/upstream app has a higher released version than the `upstream_version` of the linked app. Pulling a linked app is similar but not identical to copying an app.

When a linked/downstream app is pulled from its master/upstream app:
- The linked app's version will be incremented.
- The two apps will have **different** ids.
- Corresponding modules in the master and linked app will have the **same** unique ids.
- Corresponding forms in the master and linked app will have the **same** XMLNS.
- Corresponding forms in the master and linked app will have **different** unique ids.
   - In order to keep these ids consistent from one pull to another, particularly when using multiple master apps (see below), part of the pull process maps the forms in the new linked app to the forms in the most recent version of the linked app. This overwrites the form ids copied from the master app with the form ids that are being used in the linked app. Any new forms (added to the master since the last time the linked app was pulled) will be assigned brand-new ids.
   - Note on shadow forms: The mapping described above is based on XMLNS. Since a shadow form inherits its parent's XMLNS, shadow forms cannot be mapped. The result of this is that any shadow forms in the linked app are unstable: their unique ids change on **every** pull. This means that workflows that store a form's unique id, such as UCRs based on a form data source, will not work with shadow forms on linked apps.

## Exclusions
A few fields are **not** copied from the master app to the linked app. They include basic metadata (doc type, name, date created, comment, etc) and some build-related fields (build profiles and practice mobile workers). For the full list, see [excluded_fields in overwrite_app](https://github.com/dimagi/commcare-hq/blob/47b197378fc196ff25a88dc5b2c56a389aaec85f/corehq/apps/app_manager/views/utils.py#L165-L169).

## Overrides
A small number of settings can be overridden in a linked app. App settings can be tagged with the `supports_linked_app` flag to make them appear on the linked app's settings page.

## Multi-master
The `MULTI_MASTER_LINKED_DOMAINS` feature flag allows a linked app to pull changes from more than one master app. The use case for multiple master apps is to support a branching-type workflow.

A linked app may pull from all multiple upstream apps within a single "family." Families are created by copying apps; when an app is copied, its `family_id` is set to the id of the app it was copied from.

When this flag is on, different builds of the same linked app may have different values for `upstream_app_id`. This id reflects the app that specific build was pulled from.

