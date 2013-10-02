function (doc) {
    if (doc.doc_type === 'CommCareCase' && (doc.domain === 'gsid')) {

        emit(
            [doc.domain,
            doc.disease,
            doc.test_version,
            doc.country,
            doc.province,
            doc.district,
            doc.clinic,
            doc.sex,
            doc.opened_on,
            doc.diagnosis,
            parseInt(doc.lot_number, 10),
            doc.gps,
            doc.gps_country,
            doc.gps_province,
            doc.gps_district],
            parseInt(doc.age, 10)
        );
    }
}