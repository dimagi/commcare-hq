/*
 * Widget for creating/editing lists of key/value pairs
 * - collection: a knockout observable array whose elements look like
        {key: "My Key", value: "My Value"}
 */
hqDefine('hqwebapp/js/components/key_value_list', [
    'jquery',
    'knockout',
    'underscore',
], function (
    $,
    ko,
    _,
) {
    return {
        viewModel: function(params) {
            var self = this;
            self.keyHeader = params.keyHeader || "";
            self.valueHeader = params.valueHeader || "";
            self.btnText = params.btnText || "";

            if (!ko.isObservableArray(params.collection)) {
                throw "'collection' must be an observable Array"
            }
            self.collection = params.collection || {};

            self.addRow = function (e) {
                self.collection.push({key: '', value: ''});
            }
        },
        template: '<div data-bind="template: { name: \'ko-key-value-list-template\' }"></div>',
    };
});
