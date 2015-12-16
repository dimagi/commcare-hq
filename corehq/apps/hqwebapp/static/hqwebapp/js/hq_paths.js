requirejs.config({
    paths: {
        // TODO autogenerate this file?
        // Note that there's no trailing `.js`

        // jQuery and friends
        // hquery is jquery with various plugins included
        // ideally we'd call it jquery, but other libs expect the plain,
        // unmodified jquery to be called "jquery", so that gets confusing
        // for more, see: http://requirejs.org/docs/jquery.html#modulename
        "hquery": "/static/hqwebapp/js/hquery",
        "jquery": "/static/jquery/dist/jquery.min",
        "bootstrap": "/static/style/lib/bootstrap-3.2.0/dist/js/bootstrap.min",
        "jquery.form": "/static/jquery-form/jquery.form",
        "jquery.cookie": "/static/jquery.cookie/jquery.cookie",
        "jquery.hq": "/static/style/js/hq_extensions.jquery",

        "jquery17": "/static/jquery-1.7.1-legacy/jquery",
        "knockout": "/static/knockout/dist/knockout",
        "underscore": "/static/underscore/underscore",
        "underscore-mixins": "/static/style/js/underscore-mixins",

    },
    shim: {
        "jquery.form": ["jquery"],
        "bootstrap": ["jquery"],
        "jquery.cookie": ["jquery"],
        "jquery.hq": ["jquery"],
    },
});
