import $ from "jquery";

function customIconManager() {
    var self = {};

    const $customIconXpathInput = $("#custom_icon_xpath");
    const $customIconTextBodyInput = $("#custom_icon_text_body");

    var showXpathInput = function () {
        $customIconXpathInput.removeClass('hide');
        $customIconTextBodyInput.addClass('hide');
    };

    var showTextBodyInput = function () {
        $customIconTextBodyInput.removeClass('hide');
        $customIconXpathInput.addClass('hide');
    };

    self.init = function () {
        $('#custom-icon-type-select').on('change', function () {
            var selectedType = $(this).val();
            if (selectedType === "xpath") {
                showXpathInput();
            } else {
                showTextBodyInput();
            }
        });
    };

    return self;
}

export { customIconManager };
