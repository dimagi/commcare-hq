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

We've talked about JavaScript in Django templates before,
but it's worth mentioning again that the most common integration
pattern you'll see for initializing your JavaScript function and
models with data from the server is to dump them
in your template into little bits of JavaScript that initialize
the rest of your code. If you're separating this step
from the rest of the code, then you're following our current best
practice.

However, having to pass everything you need through this boilerplate
can be pretty messy, so for some very common state, we have better
systems that you should use instead.

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

For more on Django JS I18n, check out https://docs.djangoproject.com/en/1.7/topics/i18n/translation/.

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

`dimagi/jquery.rmi` was modeled after [Djangular's RMI](http://django-angular.readthedocs.org/en/latest/remote-method-invocation.html)), and currently relies on a portion of that library to handle server responses.

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
