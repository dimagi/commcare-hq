'use strict';
hqDefine("cloudcare/js/formplayer/layout/views/progress_bar", [
    'jquery',
    'underscore',
    'backbone.marionette',
    'hqwebapp/js/toggles',
], function (
    $,
    _,
    Marionette,
    toggles
) {
    var ProgressView = Marionette.View.extend({
        template: _.template($("#progress-view-template").html() || ""),

        initialize: function (options) {
            this.progressMessage = options.progressMessage;
            this.progressEl = $(this.el);
        },

        templateContext: function () {
            return {
                progressMessage: this.progressMessage,
            };
        },

        hasProgress: function () {
            return +this.progressEl.find('.js-progress-bar').width() > 0;
        },

        setProgress: function (done, total, duration) {
            if (done === 0) {
                this.progressEl.find('.progress').addClass("hide");
                this.progressEl.find('.js-loading').removeClass("hide");
            } else {
                this.progressEl.find('.progress').removeClass("hide");
                this.progressEl.find('.js-loading').addClass("hide");
            }

            var progress = total === 0 ? 0 : done / total;
            // Due to jQuery bug, can't use .animate() with % until jQuery 3.0
            this.progressEl.find('.js-progress-bar').css('transition', duration + 'ms');
            this.progressEl.find('.js-progress-bar').width(progress * 100 + '%');
            if (total > 0 && !(toggles.toggleEnabled('USE_PROMINENT_PROGRESS_BAR'))) {
                this.progressEl.find('.js-subtext small').text(
                    gettext('Completed: ') + done + '/' + total
                );
            }
        },
    });

    return function (options) {
        return new ProgressView(options);
    };
});

