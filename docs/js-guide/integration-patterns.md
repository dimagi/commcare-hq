# Integration Patterns

Sometimes you want to have at your fingertips in client-side code
things that live primarily live on the server.
This interface between JavaScript code and the data
and systems we take for granted on the server can get messy and ugly.

This section lays out some conventions for getting the data you need
to your JavaScript code
and points you to some frameworks we've set up
for making particularly common things really easy.

## JavaScript in Django Templates

The `initial_page_data` template tag and `initial_page_data.js` library are for passing generic data from python to JavaScript.

In a Django template, use `initial_page_data` to register a variable. The data can be a template variable or a constant.

```
{% initial_page_data 'renderReportTables' True %}
{% initial_page_data 'defaultRows' report_table.default_rows|default:10 %}
{% initial_page_data 'tableOptions' table_options %}
```

Your JavaScript can then include `<script src="{% static 'hqwebapp/js/initial_page_data.js' %}"></script>` and access this data using the same names as in the Django template:

```
var get = hqImport('hqwebapp/js/initial_page_data').get,
    renderReportTables = get('renderReportTables'),
    defaultRows = get('defaultRows'),
    tableOptions = get('tableOptions');
```

When your JavaScript data is a complex object, it's generally cleaner to build it in your view than to pass a lot of variables through the Django template and then build it in JavaScript. So instead of a template with

```
{% initial_page_data 'width' 50 %}
{% initial_page_data 'height' 100 %}
{% initial_page_data 'thingType' type %}
{% if type == 'a' %}
    {% initial_page_data 'aProperty' 'yes' %}
{% else %}
    {% initial_page_data 'bProperty' 'yes' %}
{% endif %}
```

that then builds an object in JavaScript, when building your view context

```
options = {
    'width': 50,
    'height': 100,
    'thingType': type,
})
if type == 'a':
    options.update({'aProperty': 'yes'})
else:
    options.update({'bProperty': 'yes'})
context.update({'options': options})
```

and then use a single `{% initial_page_data 'thingOptions' %}` in your Django template.

It's common to see little bits of inline JavaScript initializing variables and calling constructor functions. This isn't ideal because it makes it harder to reason about when code is executed, particularly in JavaScript-heavy areas.

Note that the `initial_page_data` approach uses a global namespace (as does the inline JavaScript approach). That is a problem for another day. An error will be thrown if you accidentally register two variables with the same name with `initial_page_data`.

### Partials

The initial page data pattern can get messy when working with partials: the `initial_page_data` tag generally needs to go into a base template (a descendant of [hqwebapp/base.html](https://github.com/dimagi/commcare-hq/tree/master/corehq/apps/hqwebapp/templates/hqwebapp/base.html)), not the partial template, so you can end up with tags in a template - or multiple templates - not obviously related to the partial.

An alternative approach to passing server data to partials is to encode is as `data-` attributes. This can get out of hand if there's a lot of complex data to pass, but it often works well for partials that define a widget that just needs a couple of server-provided options. Report filters typically use this approach.


## I18n
Just like Django lets you use `ugettext('...')` in python
and `{% trans '...' %}`, you can also use `django.gettext('...')`
in any JavaScript.

For any page extending our main template, there's nothing further
you need to do to get this to work.
If you're interested in how it works,
any page with `<script src="{% statici18n LANGUAGE_CODE %}"></script>`
in the template will have access to the global `django` module
and its methods.

If `djangojs.js` is missing, you can run `./manage.py compilejsi18n` to regenerate it.

For more on Django JS I18n, check out https://docs.djangoproject.com/en/1.7/topics/i18n/translation/.

## Django URLs

Just like you might use `{% url ... %}` to resolve a URL in a template

```
<a href="{% url 'all_widget_info' domain %}">Widget Info</a>
```

(or `reverse(...)` to resolve a URL in python), you can use `{% registerurl %}` to make a URL available in javascript, through the initial_page_data.reverse utility (modeled after Django's python `reverse` function).

in template
```
{% registerurl 'all_widget_info' domain %}
```

in js

```
var initial_page_data = hqImport('hqwebapp/js/initial_page_data');

$.get(initial_page_data.reverse('all_widget_info')).done(function () {...});
```

As in this example, prefer inlining the call to `initial_page_data.reverse` over assigning its return value to a variable if there's no specific motivation for doing so.

In addition, you may keep positional arguments of the url unfilled by passing the special string `'---'` to `{% registerurl %}` and passing the argument value to `initial_page_data.reverse` instead.

in template
```
{% registerurl 'more_widget_info' domain '---' %}
```

in js

```
var initial_page_data = hqImport('hqwebapp/js/initial_page_data');
var widgetId = 'xxxx';
$.get(initial_page_data.reverse('more_widget_info', widgetId)).done(function () {...});
```

`registerurl` is essentially a special case of initial page data, and it gets messy when used in partials in the same way as initial page data. Encoding a url in a DOM element, in an attribute like `data-url`, is sometimes cleaner than using the `registerurl` template tag. See [partials](https://github.com/dimagi/js-guide/blob/master/integration-patterns.md#partials) above for more detail.


## Toggles and Feature Previews
In python you generally have the ability to check
at any point whether a toggle or feature preview is enabled
for a particular user on a particular domain.

In JavaScript it's even easier,
because the user and domain are preset for you.
To check, for example, whether the `IS_DEVELOPER` toggle is enabled, use

```javascript
COMMCAREHQ.toggleEnabled('IS_DEVELOPER')
```

and to check whether the `'ENUM_IMAGE'` feature preview
is enabled, use

```javascript
COMMCAREHQ.previewEnabled('ENUM_IMAGE')
```

and that's pretty much it.

On a page that doesn't inherit from our main templates, you'll also
have to include

```html
<script src="{% static 'hqwebapp/js/hqModules.js' %}"></script>
<script src="{% static 'hqwebapp/js/toggles.js' %}"></script>
<script src="{% static 'style/js/bootstrap3/main.js' %}"></script>
```

## Remote Method Invocation

We use our own `dimagi/jquery.rmi` library to post ajax calls to methods in Django Views that have been tagged to allow remote method invocation. Each RMI request creates a Promise for handling the server response.

`dimagi/jquery.rmi` was modeled after [Django-Angular's RMI](http://django-angular.readthedocs.org/en/latest/remote-method-invocation.html)), and currently relies on a portion of that library to handle server responses.

The [README for dimagi/jquery.rmi](http://github.com/dimagi/jquery.rmi) has excellent instructions for usage.

The `notifications` app is a good example resource to study how to use this library:

- `NotificationsServiceRMIView` is an example of the type of view that can accept RMI posts.
- `NotificationsService.ko.js` is an example of the client-side invocation and handling.
- `style/bootstrap3/base.html` has a good example for usage of `NotificationsService`.
```html
<script type="text/javascript" src="{% static '/notifications/js/NotificationsService.ko.js' %}"></script>
<script type="text/javascript">
    $(function () {
        $('#js-settingsmenu-notifications').startNotificationsService('{% url 'notifications_service' %}');
    });
</script>
```

NOTE: It is not always the case that the RMI view is a separate view from the one hosting the client-side requests and responses. More often it's the same view, but the current examples are using Angular.js as of this writing.
