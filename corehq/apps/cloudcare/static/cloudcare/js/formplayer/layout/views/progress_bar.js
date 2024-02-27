/*global Marionette */

hqDefine("cloudcare/js/formplayer/layout/views/progress_bar", function () {
    var ProgressView = Marionette.View.extend({
        template: _.template($("#progress-view-template").html() || ""),

        initialize: function (options) {
            this.progressMessage = options.progressMessage;
        },

        templateContext: function () {
            return {
                progressMessage: this.progressMessage,
            };
        },

        hasProgress: function () {
            return +$(this.el).find('.js-progress-bar').width() > 0;
        },

        setProgress: function (done, total, duration) {
            if (done === 0) {
                $(this.el).find('.progress').addClass("hide");
                $(this.el).find('.js-loading').removeClass("hide");
            } else {
                if (hqImport('hqwebapp/js/toggles').toggleEnabled('USE_PROMINENT_PROGRESS_BAR')) {
                    $(this.el).find('.progress').css("height", "12px");
                    $(this.el).find('.progress-container').css("width", "50%");
                    $(this.el).find('.progress-title h1').css("font-size", "25px");
                    $(this.el).find('#formplayer-progress ').css("background-color", "rgba(255, 255, 255, 0.7)");
                }
                $(this.el).find('.progress').removeClass("hide");
                $(this.el).find('.js-loading').addClass("hide");
            }

            var progress = total === 0 ? 0 : done / total;
            // Due to jQuery bug, can't use .animate() with % until jQuery 3.0
            $(this.el).find('.js-progress-bar').css('transition', duration + 'ms');
            $(this.el).find('.js-progress-bar').width(progress * 100 + '%');
            if (total > 0 && !(hqImport('hqwebapp/js/toggles').toggleEnabled('USE_PROMINENT_PROGRESS_BAR'))) {
                $(this.el).find('.js-subtext small').text(
                    gettext('Completed: ') + done + '/' + total
                );
            }
        },
    });

    return function (options) {
        return new ProgressView(options);
    };
});

