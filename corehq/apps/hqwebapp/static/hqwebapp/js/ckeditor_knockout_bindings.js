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
    ko.bindingHandlers.ckeditor = {
        init: function (element, valueAccessor, allBindingsAccessor, viewModel) {
            var options = {
                simpleUpload: {
                    uploadUrl: initialPageData.reverse(element.attributes['data-image-upload-url'].value),
                    withCredentials: true,
                    headers: {
                        'X-CSRFTOKEN': $("#csrfTokenContainer").val(),
                    }
                },
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
                var isSubscriberChange = false,
                    isEditorChange = false,
                editorInstance = editor;

                if (typeof ko.utils.unwrapObservable(valueAccessor()) !== "undefined") {
                    editorInstance.setData(ko.utils.unwrapObservable(valueAccessor()));
                };

                // Update the observable value when the document changes
                editorInstance.model.document.on('change:data', function(data) {
                    if (!isSubscriberChange) {
                        isEditorChange = true;
                        valueAccessor()(editorInstance.getData());
                        isEditorChange = false;
                    }
                    
                });

                // Update the document whenever the observable changes
                valueAccessor().subscribe(function (value) {
                    if (!isEditorChange){
                        isSubscriberChange = true;
                        editorInstance.setData(value);
                        isSubscriberChange = false;
                    }

                });

                if (initialPageData.get('read_only_mode')) {
                    editorInstance.enableReadOnlyMode('');
                }
            });

            // handle disposal (if KO removes by the template binding)
            ko.utils.domNodeDisposal.addDisposeCallback(element, function () {
                CKEditor.remove(editorInstance);
            });

        }
    };
});
