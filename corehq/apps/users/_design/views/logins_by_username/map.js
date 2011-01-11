function(doc) {
    if(doc.django_type == "users.hquserprofile") {
        emit(doc.django_user.username, doc._id)
    }
}