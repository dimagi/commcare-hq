'use strict';

// When adding a ckeditor binding, be sure to also add the name of an image upload url.
// For example <textarea data-bind="ckeditor: message" data-image-upload-url="upload_messaging_image"></textarea>

hqDefine('hqwebapp/js/ckeditor_knockout_bindings', [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'ckeditor5/ckeditor5.js',   // needs the .js extension to differentiate from css and map files in the same directory
], function (
    $,
    _,
    ko,
    initialPageData,
    CKEditor5
) {
    ko.bindingHandlers.ckeditor = {
        init: function (element, valueAccessor) {
            var options = {
                    licenseKey: 'GPL',
                    plugins: [
                        CKEditor5.Alignment,
                        CKEditor5.AutoLink,
                        CKEditor5.Autoformat,
                        CKEditor5.Bold,
                        CKEditor5.Italic,
                        CKEditor5.Essentials,
                        CKEditor5.Font,
                        CKEditor5.FontColor,
                        CKEditor5.Heading,
                        CKEditor5.HorizontalLine,
                        CKEditor5.GeneralHtmlSupport,
                        CKEditor5.Image,
                        CKEditor5.ImageCaption,
                        CKEditor5.ImageStyle,
                        CKEditor5.ImageResize,
                        CKEditor5.ImageResizeButtons,
                        CKEditor5.ImageToolbar,
                        CKEditor5.ImageUpload,
                        CKEditor5.Indent,
                        CKEditor5.Link,
                        CKEditor5.LinkImage,
                        CKEditor5.List,
                        CKEditor5.Paragraph,
                        CKEditor5.PasteFromOffice,
                        CKEditor5.RestrictedEditingMode,
                        CKEditor5.SimpleUploadAdapter,
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
                            'alignment',
                            'bulletedList',
                            'numberedList',
                            'uploadImage',
                            '|',
                            'outdent',
                            'indent',
                            '|',
                            'undo',
                            'redo',
                            'restrictedEditing',
                        ],
                    },
                    image: {
                        insert: {
                            type: 'inline',
                        },
                        toolbar: [
                            'imageStyle:side',
                            '|',
                            'toggleImageCaption',
                            '|',
                            'linkImage',
                        ],
                    },
                    simpleUpload: {
                        uploadUrl: initialPageData.reverse(element.attributes['data-image-upload-url'].value),
                        withCredentials: true,
                        headers: {
                            'X-CSRFTOKEN': $("#csrfTokenContainer").val(),
                        },
                    },
                    htmlSupport: {
                    // We allow all HTML here, and filter it out in a sanitizing step
                        allow: [
                            {
                                name: /.*/,
                                attributes: true,
                                classes: true,
                                styles: true,
                            },
                        ],
                    },
                    restrictedEditing: {
                        allowedCommands: [
                            "alignment",
                            "fontColor",
                            "fontBackgroundColor",
                            "deleteForward",
                            "forwardDelete",
                            "delete",
                            "bold",
                            "italic",
                            "enter",
                            "selectAll",
                            "shiftEnter",
                            "insertText",
                            "input",
                            "undo",
                            "redo",
                            "fontFamily",
                            "fontSize",
                            "paragraph",
                            "insertParagraph",
                            "heading",
                            "horizontalLine",
                            "insertImage",
                            "replaceImageSource",
                            "imageInsert",
                            "imageTextAlternative",
                            "imageTypeInline",
                            "toggleImageCaption",
                            "imageStyle",
                            "resizeImage",
                            "imageResize",
                            "uploadImage",
                            "imageUpload",
                            "indent",
                            "outdent",
                            "link",
                            "unlink",
                            "numberedList",
                            "bulletedList",
                            "indentList",
                            "outdentList",
                        ],
                    },
                },
                editorInstance = undefined;

            CKEditor5.ClassicEditor.create(element, options).then(function (editor) {
                var isSubscriberChange = false,
                    isEditorChange = false,
                    editorInstance = editor;
                if (typeof ko.utils.unwrapObservable(valueAccessor()) !== "undefined") {
                    editorInstance.setData(ko.utils.unwrapObservable(valueAccessor()));
                }

                // Update the observable value when the document changes
                editorInstance.model.document.on('change:data', function () {
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
                CKEditor5.ClassicEditor.remove(editorInstance);
            });

        },
    };
});
