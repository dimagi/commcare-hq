import "hqwebapp/js/htmx_and_alpine";
import $ from 'jquery';
import 'select2/dist/js/select2.full.min';

$(function () {
    $("#id_country_allowlist").select2();
});
