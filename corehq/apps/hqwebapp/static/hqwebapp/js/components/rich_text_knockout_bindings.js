import ko from "knockout";

import "quill/dist/quill.snow.css";
import "hqwebapp/js/components/quill.css";
import Quill from 'quill';
import Toolbar from "quill/modules/toolbar";
import Snow from "quill/themes/snow";
import Bold from "quill/formats/bold";
import Italic from "quill/formats/italic";
import Header from "quill/formats/header";
import {QuillDeltaToHtmlConverter} from 'quill-delta-to-html';

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
    const input = document.createElement("input");
    input.accept = "image/png, image/jpeg";
    input.type = "file";
    input.onchange = function (onChangeEvent) {
        const file = onChangeEvent.target.files[0];
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
            });
    };
    input.click();
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
                const converter = new QuillDeltaToHtmlConverter(editor.getContents().ops, {});
                const html = converter.convert();
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
