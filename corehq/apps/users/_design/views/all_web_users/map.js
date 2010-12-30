function(doc){ 
    if (doc.django_type == "users.hquserprofile" && doc.django_user.username != null)
        emit(doc._id, doc);
}
