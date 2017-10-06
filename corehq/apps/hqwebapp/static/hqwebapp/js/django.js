/*
    Allow usage of gettext, RequireJS-style, rather than accessing the global django.
*/
define([], function() {
    return { gettext: django.gettext };
});
