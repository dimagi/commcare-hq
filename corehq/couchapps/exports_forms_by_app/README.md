# The `export_forms/by_xmlns` Map-Reduce View

## Output format

The view uses a fairly non-standard reduce to interleave information from
applications and form submissions. Here is an overview of the output format.

### Emit Value

`exports_forms/by_xmlns` outputs information in the following format:

```js
{
    xmlns: string,
    app: {name: string, langs: [string], id: string},
    is_user_registration: bool,
    module: {name: {*: string}, id: int},
    form: {name: {*: string}, id: int},
    app_deleted: bool,
    submissions: int
}
```

When reduced, this has the effect of

1. Listing out all possible combinations seen of (domain, app, xmlns)
   in apps or submissions
2. Giving info aobut the accociated app form if applicable
3. Counting how many forms have been submitted in that category

### Emit Key

There are three basic key types. The main one is

- `[domain, app_id, xmlns]`

but there are also two others that split out the sources of this info into
just apps or just form submissions:

- `['^XFormInstance', domain, app_id, xmlns]`
- `['^Application', domain, xmlns]`



## Usages in our code

There are only 5 usages of this view in our code. I've outlined them below.

### With reduce

- [corehq/apps/app_manager/models.py](https://github.com/dimagi/commcare-hq/blob/23740fd5943a82c3f5a4afeeb91860a05d852a9e/corehq/apps/app_manager/models.py#L3288-3288)
  - `key=[domain, {}, xmlns]`
  - Get info forms in `domain` that have `xmlns` (regardless of app)
- [corehq/apps/reports/display.py](https://github.com/dimagi/commcare-hq/blob/23740fd5943a82c3f5a4afeeb91860a05d852a9e/corehq/apps/reports/display.py#L85-85)
  - `key=[domain, app_id, xmlns]`
  - Get info forms in `domain` in app with `app_id` that have `xmlns`
- [corehq/apps/reports/standard/export.py](https://github.com/dimagi/commcare-hq/blob/23740fd5943a82c3f5a4afeeb91860a05d852a9e/corehq/apps/reports/standard/export.py#L109-109)
  - `startkey=[self.domain], endkey=[self.domain, {}]`
  - Get a list of all "classes" of forms that are either in an app or submitted,
    broken down by (domain, app_id, xmlns).
    Some forms (either old or not submitted through the phone)
    are not associated with an app; they'll have a null app_id.

### Without reduce

- [corehq/apps/cleanup/views.py](https://github.com/dimagi/commcare-hq/blob/23740fd5943a82c3f5a4afeeb91860a05d852a9e/corehq/apps/cleanup/views.py#L36-36)
  - `key=['^XFormInstance', domain, app_id, xmlns]` with `include_docs`
  - Get all forms that were submitted in `domain` against `app_id` with `xmlns`
- [corehq/apps/reports/standard/export.py](https://github.com/dimagi/commcare-hq/blob/23740fd5943a82c3f5a4afeeb91860a05d852a9e/corehq/apps/reports/standard/export.py#L130-130)
  - `startkey=['^Application', self.domain], endkey=['^Application', self.domain, {}]`
  - Get info for all apps in a domain
