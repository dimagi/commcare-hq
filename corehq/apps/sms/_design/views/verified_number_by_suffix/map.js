function(doc) {
    if(doc.doc_type == "VerifiedNumber") {
        if(doc.phone_number != null) {
            number1 = doc.phone_number.substring(1);
            number2 = doc.phone_number.substring(2);
            number3 = doc.phone_number.substring(3);
            emit(number1, null);
            emit(number2, null);
            emit(number3, null);
        }
    }
}
