# Linking Domains

Linked project spaces allow project spaces to share much of their data. You configure one controlling upstream domain
with one or more downstream domains and then can overwrite downstream content with upstream content.
Most code refers to upstream domains as "master" and downstream as "linked", though we're updating that
terminology.

Linked domains have two major use cases:

1. Setting up a practice domain and then a production domain
1. Multi-geography projects that have one upstream domain and then a downstream domain for each of several different locations.

Most domain linkages are "local",  with all domains residing in the same HQ cloud environment.
There are also "remote" links, where the upstream domain is in a different environment than the downstream domains.
Not all functionality is supported by remote linked domains, but most of it is. See below for more on remote
linking.

## User Interface

The upstream domain looks like any other domain, but downstream domains have a more limited UI, because most of
their configuration
comes from their upstream domain and much of that shared content is read-only (see below for details on specific
data models). Both upstream and downstream domains have a settings
page (Project Settings > Linked Project Spaces) used to overwrite content.

Overwriting can be triggered from either the upstream domain ("pushing" / "Enterprise Release Management") or any
downstream domain ("pulling"). Individual downstream domains can be pushed/pulled, and individual data types can be
pushed/pulled.

To enable linked domains, turn on the feature flag
[LINKED_DOMAINS](https://github.com/dimagi/commcare-hq/blob/966b62cc113b56af771906def76833446b4ba025/corehq/toggles.py#L1497).
To link two domains, copy an application from the upstream domain to the desired downstream domain, checking the
checkbox "Copy as linked application." This is a legacy workflow, leftover from when linked domains **only**
supported applications. Remote domain linkages cannot be created via the UI; see below for details.

## Data models

Linked domains share configuration data. Supported data types are defined in
corehq.apps.linked_domain.const.ALL_LINKED_MODELS:

- Applications
- Reports
- Lookup tables
- Keywords
- User roles
- Custom data fields for users, products, and locations
- Feature Flags
- Feature Previews
- Case search settings
- Data dictionary
- Dialer settings
- OTP Pass-through Settings
- Signed Callout

Of these, apps, keywords, and reports need to be linked individually, from the app settings, keywords, and edit report UIs, and are
overwritten individually. The rest of the data types are overwritten as entire blocks: for example, you can't
overwrite a single user role, you update them as one unit. Lookup tables are in between: you don't need to link
them individually, but you can update them individually (due to performance concerns around updating them as a
block).

The ability to edit linked data on a downstream domain depends on the data type. For example, applications are
read-only on downstream domains, with a few settings (controlled by
[supports_linked_app](https://github.com/dimagi/commcare-hq/blob/966b62cc113b56af771906def76833446b4ba025/corehq/apps/app_manager/static/app_manager/json/commcare-profile-settings.yaml#L97))
that may be edited and will retain their
values even when the app is updated. Reports cannot be edited at all. Other data, such as user roles, can typically
be edited on the downstream domain, but any edits will be overwritten the next time that data type is
pushed/pulled.

Support for additional models is added as time permits. Any configuration-related data type could potentially be shared.
Project data like forms and cases would not be shared.


## Remote linking

### On 'master domain':

Run `add_downstream_domain` management command on source HQ.

```
$ ./manage.py add_downstream_domain --url {https://url.of.linked.hq/a/linked_domain_name/} --domain {upstream_domain_name}
```

This gets used as a permissions check during remote requests to ensure
that the remote domain is allowed to sync from this domain.

### On 'linked domain'

Run `link_to_upstream_domain` management command on downsream HQ.

### Pulling changes from master

On downstream HQ, enable `linked_domains` feature flag and navigate to `project settings > Linked Projects` page which has a UI to pull changes from master domain for custom data fields for Location, User and Product models, user roles and feature flags/previews.

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
- Corresponding forms in the master and linked app may have either the same or different unique ids, depending on how old the linked app is.
   - Older linked apps will have differing ids, while linked apps created after the deploy of [#25998](https://github.com/dimagi/commcare-hq/pull/25998) in December 2019 will use the same ids in both the linked and master apps.
   - Linked apps that do not have form ids that match their master app have a mapping of master app form unique id => linked app form unique id, stored as [ResourceOverride](https://github.com/dimagi/commcare-hq/blob/15ceabdccf0ed49ed306462b3a154fe14886bf27/corehq/apps/app_manager/suite_xml/post_process/resources.py#L11) objects.
   - See [#25718](https://github.com/dimagi/commcare-hq/issues/25718) for context around why this change was made.

## Exclusions
A few fields are **not** copied from the master app to the linked app. They include basic metadata (doc type, name, date created, comment, etc) and some build-related fields (build profiles and practice mobile workers). For the full list, see [excluded_fields in overwrite_app](https://github.com/dimagi/commcare-hq/blob/47b197378fc196ff25a88dc5b2c56a389aaec85f/corehq/apps/app_manager/views/utils.py#L165-L169).

## Overrides
A small number of settings can be overridden in a linked app. App settings can be tagged with the `supports_linked_app` flag to make them appear on the linked app's settings page.

## Multi-master
The `MULTI_MASTER_LINKED_DOMAINS` feature flag allows a linked app to pull changes from more than one master app. The use case for multiple master apps is to support a branching-type workflow.

A linked app may pull from all multiple upstream apps within a single "family." Families are created by copying apps; when an app is copied, its `family_id` is set to the id of the app it was copied from.

When this flag is on, different builds of the same linked app may have different values for `upstream_app_id`. This id reflects the app that specific build was pulled from.
