(function () {
    var components = {
        'inline-edit': 'hqwebapp/js/components/inline_edit',
        'pagination': 'hqwebapp/js/components/pagination',
    };

    _.each(components, function(moduleName, elementName) {
        ko.components.register(elementName, hqImport(moduleName));
    });

    $(function() {
        _.each(_.keys(components), function(elementName) {
            _.each($(elementName), function(el) {
                var $el = $(el);
                if (!($el.data('apply-bindings') === false)) {
                    $(el).koApplyBindings();
                }
            });
        });
    });
}());
