({
    mainConfigFile: "corehq/apps/hqwebapp/static/hqwebapp/js/requirejs_config.js",
    baseUrl: 'staticfiles',
    optimize: "none",
    fileExclusionRegExp: /(^\.)|(\.css$)/,
    dir: 'built',   // TODO: send to staticfiles instead, rather than copying, but r.js throws an error
    modules: [
        {
            name: "hqwebapp/js/common",
        },
        {
            name: "fixtures/js/built",
            exclude: ["hqwebapp/js/common"],
        },
    ],
});
