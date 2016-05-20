/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate.MenuList", function (MenuList, FormplayerFrontend, Backbone, Marionette) {
    MenuList.MenuView = Marionette.ItemView.extend({
        tagName: "tr",

        events: {
            "click": "rowClick",
        },

        getTemplate: function () {
            if (this.model.attributes.audioUri) {
                return "#menu-view-item-audio";
            } else {
                return "#menu-view-item";
            }
        },

        rowClick: function (e) {
            e.preventDefault();
            var model = this.model;
            FormplayerFrontend.trigger("menu:select", model.get('index'), model.collection.appId);
        },
        templateHelpers: function () {
            var imageUri = this.options.model.attributes.imageUri;
            var audioUri = this.options.model.attributes.audioUri;
            var appId = this.model.collection.appId;
            return {
                imageUrl: imageUri ? FormplayerFrontend.request('resourceMap', imageUri, appId) : "",
                audioUrl: audioUri ? FormplayerFrontend.request('resourceMap', audioUri, appId) : "",
            };
        },
    });

    MenuList.MenuListView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#menu-view-list",
        childView: MenuList.MenuView,
        childViewContainer: "tbody",
        templateHelpers: function () {
            return {
                title: this.options.collection.title,
            };
        },
    });

    MenuList.CaseView = Marionette.ItemView.extend({
        tagName: "tr",
        template: "#case-view-item",

        events: {
            "click": "rowClick",
        },

        rowClick: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("menu:show:detail", this);
        },

        templateHelpers: function () {
            return {
                data: this.options.model.attributes.data,
            };
        },
    });

    MenuList.CaseListView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#case-view-list",
        childView: MenuList.CaseView,
        childViewContainer: "tbody",

        ui: {
            button: '#double-management',
            paginators: '.page-link',
        },

        events: {
            'click @ui.button': 'caseListAction',
            'click @ui.paginators': 'paginateAction',
        },

        caseListAction: function () {
            FormplayerFrontend.trigger("menu:select", "action 0", this.options.collection.appId);
        },

        paginateAction: function (e) {
            var pageSelection = $(e.currentTarget).data("id");
            FormplayerFrontend.trigger("menu:paginate", pageSelection, this.options.collection.appId);
        },

        templateHelpers: function () {
            return {
                title: this.options.title,
                headers: this.options.headers,
                widthHints: this.options.widthHints,
                action: this.options.action,
                currentPage: this.options.currentPage,
                pageCount: this.options.pageCount,
            };
        },
    });

    MenuList.DetailView = Marionette.ItemView.extend({
        tagName: "tr",
        template: "#detail-view-item",
    });

    MenuList.DetailListView = Marionette.CompositeView.extend({
        tagName: "table",
        className: "table table-hover",
        template: "#detail-view-list",
        childView: MenuList.DetailView,
        childViewContainer: "tbody",
    });
});