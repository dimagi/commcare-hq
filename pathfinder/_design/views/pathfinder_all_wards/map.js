function(doc) {
  if (doc.doc_type == 'CouchUser' && doc.commcare_accounts[0].domain == 'pathfinder'){
  var u = doc.commcare_accounts[0].user_data;
  emit([doc.commcare_accounts[0].domain, u.district, u.ward], null);
}
}