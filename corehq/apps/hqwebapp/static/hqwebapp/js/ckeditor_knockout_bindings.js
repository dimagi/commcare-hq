hqDefine('hqwebapp/js/ckeditor_knockout_bindings', [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/lib/ckeditor5/ckeditor',
], function (
    $,
    _,
    ko,
    CKEditor
) {
    ko.bindingHandlers.ckeditor = function() {
        self.init = function (element, valueAccessor, allBindingsAccessor, viewModel) {
            var options = allBindingsAccessor().richTextOptions || {},
                editorInstance = undefined;

            CKEditor.create(element, options).then(function(editor) {
                editorInstance = editor;

                if (typeof ko.utils.unwrapObservable(valueAccessor()) !== "undefined") {
                    editorInstance.setData(ko.utils.unwrapObservable(valueAccessor()));
                };

                editorInstance.model.document.on('change:data', function(data) {
                    // TODO: inline CSS here?
                    valueAccessor()(editorInstance.getData());
                });
            });

            // handle disposal (if KO removes by the template binding)
            ko.utils.domNodeDisposal.addDisposeCallback(element, function () {
                CKEditor.remove(editorInstance);
            });

        };
        
        return self;
    }();
});
