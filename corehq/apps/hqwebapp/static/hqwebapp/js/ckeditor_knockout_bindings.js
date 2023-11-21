hqDefine('hqwebapp/js/ckeditor_knockout_bindings', [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'ckeditor5',
    '@ckeditor/ckeditor5-editor-classic/build/editor-classic',
    '@ckeditor/ckeditor5-autoformat/build/autoformat',
    '@ckeditor/ckeditor5-basic-styles/build/basic-styles',
    '@ckeditor/ckeditor5-block-quote/build/block-quote',
    '@ckeditor/ckeditor5-essentials/build/essentials',
    '@ckeditor/ckeditor5-font/build/font',
    '@ckeditor/ckeditor5-heading/build/heading',
    '@ckeditor/ckeditor5-html-support/build/html-support',
    '@ckeditor/ckeditor5-horizontal-line/build/horizontal-line',
    '@ckeditor/ckeditor5-image/build/image',
    '@ckeditor/ckeditor5-indent/build/indent',
    '@ckeditor/ckeditor5-link/build/link',
    '@ckeditor/ckeditor5-list/build/list',
    '@ckeditor/ckeditor5-paste-from-office/build/paste-from-office',
    '@ckeditor/ckeditor5-restricted-editing/build/restricted-editing',
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
                        CKEditor5.link.AutoLink,
                        CKEditor5.autoformat.Autoformat,
                        CKEditor5.basicStyles.Bold,
                        CKEditor5.basicStyles.Italic,
                        CKEditor5.blockQuote.BlockQuote,
                        CKEditor5.essentials.Essentials,
                        CKEditor5.font.Font,
                        CKEditor5.font.FontColor,
                        CKEditor5.heading.Heading,
                        CKEditor5.horizontalLine.HorizontalLine,
                        CKEditor5.htmlSupport.GeneralHtmlSupport,
                        CKEditor5.image.Image,
                        CKEditor5.image.ImageCaption,
                        CKEditor5.image.ImageStyle,
                        CKEditor5.image.ImageResize,
                        CKEditor5.image.ImageResizeButtons,
                        CKEditor5.image.ImageToolbar,
                        CKEditor5.image.ImageUpload,
                        CKEditor5.indent.Indent,
                        CKEditor5.link.Link,
                        CKEditor5.link.LinkImage,
                        CKEditor5.list.List,
                        CKEditor5.paragraph.Paragraph,
                        CKEditor5.pasteFromOffice.PasteFromOffice,
                        CKEditor5.restrictedEditing.RestrictedEditingMode,
                        CKEditor5.upload.SimpleUploadAdapter,
                    ],
                    toolbar: {
                        items: [
                            'heading',
                            'fontFamily',
                            'fontSize',
                            'fontColor',
                            '|',
                            'bold',
                            'italic',
                            'link',
                            'bulletedList',
                            'numberedList',
                            '|',
                            'outdent',
                            'indent',
                            '|',
                            'uploadImage',
                            'blockQuote',
                            'undo',
                            'redo',
                            'restrictedEditing',
                        ],
                    },
                    image: {
                        toolbar: [
                            'imageStyle:block',
                            'imageStyle:side',
                            '|',
                            'toggleImageCaption',
                            '|',
                            'linkImage',
                        ],
                    },
                    restrictedEditing: {
                        allowedCommands: ['bold'],
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
