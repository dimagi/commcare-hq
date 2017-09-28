({
    mainConfigFile: "corehq/apps/hqwebapp/static/hqwebapp/js/requirejs_config.js",
    baseUrl: 'staticfiles',
    fileExclusionRegExp: /(^\.)|(\.css$)|(CACHE)/,
    dir: 'staticfiles',
    allowSourceOverwrites: true,
    keepBuildDir: true,
    skipDirOptimize: true,  // could turn this off to minify everything (including bower_components), which takes a while
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
            name: "hqwebapp/js/bundle",
            exclude: ["hqwebapp/js/common"],
        },

        // App-specific modules
        {
            name: "fixtures/js/bundle",
            exclude: ["hqwebapp/js/common", "hqwebapp/js/bundle"],
        },
    ],
});
