(function () {
    var components = {
        'inline-edit': 'style/js/components/inline_edit.js',
        'inline-edit-v2': 'style/js/components/inline_edit_v2.js'
    };

    _.each(components, function(moduleName, elementName) {
        ko.components.register(elementName, hqImport(moduleName));
    });

    $(function() {
        _.each(_.keys(components), function(elementName) {
            _.each($(elementName), function(el) {
                var $el = $(el);
                if (!$el.closest('.ko-template').length) {
                    $(el).koApplyBindings();
                }
            });
        });
    });
}());
