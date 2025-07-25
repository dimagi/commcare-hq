import $ from "jquery";
import ko from "knockout";

export default {
    register: function (name, component) {
        ko.components.register(name, component);

        $(function () {
            $(name).each(function (index, el) {
                var $el = $(el);
                if ($el.data('apply-bindings') !== false) {
                    $(el).koApplyBindings();
                }
            });
        });
    },
};
