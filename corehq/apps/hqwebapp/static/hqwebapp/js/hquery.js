// bundles jquery plugins with jquery in one dependency
// otherwise we'd need to specify which ones are required each time
// which is nice and explicit, but makes it harder to adapt existing code
define([
    "jquery",
    "jquery.form",
    "bootstrap",
    "jquery.cookie",
    "jquery.hq",
], function($) {
    return $;
});
