import $ from 'jquery';
import initialPageData from 'hqwebapp/js/initial_page_data';
import 'hqwebapp/js/components/inline_edit';

$(function () {
    // notice how ids referenced in javascript are prefixed with js,
    // so it's clear to someone reading the HTML that there is associated js functionality
    $("#js-inline-edit-example").koApplyBindings(function () {
        let self = {};

        self.text = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.';

        self.url = initialPageData.reverse("styleguide_inline_edit_demo");

        return self;
    });
});
