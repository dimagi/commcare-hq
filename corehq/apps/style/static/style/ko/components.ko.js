var components = {
    'inline-edit': 'style/ko/components/inline_edit.js',
};

_.each(components, function(moduleName, elementName) {
    ko.components.register(elementName, hqImport(moduleName));
});

$(document).ready(function() {
    _.keys(components, function(elementName) {
        $(elementName).koApplyBindings();
    });
});
