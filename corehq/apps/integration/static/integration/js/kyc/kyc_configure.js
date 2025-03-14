import $ from "jquery";
import baseAce from "hqwebapp/js/base_ace";
import "hqwebapp/js/htmx_and_alpine";

document.body.addEventListener("htmx:afterSwap", function () {
    const $jsonField = $("#api-mapping").find("textarea");
    if (!$jsonField) {
        return;
    }

    // We need to wait for the JSON field to be rendered before initializing the Ace editor
    setTimeout(() => {
        const jsonWidget = baseAce.initJsonWidget($jsonField);
        const fieldVal = $jsonField.val();
        jsonWidget.getSession().setValue(fieldVal);
    }, 50);
});
