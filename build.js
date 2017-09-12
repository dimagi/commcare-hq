({
    mainConfigFile: "corehq/apps/hqwebapp/static/hqwebapp/js/requirejs_config.js",
    baseUrl: 'staticfiles',
    optimize: "none",
    fileExclusionRegExp: /(^\.)|(\.css$)/,
    dir: 'built',   // TODO: send to staticfiles instead, rather than copying, but r.js throws an error
    modules: [
        // Third-party modules
        {
            name: "hqwebapp/js/common",
        },
        {
            name: "hqwebapp/js/jquery-ui",
            exclude: ["hqwebapp/js/common"],
        },

        // Modules common to HQ
        {
            name: "hqwebapp/js/built",
            exclude: ["hqwebapp/js/common"],
        },

        // App-specific modules
        {
            name: "fixtures/js/built",
            exclude: ["hqwebapp/js/common", "hqwebapp/js/built"],
        },
    ],
});
