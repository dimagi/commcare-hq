var casexml = (function () {
    'use strict';
    var casexml = {
        iso: function (date) {
            function ISODateString(d){
                function pad(n) {
                    return n < 10 ? '0' + n : n
                }
                return d.getUTCFullYear() + '-'
                    + pad(d.getUTCMonth() + 1) + '-'
                    + pad(d.getUTCDate()) + 'T'
                    + pad(d.getUTCHours()) + ':'
                    + pad(d.getUTCMinutes()) + ':'
                    + pad(d.getUTCSeconds()) + 'Z';
            }
        },
        update: function (kwargs) {
            var xml = $('<case/>'),
                case_id = kwargs.case_id,
                user_id = kwargs.user_id,
                owner_id = kwargs.owner_id;

            xml.attr({
                case_id: case_id,
                user_id: user_id,
                xmlns: 'http://commcarehq.org/case/transaction/v2',
                date_modified: casexml.iso(new Date())
            }).append(
                $('<update/>').append(
                    $('<owner_id/>').text(owner_id)
                )
            );
            return new XMLSerializer().serializeToString(xml[0]);
        }
    };
    return casexml;
}());