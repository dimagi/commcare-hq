from django.db import models

from corehq.util.test_utils import create_and_save_a_case


class PatientDetail(models.Model):
    PregId = models.CharField(max_length=255, primary_key=True)
    Stocode = models.CharField(max_length=255, null=True)
    Dtocode = models.CharField(max_length=255, null=True)
    Tbunitcode = models.IntegerField(null=True)
    pname = models.CharField(max_length=255, null=True)
    pgender = models.CharField(max_length=255, null=True)
    page = models.IntegerField(null=True)
    poccupation = models.IntegerField(null=True)
    paadharno = models.CharField(max_length=255, null=True) # big ints (scientific notation) and nulls
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

    def create_person_case(self):
        create_and_save_a_case(
            domain='enikshay-np',
            case_id=self.PregId.strip(),
            case_name=self.pname,
            case_properties={
                'name': self.pname,
            }
        )
