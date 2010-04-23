
function show_annotations(attachment_id, div_id) {
    // uses jqModal to show annotations in an ajaxy way.  Pass in the attachment
    // to annotate, and the div where you want to display your ajax.
    $(div_id).jqm({ajax: '/receiver/annotations/' + attachment_id, trigger: 'div.annotationtrigger',
                   ajaxText: 'Please wait while we load that for you'});
}
