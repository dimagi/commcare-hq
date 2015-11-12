# CommCare case type of OpenClinica study subjects
CC_SUBJECT_CASE_TYPE = 'subject'

# Names of case properties used in report
CC_SUBJECT_KEY = 'screening_number'
CC_STUDY_SUBJECT_ID = 'subject_number'
CC_ENROLLMENT_DATE = 'assd1'
CC_SEX = 'sex'
CC_DOB = 'dob'

# Include audit logs in export document
AUDIT_LOGS = True

# Maps a single-event form XMLNS to its event index
SINGLE_EVENT_FORM_EVENT_INDEX = {
    # Adverse Events 1
    'http://openrosa.org/formdesigner/B3BFA5DE-7A52-47D3-B003-FF00F94B843A': 0,
    # Adverse Events 2
    'http://openrosa.org/formdesigner/2bfff48eb9e2b7c75d5e2489995657883191c202': 1,
    # Adverse Events 3
    'http://openrosa.org/formdesigner/e75af2d3c901f1274ede277a19b01044d85e5df4': 2,
    # Adverse Events 4
    'http://openrosa.org/formdesigner/f0cf36e379b07e196db3f16aa2db04120cb20664': 3,
    # Adverse Events 5
    'http://openrosa.org/formdesigner/a2efc7bb9fc344a3d6974556044b9b2dc9293ebb': 4,
    # Adverse Events 6
    'http://openrosa.org/formdesigner/77219b321c3e6d55065a42640cfcefaea5f3b914': 5,
    # Adverse Events 7
    'http://openrosa.org/formdesigner/da8020e4dcabbd5466f182d998a223584fbf1509': 6,
    # Adverse Events 8
    'http://openrosa.org/formdesigner/1d854aaa5841c5bde25c5d5c8126e215f8efe1a3': 7,
    # Adverse Events 9
    'http://openrosa.org/formdesigner/be6579acb3d6bcd8e14e6f80846e6bb2a0ef9bc0': 8,
    # Adverse Events 10
    'http://openrosa.org/formdesigner/321392ace83c49b29fb7f6ad9f1bd2da65c60ae0': 9,
    # Adverse Events 11
    'http://openrosa.org/formdesigner/599f84f68d11cb17c0729c68c1855435c82f5fb1': 10,
    # Adverse Events 12
    'http://openrosa.org/formdesigner/9f4ee2d1d73c7e101d24efa580cbbca9a9bcc58b': 11,
    # Adverse Events 13
    'http://openrosa.org/formdesigner/e1559787eac833eb44ff1f0d1aee251d4dfcd4ea': 12,
    # Adverse Events 14
    'http://openrosa.org/formdesigner/16664ed83d6dfea1b9e639da28a0fddc971ae5f0': 13,
    # Adverse Events 15
    'http://openrosa.org/formdesigner/56eb48b0c32eb325da372ddd30b0634a13791d2f': 14,

    # Concomitant Medication 1
    'http://openrosa.org/formdesigner/16BA2A00-EA87-4C24-9CE9-6128A38829D2': 0,
    # Concomitant Medication 2
    'http://openrosa.org/formdesigner/be560e0ee8d59f364a8fd56945b7ece5ad9a7fbf': 1,
    # Concomitant Medication 3
    'http://openrosa.org/formdesigner/147dc0672c49479f3abd9fd07f4f8cb59e2a0ea4': 2,
    # Concomitant Medication 4
    'http://openrosa.org/formdesigner/40da33a113ec7e4e52f3a84cbebffd1db67666ee': 3,
    # Concomitant Medication 5
    'http://openrosa.org/formdesigner/f6eaf38cd2c0edb94d073b43973cb57694970ef5': 4,
    # Concomitant Medication 6
    'http://openrosa.org/formdesigner/74b83c90231e9cb6afdf86f17e1f42c7d1a32b0': 5,
    # Concomitant Medication 7
    'http://openrosa.org/formdesigner/f712a52e97f48868f414593b9710cfd27bfb2dad': 6,
    # Concomitant Medication 8
    'http://openrosa.org/formdesigner/2a4a570694ccfa447873b05322ac4b5d35eb4dbf': 7,
    # Concomitant Medication 9
    'http://openrosa.org/formdesigner/1a41db6a629e22174f340f9d1afb2962cc2f39ac': 8,
    # Concomitant Medication 10
    'http://openrosa.org/formdesigner/56aa2609cea7277a4a9f1445ac0b19d3efdea712': 9,

    # Unscheduled Visit 1: Checklist
    'http://openrosa.org/formdesigner/efa101e1e4155958fd9816686f0478c9400b5f60': 0,
    # Unscheduled Visit 1: Medical History/Current Medical Condition
    'http://openrosa.org/formdesigner/37f49f3825a10950bfe04604d3f5d724ea044ad4': 0,
    # Unscheduled Visit 1: Physical Examination
    'http://openrosa.org/formdesigner/b30b10c4ebd58afc0c4325c8aeeca8a9f02e6a25': 0,
    # Unscheduled Visit 1: Haematology & Biochemistry/Renal Function
    'http://openrosa.org/formdesigner/18dba5e39ceb071e20be75eb2268a10ffd4fca6': 0,
    # Unscheduled Visit 1: Vital Signs
    'http://openrosa.org/formdesigner/c326601c4dd1a7d0beb7c9615a187b877eddd0e2': 0,

    # Unscheduled Visit 2: Checklist
    'http://openrosa.org/formdesigner/67794f250f5704aa3dbc1eb7eed919d9a8864a40': 1,
    # Unscheduled Visit 2: Medical History/Current Medical Condition
    'http://openrosa.org/formdesigner/1dc411d181ef0a8f123e39c8a60872f5a4a546dd': 1,
    # Unscheduled Visit 2: Physical Examination
    'http://openrosa.org/formdesigner/f88f6b51b716c59e6f94b7102a9dc07bcbabc652': 1,
    # Unscheduled Visit 2: Haematology & Biochemistry/Renal Function
    'http://openrosa.org/formdesigner/c88074df26124b037c7b0f2d3ebadf53020c0d3c': 1,
    # Unscheduled Visit 2: Vital Signs
    'http://openrosa.org/formdesigner/b16d46ef243477cace3ec982d90f35bab663383c': 1,

    # Unscheduled Visit 3: Checklist
    'http://openrosa.org/formdesigner/64ab8da8a4401b824a3c0bc643d16d0374654bec': 2,
    # Unscheduled Visit 3: Medical History/Current Medical Condition
    'http://openrosa.org/formdesigner/2e3675a0c9c692bf0992ecc080784b3bb0832e11': 2,
    # Unscheduled Visit 3: Physical Examination
    'http://openrosa.org/formdesigner/921239b96baa3ca81762d030b54c0a05af873142': 2,
    # Unscheduled Visit 3: Haematology & Biochemistry/Renal Function
    'http://openrosa.org/formdesigner/e455dc4beaebcc508aefef57f691af59078db71e': 2,
    # Unscheduled Visit 3: Vital Signs
    'http://openrosa.org/formdesigner/bfcc88f81fe74ac9c06a707981005477634aed8c': 2,
}

