/*global FormplayerFrontend */

FormplayerFrontend.module("Utils.Views", function (Views, FormplayerFrontend, Backbone, Marionette) {

    Views.ProgressView = Marionette.ItemView.extend({
        template: "#progress-view-template",

        setProgress: function(progress) {
            $(this.el).find('.js-progress-bar').width(progress);
        },
    });
});

