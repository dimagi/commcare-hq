from custom.enikshay.nikshay_datamigration.management.commands.base_cleanup_command import BaseCleanupCommand


class Command(BaseCleanupCommand):

    headers = [
        'Sno',
        'PregId',
        'scode',
        'dcode',
        'tcode',
        'pname',
        'pgender',
        'page',
        'poccupation',
        'paadharno',
        'paddress',
        'pmob',
        'plandline',
        'ptbyr',
        'pregdate',
        'cname',
        'caddress',
        'cmob',
        'clandline',
        'cvisitedby',
        'cvisitedDate',
        'dcpulmunory',
        'dcexpulmunory',
        'dcpulmunorydet',
        'dotname',
        'dotdesignation',
        'dotmob',
        'dotlandline',
        'dotpType',
        'dotcenter',
        'dotphi',
        'dotmoname',
        'dotmosign',
        'dotmosdone',
        'atbtreatment',
        'atbduration',
        'atbsource',
        'atbregimen',
        'atbyr',
        'Ptype',
        'pcategory',
        'regBy',
        'regDate',
        'IsRntcp',
        'dotprovider_Id',
        'InitiationDate',
        'pregdate1',
        'cvisitedDate1',
        'InitiationDate1',
        'dotmosign1',
        'demoDate',
        'IP_From',
        'P_barcode',
        'Local_ID',
        'Source',
    ]

    @staticmethod
    def _skip_new_columns(row):
        PregId_INDEX = 1
        pregdate_INDEX = 14
        cvisitedDate_INDEX = 20
        dotmosign_INDEX = 32
        InitiationDate_INDEX = 45
        return (
            row[PregId_INDEX:pregdate_INDEX] +
            row[pregdate_INDEX + 1:cvisitedDate_INDEX] +
            row[cvisitedDate_INDEX + 1:dotmosign_INDEX] +
            row[dotmosign_INDEX + 1:InitiationDate_INDEX] +
            row[InitiationDate_INDEX + 1: -5]
        )

    @staticmethod
    def clean_rows(rows, exclude_ids):
        new_rows = [Command._skip_new_columns(Command.headers)]

        cur_row = ['']

        skipped = 0

        for i, row in enumerate(rows):
            if row:
                cur_row[-1] = cur_row[-1] + row[0]  # concatenate first element in row with last element in cur_row
                cur_row.extend(row[1:])  # append remaining elements in row to cur_row

                while len(cur_row) > len(Command.headers):
                    pmob_INDEX = 11
                    plandline_INDEX = 12
                    ptbyr_INDEX = 13
                    pregdate_INDEX = 14
                    cmob_INDEX = 17
                    dotmob_INDEX = 26
                    atbyr_INDEX = 38
                    Ptype_INDEX = 39
                    if cur_row[pmob_INDEX] != '' and not cur_row[pmob_INDEX].isdigit():
                        cur_row = cur_row[:pmob_INDEX - 1] + [cur_row[pmob_INDEX - 1] + ',' + cur_row[pmob_INDEX]] + cur_row[pmob_INDEX + 1:]
                    elif cur_row[plandline_INDEX] != '' and not cur_row[plandline_INDEX].isdigit():
                        cur_row = cur_row[:pmob_INDEX - 1] + [cur_row[pmob_INDEX - 1] + ',' + cur_row[pmob_INDEX]] + cur_row[pmob_INDEX + 1:]
                    elif cur_row[ptbyr_INDEX] == '' or cur_row[ptbyr_INDEX].count('/') not in [1, 2]:
                        cur_row = cur_row[:pmob_INDEX - 1] + [cur_row[pmob_INDEX - 1] + ',' + cur_row[pmob_INDEX]] + cur_row[pmob_INDEX + 1:]
                    elif cur_row[pregdate_INDEX] == '' or cur_row[pregdate_INDEX].count('/') not in [1, 2]:
                        cur_row = cur_row[:pmob_INDEX - 1] + [cur_row[pmob_INDEX - 1] + ',' + cur_row[pmob_INDEX]] + cur_row[pmob_INDEX + 1:]
                    elif cur_row[cmob_INDEX] != '' and not cur_row[cmob_INDEX].isdigit():
                        cur_row = cur_row[:cmob_INDEX - 1] + [cur_row[cmob_INDEX - 1] + ',' + cur_row[cmob_INDEX]] + cur_row[cmob_INDEX + 1:]
                    elif cur_row[cmob_INDEX + 3].count('/') != 2:
                        cur_row = cur_row[:cmob_INDEX - 1] + [cur_row[cmob_INDEX - 1] + ',' + cur_row[cmob_INDEX]] + cur_row[cmob_INDEX + 1:]
                    elif cur_row[dotmob_INDEX] != '' and not cur_row[dotmob_INDEX].isdigit():
                        cur_row = cur_row[:dotmob_INDEX - 3] + [cur_row[dotmob_INDEX - 3] + ',' + cur_row[dotmob_INDEX - 2]] + cur_row[dotmob_INDEX - 1:]
                    elif cur_row[atbyr_INDEX] and cur_row[atbyr_INDEX].strip() != '' and not cur_row[atbyr_INDEX].strip().isdigit():
                        cur_row = cur_row[:atbyr_INDEX - 1] + [cur_row[atbyr_INDEX - 1] + ',' + cur_row[atbyr_INDEX]] + cur_row[atbyr_INDEX + 1:]
                    elif cur_row[Ptype_INDEX] not in range(1, 8):
                        cur_row = cur_row[:atbyr_INDEX - 1] + [cur_row[atbyr_INDEX - 1] + ',' + cur_row[atbyr_INDEX]] + cur_row[atbyr_INDEX + 1:]
                    else:
                        if skipped == 0:
                            print i + 1
                            print cur_row
                            print len(cur_row)
                            print len(Command.headers)
                            print cur_row[pmob_INDEX]
                            print cur_row[cmob_INDEX]
                        skipped += 1
                        cur_row = ['']
                if len(cur_row) == len(Command.headers):
                    cur_row[1] = cur_row[1].strip()
                    new_rows.append(Command._skip_new_columns(cur_row))
                    cur_row = ['']

        print 'skipped = %d' % skipped

        return new_rows
