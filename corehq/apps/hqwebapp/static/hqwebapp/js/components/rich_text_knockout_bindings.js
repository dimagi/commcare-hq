import ko from "knockout";

import "quill/dist/quill.snow.css";
import Quill from 'quill';
import Toolbar from "quill/modules/toolbar";
import Snow from "quill/themes/snow";
import Bold from "quill/formats/bold";
import Italic from "quill/formats/italic";
import Header from "quill/formats/header";

import initialPageData from "hqwebapp/js/initial_page_data";

Quill.register({
    "modules/toolbar": Toolbar,
    "themes/snow": Snow,
    "formats/bold": Bold,
    "formats/italic": Italic,
    "formats/header": Header,
});

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
                toolbar: toolbar,
            },
            theme: "snow",
        });

        let currentSelectionRange = { index: 0, length: 0};
        const insertImageButton = toolbar.querySelector("#insert-image");
        insertImageButton.addEventListener("click", function (clickEvent) {
            clickEvent.stopPropagation();
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
                        editor.updateContents(
                            new Delta()
                                .retain(currentSelectionRange.index)
                                .delete(currentSelectionRange.length)
                                .insert({
                                    image: data.url,
                                }, {
                                    // link: data.url,
                                    alt: file.name,
                                }),
                        );
                    });
            };

            input.click();
        });

        editor.on("selection-change", (range) => {
            if (range) {
                currentSelectionRange = range;
            }
        });

        const value = ko.utils.unwrapObservable(valueAccessor());
        editor.clipboard.dangerouslyPasteHTML(value);

        let isSubscriberChange = false;
        let isEditorChange = false;

        editor.on("text-change", function () {
            if (!isSubscriberChange) {
                isEditorChange = true;
                valueAccessor()(editor.root.innerHTML);
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
