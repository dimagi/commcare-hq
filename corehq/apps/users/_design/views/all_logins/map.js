function(doc){ 
    if (doc.django_type == "users.hquserprofile")
        emit(doc._id, null);
}