# Maps CommCare modules to OpenClinica events.
MODULE_EVENTS = {
    'Lab Tests': ('SE_VISIT1A', 'SE_VISIT1B', 'SE_VISIT2', 'SE_VISIT3', 'SE_ENDOFSTUDY', 'SE_UNSCHEDULEDVISIT'),
    'Register Patient': ('SE_VISIT1A', ),
    'Assign Screening Number': None,
    'Visit 1: Screening': ('SE_VISIT1A', 'SE_VISIT1B'),
    'Enrollment Call': (),
    'Enroll Patient Into Study': (),
    'Visit 2: Baseline Screening': ('SE_VISIT2', ),
    'Visit 3: Dosing': ('SE_VISIT3', ),
    'Discharge Patient from Ward': ('SE_ENDOFSTUDY', ),
    '30 Days Follow Up Call': (),
    'End of Study': ('SE_ENDOFSTUDY', ),
    'Adverse Events Log': ('SE_AEANDCONCOMITANTMEDICATIONS', ),
    'Concomitant Medication Log': ('SE_AEANDCONCOMITANTMEDICATIONS', ),
    'Unscheduled Visits Log': ('SE_UNSCHEDULEDVISIT', ),
    'Unscheduled Contact Log': ('SE_UNSCHEDULEDVISIT', ),

    'Demographic and History': ('SE_VISIT1A', ),
}

