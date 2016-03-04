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
<script src="{% new_static 'hqwebapp/js/hqModules.js' %}"></script>
<script src="{% new_static 'hqwebapp/js/toggles.js' %}"></script>
<script src="{% new_static 'style/js/bootstrap3/main.js' %}"></script>
```
