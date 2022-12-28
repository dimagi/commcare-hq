/* global django */
/*
    Allow usage of gettext, RequireJS-style, rather than accessing the global django.
*/
define([], function () {
    return { gettext: window.django ? django.gettext : undefined };
});