# The Lab Tests module spans many events, and its forms each map to one event.
FORM_EVENTS = {
    # Lab Tests > Screening 1: Enter Lab Test results
    "http://openrosa.org/formdesigner/7ce0af9273196c50fa1c7da4ce0ffe8efd95db89": ('SE_VISIT1A', 'SE_VISIT1B'),
    # Lab Tests > Screening 2: Enter Lab Test results
    "http://openrosa.org/formdesigner/bcc0e64bfca2ec49b23af088bd999ce6fa4519ca": ('SE_VISIT2', ),
    # Lab Tests > Record Post Dose PK Sample Processing Time
    "http://openrosa.org/formdesigner/E0ADA889-F6D7-45F9-A80F-D5558FEB12C3": ('SE_VISIT3', ),
    # Lab Tests > Patient Discharge: Enter Lab Test results
    "http://openrosa.org/formdesigner/B181B493-567F-4FF3-9C0A-684C306DCC84": ('SE_ENDOFSTUDY', ),
    # Lab Tests > Unscheduled Visit: Enter Lab Results
    "http://openrosa.org/formdesigner/11a29254a2df4a77a30608e97736c9f95aee7e2f": ('SE_UNSCHEDULEDVISIT', ),
    # Unscheduled Visits Log > Screening & Lab Request Form
    'http://openrosa.org/formdesigner/cdd2842cd1c8640fc2846f1b042dad06ac170d5': ('SE_UNSCHEDULEDVISIT', ),
}

# When MODULE_EVENTS is not narrow enough to determine a unique question-item match, map the CommCare form and
# question to an OpenClinica Item OID, or None if it's a CommCare-only question
FORM_QUESTION_ITEM = {
    # Lab Tests > Patient Discharge: Enter Lab Test results
    ('http://openrosa.org/formdesigner/B181B493-567F-4FF3-9C0A-684C306DCC84', 'dosh'): None,
    ('http://openrosa.org/formdesigner/B181B493-567F-4FF3-9C0A-684C306DCC84', 'dosb'): None,
    # Lab Tests > Unscheduled Visit: Enter Lab Results
    ('http://openrosa.org/formdesigner/11a29254a2df4a77a30608e97736c9f95aee7e2f', 'dosh'): None,
    ('http://openrosa.org/formdesigner/11a29254a2df4a77a30608e97736c9f95aee7e2f', 'dosb'): None,
    ('http://openrosa.org/formdesigner/11a29254a2df4a77a30608e97736c9f95aee7e2f', 'pg_pf'): None,
    ('http://openrosa.org/formdesigner/11a29254a2df4a77a30608e97736c9f95aee7e2f', 'dospg'): None,
    ('http://openrosa.org/formdesigner/11a29254a2df4a77a30608e97736c9f95aee7e2f', 'pgt'): None,
    # Unscheduled Visits Log > Screening & Lab Request Form
    ('http://openrosa.org/formdesigner/cdd2842cd1c8640fc2846f1b042dad06ac170d5', 'smlcd'): None,
    ('http://openrosa.org/formdesigner/cdd2842cd1c8640fc2846f1b042dad06ac170d5', 'psmk'): None,
    ('http://openrosa.org/formdesigner/cdd2842cd1c8640fc2846f1b042dad06ac170d5', 'palc'): None,
    ('http://openrosa.org/formdesigner/cdd2842cd1c8640fc2846f1b042dad06ac170d5', 'win'): None,
    ('http://openrosa.org/formdesigner/cdd2842cd1c8640fc2846f1b042dad06ac170d5', 'bru'): None,
    ('http://openrosa.org/formdesigner/cdd2842cd1c8640fc2846f1b042dad06ac170d5', 'sprt'): None,
}
