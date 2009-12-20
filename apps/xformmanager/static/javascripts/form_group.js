
function show_forms(xmlns, div_id) {
    // uses jqModal to show annotations in an ajaxy way.  Pass in the attachment
    // to annotate, and the div where you want to display your ajax.
    $(div_id).jqm({ajax: '/xforms/groups?xmlns=' + xmlns, trigger: 'div.formtrigger'});
}
