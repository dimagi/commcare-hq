PATIENT_FINDERS = []


def register_patient_finder(class_):
    PATIENT_FINDERS.append(class_)
    return class_


class PatientFinderBase(object):
    """
    PatientFinderBase is used to find a patient if ID matchers fail.
    """

    def find_patients(self, requests, case, case_config):
        """
        Given a case, search OpenMRS for possible matches. Return the
        best results. Subclasses must define "best". If just one result
        is returned, it will be chosen.

        NOTE:: False positives can result in overwriting one patient
               with the data of another. It is definitely better to
               return no results than to return an invalid result.
               Returned results should be logged.

        """
        raise NotImplementedError
