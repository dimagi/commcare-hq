/* global require */
import $ from "jquery";
import _ from "underscore";
import initialPageData from "hqwebapp/js/initial_page_data";
import noopMetrics from "analytix/js/noopMetrics";
import appManager from "app_manager/js/bootstrap3/app_manager";
import "jquery-ui/ui/widgets/sortable";
import "jquery-ui-built-themes/redmond/jquery-ui.min.css";

$(function () {
    var VELLUM_OPTIONS = _.extend({}, initialPageData.get("vellum_options"), {
        itemset: {
            dataSourcesFilter: function (sources) {
                return _.filter(sources, function (source) {
                    return !source.uri || /^jr:\/\/fixture\//.test(source.uri);
                });
            },
        },
        windowManager: {
            leftOffset: function () {
                return $('#hq-sidebar').outerWidth() + 2;
            },
            topOffset: function () {
                return $('#hq-navigation').outerHeight();
            },
            toggleFullScreenCallback: function (isFullscreen) {
                var $preview = $('#js-appmanager-preview');
                if (isFullscreen) {
                    $preview.addClass('fullscreen');
                } else {
                    $preview.removeClass('fullscreen');
                }
            },
        },
        csrftoken: $("#csrfTokenContainer").val(),
    });

    // Add callbacks to core, which has already been provided by the server
    VELLUM_OPTIONS.core = _.extend(VELLUM_OPTIONS.core, {
        formLoadingCallback: function () {
            $('#formdesigner').addClass('loading');
        },
        formLoadedCallback: function () {
            $('#formdesigner').removeClass('loading');
        },
    });
    VELLUM_OPTIONS.core = _.extend(VELLUM_OPTIONS.core, {
        onFormSave: function (data) {
            appManager.updateDOM(data.update);
            if (data.update?.['.variable-form_name']) {
                appManager.updatePageTitle(data.update['.variable-form_name']);
            }
            $('.js-preview-toggle').removeAttr('disabled');
            if (initialPageData.get("days_since_created") === 0) {
                noopMetrics.track.event('Saved the Form Builder within first 24 hours');
            }
        },
        onReady: function () {
            var noopMetricsTrack = function () {};
            if (initialPageData.get('days_since_created') === 0) {
                noopMetricsTrack = function () {
                    noopMetrics.track.event(
                        'Added question in Form Builder within first 24 hours',
                    );
                };
            }
            $("#formdesigner").vellum("get").data.core.form.on("question-create", function () {
                noopMetricsTrack();
            });
            document.dispatchEvent(new CustomEvent('vellum:ready'));
        },
    });

    const initVellum = function ($) {
        $(function () {
            $("#edit").hide();
            $('#hq-footer').hide();
            $('#formdesigner').vellum(VELLUM_OPTIONS);
        });
    };
    console.log("Loading vellum, debug = " + !!initialPageData.get('vellum_debug'));
    if (initialPageData.get('vellum_debug')) {
        require(["jquery", "jquery.vellum.dev"], initVellum);
    } else {
        require(["jquery", "jquery.vellum.prod"], initVellum);
    }
    noopMetrics.track.event('Entered the Form Builder');

    appManager.setPrependedPageTitle("\u270E ", true);
    appManager.setAppendedPageTitle(gettext("Edit Form"));

    // todo make this a more broadly used util, perhaps? actually add buttons to formplayer?
    var _prependTemplateToSelector = function (selector, layout, attempts, callback) {
        attempts = attempts || 0;
        if ($(selector).length) {
            var $toggleParent = $(selector);
            $toggleParent.prepend(layout);
            callback();
        } else if (attempts <= 30) {
            // give up appending element after waiting 30 seconds to load
            setTimeout(function () {
                _prependTemplateToSelector(selector, layout, attempts++, callback);
            }, 1000);
        }
    };

    if (initialPageData.get('form_uses_cases')) {
        // Show all 3 buttons for forms that use cases
        _prependTemplateToSelector(
            '.fd-form-actions',
            $('#js-fd-form-actions').html(),
            0,
            function () { },
        );
    } else {
        // Show only View Submissions button for survey forms
        _prependTemplateToSelector(
            '.fd-form-actions',
            $('#js-fd-view-submissions-only').html(),
            0,
            function () { },
        );
    }

    appManager.updatePageTitle(initialPageData.get("form_name"));
});
