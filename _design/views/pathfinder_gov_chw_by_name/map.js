function(doc) {
  if (doc.doc_type == 'CouchUser'){
  var u = doc.commcare_accounts[0].user_data;
  emit([doc.commcare_accounts[0].domain, u.full_name], []);
}
}