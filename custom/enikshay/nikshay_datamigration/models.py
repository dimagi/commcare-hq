from django.db import models


class PatientDetail(models.Model):
    PregId = models.CharField(max_length=255, primary_key=True) # need to remove trailing whitespace in Excel
    Stocode = models.CharField(max_length=255, null=True)
    Dtocode = models.CharField(max_length=255, null=True)
    Tbunitcode = models.IntegerField(null=True)
    pname = models.CharField(max_length=255, null=True)
    pgender = models.CharField(max_length=255)
    page = models.IntegerField(null=True)
    poccupation = models.IntegerField(null=True)
    paadharno = models.CharField(max_length=255, null=True) # big ints (scientific notation) and nulls. requires some formatting
    paddress = models.CharField(max_length=255, null=True)
    pmob = models.CharField(max_length=255, null=True)  # contains " ", big ints
    plandline = models.BigIntegerField(null=True)
    ptbyr = models.CharField(max_length=255, null=True)  # dates, but not clean
    pregdate1 = models.DateField()  # remove time in Excel (format as DD-MM-YYYY)
    cname = models.CharField(max_length=255, null=True)
    caddress = models.CharField(max_length=255, null=True)
    cmob = models.CharField(max_length=255, null=True)  # contains "  ", big ints
    clandline = models.BigIntegerField(null=True)
    cvisitedby = models.CharField(max_length=255, null=True)
    cvisitedDate1 = models.CharField(max_length=255, null=True)  # datetimes, look like they're all midnight
    dcpulmunory = models.CharField(
        max_length=255, choices=(
            ('y', 'y'),
            ('N', 'N'),
        )
    )  # y or N
    dcexpulmunory = models.CharField(max_length=255, null=True)
    dcpulmunorydet = models.CharField(max_length=255, null=True)
    dotname = models.CharField(max_length=255, null=True)
    dotdesignation = models.CharField(max_length=255, null=True)
    dotmob = models.CharField(max_length=255, null=True)
    dotlandline = models.CharField(max_length=255, null=True)
    dotpType = models.IntegerField()
    dotcenter = models.CharField(max_length=255, null=True)
    PHI = models.IntegerField()
    dotmoname = models.CharField(max_length=255, null=True)
    dotmosignDate = models.CharField(max_length=255, null=True)  # datetimes, look like they're all midnight. also have a bunch of 1/1/1990
    atbtreatment = models.CharField(max_length=255, choices=(
        ('Y', 'Y'),
        ('N', 'N'),
    ))  # Y or N
    atbduration = models.CharField(max_length=255, null=True)  # some int, some # months poorly formatted
    atbsource = models.CharField(max_length=255, null=True, choices=(
        ('G', 'G'),
        ('O', 'O'),
        ('P', 'P'),
    ))
    atbregimen = models.CharField(max_length=255, null=True)
    atbyr = models.IntegerField(null=True)
    Ptype = models.IntegerField()
    pcategory = models.IntegerField()
    InitiationDate1 = models.CharField(max_length=255, null=True)  # datetimes, look like they're all midnight

    @property
    def first_name(self):
        return self._list_of_names[0]

    @property
    def middle_name(self):
        return ' '.join(self._list_of_names[1:-1])

    @property
    def last_name(self):
        return self._list_of_names[-1]

    @property
    def _list_of_names(self):
        return self.pname.split(' ')

    @property
    def sex(self):
        return {
            'F': 'female',
            'M': 'male',
            'T': 'transgender'
        }[self.pgender]


class Outcome(models.Model):
    PatientId = models.ForeignKey(PatientDetail, primary_key=True)
    Outcome = models.CharField(max_length=255, null=True)
    OutcomeDate1 = models.CharField(max_length=255, null=True)
    MO = models.CharField(max_length=255, null=True)
    XrayEPTests = models.CharField(max_length=255, null=True)
    MORemark = models.CharField(max_length=255, null=True)
    HIVStatus = models.CharField(max_length=255, null=True)
    HIVTestDate = models.CharField(max_length=255, null=True)
    CPTDeliverDate = models.CharField(max_length=255, null=True)
    ARTCentreDate = models.CharField(max_length=255, null=True)
    InitiatedOnART = models.CharField(max_length=255, null=True)
    InitiatedDate = models.CharField(max_length=255, null=True)
