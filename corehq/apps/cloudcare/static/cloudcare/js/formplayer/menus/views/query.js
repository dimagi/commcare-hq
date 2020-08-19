/*global FormplayerFrontend */

FormplayerFrontend.module("Menus.Views", function (Views, FormplayerFrontend, Backbone, Marionette) {
    Views.QueryView = Marionette.LayoutView.extend({
        tagName: "tr",
        className: "formplayer-request",
        template: "#query-view-item-template",

        templateHelpers: function () {
            var imageUri = this.options.model.get('imageUri');
            var audioUri = this.options.model.get('audioUri');
            var appId = this.model.collection.appId;
            return {
                imageUrl: imageUri ? FormplayerFrontend.request('resourceMap', imageUri, appId) : "",
                audioUrl: audioUri ? FormplayerFrontend.request('resourceMap', audioUri, appId) : "",
            };
        },
    });

    Views.QueryTableView = Marionette.CollectionView.extend({
        childView: Views.QueryView,
        tagName: "tbody",
    });

    Views.QueryListView = Marionette.LayoutView.extend({
        tagName: "div",
        template: "#query-view-list-template",

        regions: {
            body: {
                el: 'table',
            },
        },
        onShow: function () {
            this.getRegion('body').show(new Views.QueryTableView({
                collection: this.collection,
            }));
        },

        initialize: function (options) {
            this.parentModel = options.collection.models;
        },

        templateHelpers: function () {
            return {
                title: this.options.title,
            };
        },

        ui: {
            submitButton: '#query-submit-button',
        },

        events: {
            'click @ui.submitButton': 'submitAction',
        },

        submitAction: function (e) {
            e.preventDefault();
            var payload = {};
            var fields = $(".query-field");
            var model = this.parentModel;
            fields.each(function (index) {
                if (this.value !== '') {
                    payload[model[index].get('id')] = this.value;
                }
            });
            FormplayerFrontend.trigger("menu:query", payload);
        },
    });
});
