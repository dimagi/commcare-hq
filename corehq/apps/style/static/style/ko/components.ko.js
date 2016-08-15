/* global define, jQuery */
hqGlobal("style/ko/components.ko", ['jquery', 'knockout', 'underscore'], function($, ko, _) {

var components = {
    'inline-edit': 'style/ko/components/inline_edit.js'
};

_.each(components, function(moduleName, elementName) {
    ko.components.register(elementName, hqImport(moduleName));
});

$(document).ready(function() {
    _.each(_.keys(components), function(elementName) {
        _.each($(elementName), function(el) { $(el).koApplyBindings(); });
    });
});

});
