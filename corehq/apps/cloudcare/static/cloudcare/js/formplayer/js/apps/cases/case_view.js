FormplayerFrontend.module("AppSelect.CaseList", function (CaseList, FormplayerFrontend, Backbone, Marionette, $, _) {
    CaseList.CaseView = Marionette.ItemView.extend({
        tagName: "tr",
        template: "#case-view-item",

        events: {
            "click": "rowClick"
        },

        rowClick: function(e){
            e.preventDefault();
            FormplayerFrontend.trigger("menu:select", this.model);
        }
    });

    CaseList.CaseListView = Marionette.CompositeView.extend({
        tagName: "table",
        className: "table table-hover",
        template: "#case-view-list",
        childView: MenuList.MenuView,
        childViewContainer: "tbody"
    });
});