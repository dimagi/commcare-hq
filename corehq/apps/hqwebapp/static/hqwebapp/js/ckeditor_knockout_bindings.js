hqDefine('hqwebapp/js/ckeditor_knockout_bindings', [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'ckeditor5',
    '@ckeditor/ckeditor5-editor-classic/build/editor-classic',
    '@ckeditor/ckeditor5-essentials/build/essentials',
    '@ckeditor/ckeditor5-basic-styles/build/basic-styles',
], function (
    $,
    _,
    ko,
    initialPageData,
    CKEditor5
) {
    ko.bindingHandlers.ckeditor = {
        init: function (element, valueAccessor, allBindingsAccessor, viewModel) {
            var options = {
                    simpleUpload: {
                        uploadUrl: initialPageData.reverse(element.attributes['data-image-upload-url'].value),
                        withCredentials: true,
                        headers: {
                            'X-CSRFTOKEN': $("#csrfTokenContainer").val(),
                        },
                    },
                    htmlSupport: {
                    // TODO: Only allow some html!
                        allow: [
                            {
                                name: /.*/,
                                attributes: true,
                                classes: true,
                                styles: true,
                            },
                        ],
                    },
                    plugins: [
                        CKEditor5.essentials.Essentials,
                        CKEditor5.basicStyles.Bold,
                        CKEditor5.basicStyles.Italic,
                        CKEditor5.paragraph.Paragraph,
                    ],
                    toolbar: {
                        items: ['bold', 'italic'],
                    },
                },
                editorInstance = undefined;

            CKEditor5.editorClassic.ClassicEditor.create(element, options).then(function (editor) {
                var isSubscriberChange = false,
                    isEditorChange = false,
                    editorInstance = editor;
                if (typeof ko.utils.unwrapObservable(valueAccessor()) !== "undefined") {
                    editorInstance.setData(ko.utils.unwrapObservable(valueAccessor()));
                }

                // Update the observable value when the document changes
                editorInstance.model.document.on('change:data', function (data) {
                    if (!isSubscriberChange) {
                        isEditorChange = true;
                        valueAccessor()(editorInstance.getData());
                        isEditorChange = false;
                    }
                    
                });

                // Update the document whenever the observable changes
                valueAccessor().subscribe(function (value) {
                    if (!isEditorChange) {
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
                CKEditor5.editorClassic.ClassicEditor.remove(editorInstance);
            });

        },
    };
});
