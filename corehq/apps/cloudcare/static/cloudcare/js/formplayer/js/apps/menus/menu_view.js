FormplayerFrontend.module("AppSelect.MenuList", function (MenuList, FormplayerFrontend, Backbone, Marionette, $, _) {
    MenuList.MenuView = Marionette.ItemView.extend({
        tagName: "tr",
        template: "#menu-view-item",

        events: {
            "click": "rowClick"
        },

        rowClick: function (e) {
            e.preventDefault();
            var model = this.model;
            FormplayerFrontend.trigger("menu:select", model.attributes.index, model.collection.app_id);
        },
    });

    MenuList.MenuListView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#menu-view-list",
        childView: MenuList.MenuView,
        childViewContainer: "tbody",
        templateHelpers: function () {
            return {
                title: this.options.collection.title
            };
        },
    });

    MenuList.CaseView = Marionette.ItemView.extend({
        tagName: "tr",
        template: "#case-view-item",

        events: {
            "click": "rowClick"
        },

        rowClick: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("app:show:detail", this);
        },
    });

    MenuList.CaseListView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#case-view-list",
        childView: MenuList.CaseView,
        childViewContainer: "tbody",
        templateHelpers: function () {
            return {
                title: this.options.collection.title
            };
        },
    });

    MenuList.DetailView = Marionette.ItemView.extend({
        tagName: "tr",
        template: "#detail-view-item"
    });

    MenuList.DetailListView = Marionette.CompositeView.extend({
        tagName: "table",
        className: "table table-hover",
        template: "#detail-view-list",
        childView: MenuList.DetailView,
        childViewContainer: "tbody"
    });
});