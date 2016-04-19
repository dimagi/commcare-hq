FormplayerFrontend.module("AppSelect.List", function (List, FormplayerFrontend, Backbone, Marionette, $, _) {
    List.AppSelect = Marionette.ItemView.extend({
        tagName: "tr",
        template: "#app-select-list-item"
    });

    List.AppSelectView = Marionette.CompositeView.extend({
        tagName: "table",
        className: "table table-hover",
        template: "#app-select-list",
        childView: List.AppSelect,
        childViewContainer: "tbody"
    });
});