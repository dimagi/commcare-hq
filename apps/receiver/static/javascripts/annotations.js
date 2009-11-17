
/*
function show_annotations(attachment_id, div_id) {
    // uses jqModal to show annotations in an ajaxy way.  Pass in the attachment
    // to annotate, and the div where you want to display your ajax.
    $(div_id).jqm({ajax: '/receiver/annotations/' + attachment_id, trigger: 'div.annotationtrigger'});
}

rO - Nov 17 HACK
*/

function show_annotations(end_of_url, div_id) {
    // uses jqModal to show annotations in an ajaxy way.  Pass in the attachment
    // to annotate, and the div where you want to display your ajax.
    $(div_id).jqm({ajax: '/receiver/annotations/' + end_of_url, trigger: 'div.annotationtrigger'});
}