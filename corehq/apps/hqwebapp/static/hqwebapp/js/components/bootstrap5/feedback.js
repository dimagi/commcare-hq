/**
 *  Knockout Feedback Component
 *
 *  Include the <feedback> element on on your knockout page to add the feedback widget.
 *
 *  Required parameters:
 *      featureName: The name of the feature a user is giving feedback on
 *
 *  Optional parameters:
 *      url: specify the url where to submit the feedback to. By default it will use
 *           the submit_feedback view, which requires a login and domain being present.
 *
 */

hqDefine('hqwebapp/js/components/bootstrap5/feedback', [
    'knockout',
    'jquery',
    'hqwebapp/js/initial_page_data',
], function (
    ko,
    $,
    initialPageData
) {
    'use strict';
    return {
        viewModel: function (params) {
            let self = {};

            if (!params.featureName) {
                throw new Error("Please specify a featureName in params.");
            }

            self.featureName = ko.observable(params.featureName);
            self.rating = ko.observable();
            self.additionalFeedback = ko.observable();
            self.showSuccess = ko.observable(false);

            self.rateBad = function () {
                self.rating(1);
            };

            self.rateOk = function () {
                self.rating(2);
            };

            self.rateGood = function () {
                self.rating(3);
            };

            self.submit = function () {
                $.ajax({
                    url: params.url || initialPageData.reverse('submit_feedback'),
                    method: 'post',
                    dataType: 'json',
                    data: {
                        featureName: self.featureName(),
                        rating: self.rating(),
                        additionalFeedback: self.additionalFeedback(),
                    },
                })
                    .done(function (data) {
                        if (data.success) {
                            self.showSuccess(true);
                        }
                    });
            };

            return self;
        },
        template: '<div data-bind="template: { name: \'ko-feedback-template\' }"></div>',
    };
});
