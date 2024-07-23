'use strict';
/* global CKEditor5 */

// When adding a ckeditor binding, be sure to also add the name of an image upload url. 
// For example <textarea data-bind="ckeditor: message" data-image-upload-url="upload_messaging_image"></textarea>

hqDefine('hqwebapp/js/ckeditor_knockout_bindings', [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    _,
    ko,
    initialPageData
) {
    ko.bindingHandlers.ckeditor = {
        init: function (element, valueAccessor) {
            var options = {
                    plugins: [
                        CKEditor5.alignment.Alignment,
                        CKEditor5.link.AutoLink,
                        CKEditor5.autoformat.Autoformat,
                        CKEditor5.basicStyles.Bold,
                        CKEditor5.basicStyles.Italic,
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

            CKEditor5.editorClassic.ClassicEditor.create(element, options).then(function (editor) {
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
                CKEditor5.editorClassic.ClassicEditor.remove(editorInstance);
            });

        },
    };
});
