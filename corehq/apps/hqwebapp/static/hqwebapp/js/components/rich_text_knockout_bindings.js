import ko from "knockout";

import "quill/dist/quill.snow.css";
import "hqwebapp/js/components/quill.css";
import Quill from 'quill';
import Toolbar from "quill/modules/toolbar";
import Snow from "quill/themes/snow";
import Bold from "quill/formats/bold";
import Italic from "quill/formats/italic";
import Header from "quill/formats/header";
import {QuillDeltaToHtmlConverter} from 'quill-delta-to-html-upate';
import $ from "jquery";

import initialPageData from "hqwebapp/js/initial_page_data";

Quill.register({
    "modules/toolbar": Toolbar,
    "themes/snow": Snow,
    "formats/bold": Bold,
    "formats/italic": Italic,
    "formats/header": Header,
});

const parser = new DOMParser();

const editorImages = new WeakMap();

const fullDomain = window.location.origin;

function extractImages(html) {
    const images = new Set();
    if (!html) {
        return images;
    }

    const doc = parser.parseFromString(html, 'text/html');
    const imgElements = doc.querySelectorAll('img');

    imgElements.forEach(img => {
        const src = img.getAttribute('src');
        if (src && src.startsWith(fullDomain)) {
            images.add(src);
        }
    });

    return images;
}

function deleteUnusedImages(editor, newImages) {
    const oldImages = editorImages.get(editor) || new Set();
    for (const oldImage of oldImages) {
        if (!newImages.has(oldImage)) {
            const deleteUrl = oldImage.replace("download", "delete");
            fetch(deleteUrl, {
                method: "DELETE",
                headers: {
                    "X-CSRFTOKEN": $("#csrfTokenContainer").val(),
                },
            });
        }
    }
}

/**
 * Upload an image file and insert it into the Quill editor
 *
 * @param {File} file - The image file to upload
 * @param {Quill} editor - The Quill editor instance
 * @param {Object} options - Additional options
 * @param {Function} options.onStart - Called when upload starts
 * @param {Function} options.onComplete - Called when upload completes
 * @param {Function} options.onError - Called when an error occurs
 * @returns {Promise<void>}
 */
async function uploadAndInsertImage(file, editor, options = {}) {
    if (!file) {
        alert(gettext('No File selected'));
        return;
    }

    if (options.onStart) {
        options.onStart();
    }

    const uploadUrl = initialPageData.reverse("upload_messaging_image");
    let formData = new FormData();
    formData.append("upload", file, file.name || "image");

    try {
        const response = await fetch(uploadUrl, {
            method: "POST",
            body: formData,
            headers: {
                "X-CSRFTOKEN": $("#csrfTokenContainer").val(),
            },
        });

        if (!response.ok) {
            if (response.status === 400) {
                const errorJson = await response.json();
                throw Error(gettext('Failed to upload image: ') + errorJson.error.message);
            }
            throw Error(gettext('Failed to upload image. Please try again.'));
        }

        const data = await response.json();
        const Delta = Quill.import("delta");
        const selectionRange = editor.getSelection(true) || { index: editor.getLength(), length: 0 };

        editor.updateContents(
            new Delta()
                .retain(selectionRange.index)
                .delete(selectionRange.length)
                .insert({
                    image: data.url,
                }, {
                    alt: file.name || "image",
                }),
        );

        // Track the image in editorImages
        const editorImageSet = editorImages.get(editor) || new Set();
        editorImageSet.add(data.url);
        editorImages.set(editor, editorImageSet);

        if (options.onComplete) {
            options.onComplete(data);
        }
    } catch (error) {
        if (options.onError) {
            options.onError(error);
        } else {
            alert(error.message || gettext('Failed to upload image. Please try again.'));
        }
    }
}

