# Linked Domains

Linked domains, referred to as Linked Project Spaces externally, allows domains to share much of their data. You configure one controlling upstream domain
with one or more downstream domains and then can overwrite downstream content with upstream content.
We have worked towards updating references from "master" to "upstream", and "linked" to "downstream", but there are still areas that use the old
terminology.

Linked domains have two major use cases:

1. Setting up a practice domain and then a production domain
1. Multi-geography projects that have one upstream domain and then a downstream domain for each of several different locations.

Most domain links are _local_, meaning all domains reside in the same HQ cloud environment.
There are also _remote_ links, where the upstream domain is in a different environment than the downstream domain(s).
Not all functionality is supported by remote links, but most of it is. See below for more under Remote
Links.

## User Interface

The upstream domain looks like any other domain, but downstream domains have a more limited UI, because most of
their configuration
comes from their upstream domain and much of that shared content is read-only (see below for details on specific
data models). Both upstream and downstream domains have a settings
page (Project Settings > Linked Project Spaces) used to overwrite content.

Overwriting can be triggered from either the upstream domain ("pushing") or any
downstream domain ("pulling").

To enable linked domains, turn on the feature flag
[LINKED_DOMAINS](https://github.com/dimagi/commcare-hq/blob/966b62cc113b56af771906def76833446b4ba025/corehq/toggles.py#L1497).
To link two domains, copy an application from the upstream domain to the desired downstream domain, checking the
checkbox "Copy as linked application." This is a legacy workflow, leftover from when linked domains **only**
supported applications. Remote domain linkages cannot be created via the UI; see below for details.

## Data Models

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
- Tableau Server and Visualizaions

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


## Remote Links

### Remote Link Setup

#### From the upstream domain's HQ environment

Run the `add_downstream_domain` management command:

```
$ ./manage.py add_downstream_domain --downstream_url {https://url.of.linked.hq/a/linked_domain_name/} --upstream_domain {upstream_domain_name}
```

This gets used as a permissions check during remote requests to ensure
that the remote domain is allowed to sync from this domain.

#### From the downstream domain's HQ environment

Run the `link_to_upstream_domain` management command.
```
$ ./manage.py link_to_upstream_domain --url_base {base_url_for_upstream_domain} --upstream_domain {upstream_domain_name} --username {username} --api_key {user_api_key} --downstream_domain {downstream_domain_name}
```
The specified username and API key are needed to authenticate requests to the upstream environment.
### Pulling Changes From the Upstream Domain

On downstream domain's HQ environment, enable `linked_domains` feature flag. Navigate to the `Project Settings > Linked Projects` page which has a UI to pull changes from the upstream domain for the following fields:
- Custom data fields for Location, User and Product models
- User Roles
- Feature Flags
- Feature Previews
- Reports

#### Linking Remote Applications

If you don't already have an upstream application you would like to link, create an app in the upstream domain. Then create an app in the downstream domain to serve as a placeholder. These app ids can then be used when running the `link_app_to_remote` management command:
```
$ ./manage.py link_app_to_remote --master_id {upstream_app_id} --linked_id {downstream_app_id} --url_base {base url} --domain {upstream_domain_name} --username {username} --api_key {api_key}
```
# Linked Applications

Linked applications predate linked domains. Now that linked domains exist, when you link an app, the linked domain record is automatically created. A downstream app is tied to an upstream app via the `upstream_app_id` and `upstream_version` attributes.

## Pulling changes from upstream
A downstream app can pull changes if its upstream app has a higher released version than the `upstream_version` of the downstream app. Pulling changes from an upstream app is similar but not identical to copying an app.

When an upstream app is pulled downstream:
- The downstream app's version will be incremented.
- The two apps will have **different** ids.
- Corresponding modules in the upstream and downstream app will have the **same** unique ids.
- Corresponding forms in the upstream and downstream app will have the **same** XMLNS.
- Corresponding forms in the upstream and downstream app may have either the same or different unique ids, depending on how old the downstream app is.
   - Older downstream apps will have differing ids, while downstream apps created after the deploy of [#25998](https://github.com/dimagi/commcare-hq/pull/25998) in December 2019 will use the same ids in both the downstream and upstream apps.
   - Downstream apps that do not have form ids that match their upstream app have a mapping of upstream app form unique id => downstream app form unique id, stored as [ResourceOverride](https://github.com/dimagi/commcare-hq/blob/15ceabdccf0ed49ed306462b3a154fe14886bf27/corehq/apps/app_manager/suite_xml/post_process/resources.py#L11) objects.
   - See [#25718](https://github.com/dimagi/commcare-hq/issues/25718) for context around why this change was made.

## Exclusions
A few fields are **not** copied from the upstream app to the downstream app. They include basic metadata (doc type, name, date created, comment, etc) and some build-related fields (build profiles and practice mobile workers). For the full list, see [excluded_fields in overwrite_app](https://github.com/dimagi/commcare-hq/blob/47b197378fc196ff25a88dc5b2c56a389aaec85f/corehq/apps/app_manager/views/utils.py#L165-L169).

## Overrides
A small number of settings can be overridden in a downstream app. App settings can be tagged with the `supports_linked_app` flag to make them appear on the downstream app's settings page.

## Multi-master
The `MULTI_MASTER_LINKED_DOMAINS` feature flag allows a downstream app to pull changes from more than one master app. The use case for multiple master apps is to support a branching-type workflow.

A downstream app may pull from all multiple upstream apps within a single "family." Families are created by copying apps; when an app is copied, its `family_id` is set to the id of the app it was copied from.

When this flag is on, different builds of the same downstream app may have different values for `upstream_app_id`. This id reflects the app that specific build was pulled from.
