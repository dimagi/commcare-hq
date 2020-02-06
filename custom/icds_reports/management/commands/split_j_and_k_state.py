import copy
import json
import subprocess

import os
from django.core.management import BaseCommand

from custom.icds_reports.utils.topojson_util.topojson_util import (
    get_topojson_directory,
    copy_custom_metadata,
    get_state_v3_topojson_file,
    get_district_v3_topojson_file
)


J_AND_K = 'J&K'
LADAKH = 'Ladakh'


class Command(BaseCommand):
    help = (
        "Split Jammu and Kashmir and Ladakh into separate states, as per "
        "https://en.wikipedia.org/wiki/Jammu_and_Kashmir_Reorganisation_Act,_2019."
    )
    # this command was used for https://app.asana.com/0/1112385193248823/1157605674172491

    def handle(self, *args, **kwargs):
        self.input_dir = get_topojson_directory()
        self._update_state_file()
        self._update_district_file()

    def _update_state_file(self):
        # loading state topojson object
        state_topojson_file = get_state_v3_topojson_file()
        state_topojson = state_topojson_file.topojson

        # remove J&K from list of geometries
        geometries = state_topojson['objects']['ind']['geometries']
        new_geometries = [g for g in geometries if g['id'] != 'J&K']
        state_topojson['objects']['ind']['geometries'] = new_geometries

        # save a new file
        tmp_state_filename = os.path.join(self.input_dir, 'states_v4_tmp.topojson')
        with open(tmp_state_filename, 'w+') as new_map_file:
            new_map_file.write(json.dumps(state_topojson))

        # assumes these files are in the input directory.
        # get them from  https://app.asana.com/0/1112385193248823/1157605674172491
        j_k_file = os.path.join(self.input_dir, 'Jammu_and_Kashmir_State.shp')
        ladakh_file = os.path.join(self.input_dir, 'Ladakh_State.shp')

        new_state_filename = os.path.join(self.input_dir, 'states_v4.topojson')

        # now we merge in the new shape files using mapshaper : https://www.npmjs.com/package/mapshaper
        # see https://gis.stackexchange.com/a/221075/126250 for details
        mapshaper_command = f"""mapshaper \
          -i {tmp_state_filename} {j_k_file} {ladakh_file} snap combine-files \
          -rename-layers states,jk,ladakh \
          -merge-layers target=states,jk,ladakh name=ind force \
          -o {new_state_filename}
        """
        subprocess.call(mapshaper_command, shell=True)

        # now open the newly created file
        with open(new_state_filename, 'r') as f:
            new_states = json.loads(f.read())

        # ...and add metadata back
        copy_custom_metadata(state_topojson, new_states)

        # we also have to manually populate metadata for the two states
        jk = new_states['objects']['ind']['geometries'][-2]
        jk['id'] = J_AND_K
        jk['properties'] = {"State": "01", "name": J_AND_K}
        ladakh = new_states['objects']['ind']['geometries'][-1]
        ladakh['id'] = LADAKH
        ladakh['properties'] = {"State": "37", "name": LADAKH}

        # then rewrite the file again
        with open(new_state_filename, 'w+') as new_map_file:
            new_map_file.write(json.dumps(new_states))

        print(f'new state file written to {new_state_filename}')

    def _update_district_file(self):
        district_file = get_district_v3_topojson_file()
        district_topojson = district_file.topojson
        j_k = district_topojson['objects'][J_AND_K]
        all_geometries = j_k['geometries']
        # make a base copy for ladakh with same properties
        ladakh = copy.deepcopy(j_k)
        # wipe the geometries of both
        j_k['geometries'] = []
        ladakh['geometries'] = []
        for geometry in all_geometries:
            # only these two districts are in Ladakh state
            if geometry['id'] in ('Leh(Ladakh)', 'Kargil'):
                ladakh['geometries'].append(geometry)
            else:
                j_k['geometries'].append(geometry)

        # add ladakh to the district topojson list
        district_topojson['objects'][LADAKH] = ladakh

        # save a new file
        new_district_filename = os.path.join(self.input_dir, 'districts_v4.topojson')
        with open(new_district_filename, 'w+') as new_district_file:
            new_district_file.write(json.dumps(district_topojson))

        print(f'new district topojson file written to {new_district_filename}')