function imageHandler() {
    const self = this;
    const $modal = $('#rich-text-image-dialog');
    const imageInput = document.getElementById('rich-text-image');
    const uploadButton = document.getElementById('rich-text-image-upload');
    const uploadProgress = document.getElementById('rich-text-image-upload-in-progress');

    const handleImage = async function () {
        const file = imageInput.files[0];

        await uploadAndInsertImage(file, self.quill, {
            onStart: function () {
                uploadProgress.classList.remove("d-none");
            },
            onComplete: function () {
                imageInput.value = '';
                uploadButton.removeEventListener('click', handleImage);
                $modal.modal('hide');
            },
            onError: function (error) {
                alert(error.message || gettext('Failed to upload image. Please try again.'));
            },
        }).finally(function () {
            uploadProgress.classList.add("d-none");
        });
    };

    uploadButton.addEventListener('click', handleImage);
    $modal.modal();
}

async function linkHandler(value) {
    const self = this;
    const linkTextInputGroup = document.getElementById('rich-text-link-text-group');
    const linkTextInput = document.getElementById('rich-text-link-text');
    const selection = self.quill.getSelection();
    if (selection.length === 0) {
        linkTextInputGroup.classList.remove("d-none");
    } else {
        linkTextInputGroup.classList.add("d-none");
    }
    if (value) {
        const $modal = $('#rich-text-link-dialog');
        const linkUrlInput = document.getElementById('rich-text-link-url');
        const insertButton = document.getElementById('rich-text-link-insert');

        const handleInsert = function () {
            let href = linkUrlInput.value.trim();
            if (!href) {
                return;
            }

            if (!href.match(/^(https?|ftp|mailto):/)) {
                href = "https://" + href;
            }
            if (selection.length === 0) {
                const text = linkTextInput.value;
                self.quill.insertText(selection.index, text);
                self.quill.setSelection({index: selection.index, length: text.length});
                self.quill.format('link', href);
                self.quill.setSelection({index: selection.index + text.length, length: 0});
            } else {
                self.quill.format('link', href);
            }

            linkTextInput.value = '';
            linkUrlInput.value = '';
            insertButton.removeEventListener('click', handleInsert);
            $modal.modal('hide');
        };

        insertButton.addEventListener('click', handleInsert);
        $modal.modal();
    }
}

const converterOptions = {
    inlineStyles: true,
    linkTarget: "",
};

const orderedListTypes = ["1", "a", "i"];

/**
 * Update the type of nested ordered lists recursively based on the given level.
 *
 * @param {HTMLElement} element - The HTML element containing the list.
 * @param {number} level - The current level of nesting for the list elements.
 *
 * @return {void}
 */
function updateListType(element, level) {
    element.childNodes.forEach(function (child) {
        if (child.tagName && child.tagName.toLowerCase() === 'ol') {
            child.type = orderedListTypes[level % orderedListTypes.length];
            updateListType(child, level + 1);
        } else {
            if (child.tagName && child.tagName.toLowerCase() === 'ul') {
                child.type = 'disc';
            }
            updateListType(child, level);
        }
    });
}

/**
 * Convert quill delta to html
 *
 * @param {object} delta - Delta representation of the text to be converted to HTML.
 * @returns {string} - HTML page converted from the given Delta object, including html
 * and body tags
 */
function deltaToHtml(delta) {
    // nice for adding more test data
    // console.log(JSON.stringify(delta, null, 4));
    if (!delta) {
        return "";
    }
    const converter = new QuillDeltaToHtmlConverter(delta.ops, converterOptions);
    const body = converter.convert();

    const xmlDoc = parser.parseFromString(body, "text/html");
    updateListType(xmlDoc, 0);
    const html = `<html><body>${xmlDoc.querySelector("body").innerHTML}</body></html>`;
    return html;
}

