# Linked Domains

Linked domains, referred to as Linked Project Spaces externally, allows domains to share much of their data. You configure one controlling upstream domain
with one or more downstream domains and then can overwrite downstream content with upstream content.
We have worked towards updating references from "master" to "upstream", and "linked" to "downstream", but there are still areas that use the old
terminology.

Linked domains have two major use cases:

1. Setting up a practice domain and then a production domain
1. Multi-geography projects that have one upstream domain and downstream domains for each unique location.

Most domain links are local, meaning all domains reside in the same HQ cloud environment.
There are also [remote links](#remote_links), where the upstream domain is in a different environment than the downstream domain(s).
Not all functionality is supported by remote links, but most of it is. See below for more under Remote
Links.

## Accessing Linked Project Spaces

Access to the Linked Project Spaces feature is controlled via the `release_management` and `lite_release_management`
privileges, externally referred to as Enterprise Release Management (ERM) and Multi-Environment Release Management (MRM)
respectively. Both privileges provide access to this feature, though notably MRM is a limited version of ERM.

## User Interface

The upstream domain looks like any other domain, but downstream domains have a more limited UI, because most of
their configuration
comes from their upstream domain and much of that shared content is read-only (see below for details on specific
data models). Both upstream and downstream domains have a settings
page (Project Settings > Linked Project Spaces) used to overwrite content.

Overwriting can be triggered from either the upstream domain ("pushing") or any
downstream domain ("pulling").

## Data Models<a name="data_models"></a>

Linked domains enable the sharing of supported data models, which are defined in
corehq.apps.linked_domain.const.ALL_LINKED_MODELS.

It is worth noting that some data models are only available with a specific feature flag enabled, and can be found in
corehq.apps.linked_domain.const.FEATURE_FLAG_DATA_MODELS.

Another important distinction to highlight is _individual_ data models vs _domain level_ data models. Individual data
models refer to any model that supports linking specific instances of that type. For instance, each app needs to be
linked _individually_. In contrast, domain level data models refer to any model that supports linking all values
associated with that type. An example is User Roles as linking individual user roles is not supported. All custom roles
associated with the upstream domain are linked to the downstream domain.

In the case of Apps, Reports, and Keywords, a linked copy must be created in the downstream domain before updates
can be pushed/pulled. Previously, this required explicitly creating a linked copy from data model specific UIs, but
**now apps are the only data models that need to be linked explicitly** from the app manager settings before being able
to push/pull updates. Reports and Keywords only require that they are **pushed** downstream first, and the link will be
created as part of this action.

The ability to edit linked data on a downstream domain depends on the data type. For example, applications are
read-only on downstream domains, with a few settings (controlled by
[supports_linked_app](https://github.com/dimagi/commcare-hq/blob/966b62cc113b56af771906def76833446b4ba025/corehq/apps/app_manager/static/app_manager/json/commcare-profile-settings.yml#L97))
that may be edited and will retain their
values even when the app is updated. Reports cannot be edited at all. Other data, such as user roles, can typically
be edited on the downstream domain, but any edits will be overwritten the next time that data type is
pushed/pulled.

Support for additional models is added as time permits. Any configuration-related data type could potentially be shared.
Project data like forms and cases would not be shared.


## Remote Links<a name="remote_links"></a>

### Remote Link Setup

#### From the upstream domain's HQ environment

Run the `add_downstream_domain` management command:

```
$ ./manage.py add_downstream_domain \
    --downstream_url {https://url.of.linked.hq/a/linked_domain_name/} \
    --upstream_domain {upstream_domain_name}
```

This gets used as a permissions check during remote requests to ensure
that the remote domain is allowed to sync from this domain.

#### From the downstream domain's HQ environment

Run the `link_to_upstream_domain` management command.
```
$ ./manage.py link_to_upstream_domain \
    --url_base {upstream base_url, eg: https://www.commcarehq.org} \
    --upstream_domain {upstream_domain_name} \
    --username {username} \
    --api_key {user_api_key} \
    --downstream_domain {downstream_domain_name}
```

The specified username and API key are needed to authenticate requests to the upstream environment.

### Pulling Changes From the Upstream Domain

On a downstream domain's HQ environment that has the `release_management` or `lite_release_management` permission, navigate to the
`Project Settings > Linked Project Spaces` page. Use the UI to pull changes from the upstream domain for all of the
[previously mentioned data models](#data_models) **except for keywords**. Keywords are not supported simply due to lack of necessity
in the context of remote links.

#### Linking Remote Applications

In order to link remote applications, you will need an existing application to reference in _both_ the upstream and downstream environments.
If needed, please create an application in the upstream and/or downstream environment(s) to reference in the following management command.

Once you have an upstream and downstream application ready to link, you can run `link_app_to_remote` from the downstream domain's
environment, using the IDs of the applications you intend to link:
```
$ ./manage.py link_app_to_remote \
    --downstream_id {downstream_app_id} \
    --upstream_id {upstream_app_id} \
    --url_base {upstream base_url, eg: https://www.commcarehq.org} \
    --domain {upstream_domain_name} \
    --username {username} \
    --api_key {api_key}
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

There are specific attributes set on the downstream application that are updated via the call to
[reapply_overrides](https://github.com/dimagi/commcare-hq/blob/4c5ebc4a1b6dbd6466f074f6b7fcfe1990eea992/corehq/apps/app_manager/models.py#L5776),
which occurs whenever an application is updated to ensure the downstream-specific attributes are not lost.

## Exclusions
A few fields are **not** copied from the upstream app to the downstream app. They include basic metadata (doc type, name, date created, comment, etc) and some build-related fields (build profiles and practice mobile workers). For the full list, see [excluded_fields in overwrite_app](https://github.com/dimagi/commcare-hq/blob/47b197378fc196ff25a88dc5b2c56a389aaec85f/corehq/apps/app_manager/views/utils.py#L165-L169).

## Overrides
A small number of settings can be overridden in a downstream app. App settings can be tagged with the `supports_linked_app` flag to make them appear on the downstream app's settings page.

## Multi-master
The `MULTI_MASTER_LINKED_DOMAINS` feature flag allows a downstream app to pull changes from more than one master app. The use case for multiple master apps is to support a branching-type workflow.

A downstream app may pull from all multiple upstream apps within a single "family." Families are created by copying apps; when an app is copied, its `family_id` is set to the id of the app it was copied from.

When this flag is on, different builds of the same downstream app may have different values for `upstream_app_id`. This id reflects the app that specific build was pulled from.

## Removing a link

Use the `unlink_apps` management command to convert a linked application to a regular application.

```
$ ./manage.py unlink_apps {downstream_app_id} {downstream_domain_name} {upstream_domain_name}
```
