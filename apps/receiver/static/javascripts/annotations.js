function show_annotations(attachment_id, div_id, pre_fill_text) {
    // uses jqModal to show annotations in an ajaxy way.  Pass in the attachment
    // to annotate, and the div where you want to display your ajax.
    $(div_id).jqm({
        ajax: '/receiver/annotations/' + attachment_id,
        trigger: 'div.annotationtrigger',
        ajaxText: 'Please wait while we load that for you'
    });

    // add pre-filled text to the text box (eg, mother name in the case of Intel)
    if (typeof(pre_fill_text) != 'undefined') {
        $(div_id).jqm({
            onLoad:function(){ $("#new_annotation").val(pre_fill_text) }
          });
    }
    
    $(div_id).jqmShow();
}