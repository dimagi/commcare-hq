/* globals define */
/*
    Workaround for integrating djangojs with requirejs.
    djangojs.js creates a global django variable; the callback
    option in requirejs config in style/base.html then sets that
    global's gettext function to be a property of this module.
*/
define([], function() {
    return {};
});
