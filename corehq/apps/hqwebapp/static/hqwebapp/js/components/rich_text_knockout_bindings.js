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

function imageHandler() {
    const self = this;
    const $modal = $('#rich-text-image-dialog');
    const imageInput = document.getElementById('rich-text-image');
    const uploadButton = document.getElementById('rich-text-image-upload');
    const uploadProgress = document.getElementById('rich-text-image-upload-in-progress');

    const handleImage = () => {
        const file = imageInput.files[0];
        if (!file) {
            alert(gettext('No File selected'));
            return;
        }
        uploadProgress.classList.remove("d-none");

        const uploadUrl = initialPageData.reverse("upload_messaging_image");
        let formData = new FormData();

        formData.append("upload", file, file.name);
        fetch(uploadUrl, {
            method: "POST",
            body: formData,
            headers: {
                "X-CSRFTOKEN": $("#csrfTokenContainer").val(),
            },
        })
            .then(function (response) {
                if (!response.ok) {
                    if (response.status === 400) {
                        return response.json().then(function (errorJson) {
                            throw Error(gettext('Failed to upload image: ') + errorJson.error.message);
                        });
                    }
                    throw Error(gettext('Failed to upload image. Please try again.'));
                }
                return response.json();
            })
            .then(function (data) {
                const Delta =  Quill.import("delta");
                const selectionRange = self.quill.getSelection(true);
                self.quill.updateContents(
                    new Delta()
                        .retain(selectionRange.index)
                        .delete(selectionRange.length)
                        .insert({
                            image: data.url,
                        }, {
                            alt: file.name,
                        }),
                );
            })
            .catch(function (error) {
                alert(error.message || gettext('Failed to upload image. Please try again.'));
            })
            .finally(function () {
                uploadProgress.classList.add("d-none");
            });


        imageInput.value = '';
        uploadButton.removeEventListener('click', handleImage);
        $modal.modal('hide');
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

        const handleInsert = () => {
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
            updateListType(child, level);
        }
    });
}

const parser = new DOMParser();

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
        });

        const value = ko.utils.unwrapObservable(valueAccessor());
        editor.clipboard.dangerouslyPasteHTML(value);

        let isSubscriberChange = false;
        let isEditorChange = false;

        editor.on("text-change", function () {
            if (!isSubscriberChange) {
                isEditorChange = true;
                const html = deltaToHtml(editor.getContents());
                valueAccessor()(html);
                isEditorChange = false;
            }
        });

        valueAccessor().subscribe(function (value) {
            if (!isEditorChange) {
                isSubscriberChange = true;
                editor.clipboard.dangerouslyPasteHTML(value);
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
