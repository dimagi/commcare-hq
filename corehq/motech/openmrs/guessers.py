from collections import defaultdict


PATIENT_GUESSERS = []


def register_patient_guesser(class_):
    PATIENT_GUESSERS.append(class_)
    return class_


class PatientGuesserBase(object):
    """
    A PatientGuesser is used to guess patient identity if ID matchers
    fail.
    """

    def guess_patients(self, requests, case, case_config):
        """
        Given a case, search OpenMRS for possible matches. Return the
        best guesses. If just one guess is returned, it will be chosen.

        NOTE:: False positives can result in overwriting one patient
               with the data of another. It is definitely better to
               return no results than to return an invalid result.
               Guesses should be logged.

        """
        raise NotImplementedError
