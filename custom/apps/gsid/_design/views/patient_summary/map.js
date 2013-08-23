function (doc) {
    //!code util/emit_array.js 
    if (doc.doc_type === 'XFormInstance' && (doc.domain === 'gsid')) {
        var form = doc.form;

        if (form["@name"] !== 'Malaria Test' && form["@name"] !== 'HIV Test') {
            return;
        }
 
        var data = {
			"age" : parseInt(form.age, 10),
			"diagnosis" : form.diagnosis
		};

        emit_array([
			doc.domain,
			form["@name"],
			form.test_version,
			form.province,
			form.district,
			form.clinic,
			form.sex], [doc.received_on], data);
    }
}