ko.bindingHandlers.richEditor = {
    init: function (element, valueAccessor) {
        const fontFamilyArr = [
            "Arial",
            "Courier New",
            "Georgia",
            "Lucida Sans Unicode",
            "Tahoma",
            "Times New Roman",
            "Trebuchet MS",
            "Verdana",
        ];
        let fonts = Quill.import("attributors/style/font");
        fonts.whitelist = fontFamilyArr;
        Quill.register(fonts, true);

        const toolbar = element.parentElement.querySelector("#ql-toolbar");
        const editor = new Quill(element, {
            modules: {
                toolbar: {
                    container: toolbar,
                    handlers: {
                        image: imageHandler,
                        link: linkHandler,
                    },
                },
            },
            theme: "snow",
            // Disable Quill's native clipboard and drop handling
            clipboard: {
                matchVisual: false,
            },
        });

        // Handle paste events in the capture phase to intercept before Quill's handlers
        editor.root.addEventListener('paste', function (e) {
            if (initialPageData.get("read_only_mode")) {
                return;
            }

            if (e.clipboardData && e.clipboardData.items) {
                const items = e.clipboardData.items;

                for (let i = 0; i < items.length; i++) {
                    if (items[i].type.indexOf('image') !== -1) {
                        // Prevent default and stop propagation to avoid Quill's handling
                        e.preventDefault();
                        e.stopPropagation();

                        const file = items[i].getAsFile();
                        if (!file) {
                            continue;
                        }

                        uploadAndInsertImage(file, editor);
                        break; // Only handle the first image
                    }
                }
            }
        }, true); // Using capture phase to intercept before Quill's handlers

        // Completely disable Quill's drop handler
        editor.root.addEventListener('drop', function (e) {
            e.stopPropagation();
        }, true);

        // Handle drag and drop images
        editor.root.addEventListener('dragover', function (e) {
            e.preventDefault();
            e.stopPropagation();
            return false;
        }, { capture: true });

        editor.root.addEventListener('dragleave', function (e) {
            e.preventDefault();
            e.stopPropagation();
            return false;
        }, { capture: true });

        editor.root.addEventListener('drop', function (e) {
            // This needs to happen before anything else
            e.preventDefault();
            e.stopPropagation();
            if (initialPageData.get("read_only_mode")) {
                return false;
            }

            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                const file = e.dataTransfer.files[0];

                if (file.type.indexOf('image') !== -1) {
                    uploadAndInsertImage(file, editor);
                } else {
                    // Handle non-image files
                    const reader = new FileReader();
                    reader.onload = function (e) {
                        const range = editor.getSelection() || { index: editor.getLength(), length: 0 };
                        editor.insertText(range.index, e.target.result);
                    };
                    reader.readAsText(file);
                }
            } else if (e.dataTransfer.getData('text')) {
                // Handle text drag and drop
                const text = e.dataTransfer.getData('text');
                const range = editor.getSelection() || { index: editor.getLength(), length: 0 };
                editor.insertText(range.index, text);
            }

            return false;
        }, true);

        const value = ko.utils.unwrapObservable(valueAccessor());
        editor.clipboard.dangerouslyPasteHTML(value);
        editorImages.set(editor, extractImages(value));
        let isSubscriberChange = false;
        let isEditorChange = false;

        editor.on("text-change", function () {
            if (!isSubscriberChange) {
                isEditorChange = true;
                const html = deltaToHtml(editor.getContents());
                const newImages = extractImages(html);
                deleteUnusedImages(editor, newImages);
                editorImages.set(editor, newImages);
                valueAccessor()(html);
                isEditorChange = false;
            }
        });

        valueAccessor().subscribe(function (value) {
            if (!isEditorChange) {
                isSubscriberChange = true;

                editor.clipboard.dangerouslyPasteHTML(value);

                const newImages = extractImages(value);
                deleteUnusedImages(editor, newImages);
                editorImages.set(editor, newImages);

                isSubscriberChange = false;
            }
        });

        if (initialPageData.get("read_only_mode")) {
            editor.enable(false);
        }
    },
};

export {
    deltaToHtml,
    updateListType,
};
