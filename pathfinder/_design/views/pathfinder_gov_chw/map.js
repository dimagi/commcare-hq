function(doc) {
  if (doc.doc_type == 'CommCareUser'){
  var u = doc.user_data;
  emit([doc.domain, u.ward], [u.login_id, u.region, u.district, u.full_name, u.chw_id, u.sex, u.training, u.trainingorg, u.trainingdays, u.user_type, u.supervisorname, u.supervisorfacility, u.supervisorid, u.orgsupervisor]);
}
}
