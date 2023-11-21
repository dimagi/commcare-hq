hqDefine('hqwebapp/js/ckeditor_knockout_bindings', [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/lib/ckeditor5/ckeditor',
], function (
    $,
    _,
    ko,
    initialPageData,
    CKEditor
) {
    ko.bindingHandlers.ckeditor = function() {
        self.init = function (element, valueAccessor, allBindingsAccessor, viewModel) {
            var options = {
                htmlSupport: {
                    // TODO: Only allow some html!
                    allow: [
                        {
                            name: /.*/,
                            attributes: true,
                            classes: true,
                            styles: true
                        }
                    ]
                },
            },
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

                if (initialPageData.get('read_only_mode')) {
                    editorInstance.enableReadOnlyMode('');
                }
            });

            // handle disposal (if KO removes by the template binding)
            ko.utils.domNodeDisposal.addDisposeCallback(element, function () {
                CKEditor.remove(editorInstance);
            });

        };
        
        return self;
    }();
});
