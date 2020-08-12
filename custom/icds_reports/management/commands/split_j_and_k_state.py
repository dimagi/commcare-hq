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
        self._update_block_files()

    def _update_state_file(self):
        # loading state topojson object
        state_topojson_file = get_state_v3_topojson_file()
        state_topojson = state_topojson_file.topojson

        # remove J&K from list of geometries
        geometries = state_topojson['objects']['ind']['geometries']
        new_geometries = [g for g in geometries if g['id'] != J_AND_K]
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

        # assumes these district files are also in the input directory.
        # to create these files:
        # 1. get the source data from https://app.asana.com/0/1112385193248823/1157605674172491
        # 2. upload the .shp and .dbf files to https://mapshaper.org/
        # 3. download the output as topojson
        j_k_file_and_layer_name = 'Jammu_and_Kashmir_District_Boundary'
        j_k_file = os.path.join(self.input_dir, f'{j_k_file_and_layer_name}.json')
        ladakh_file_and_layer_name = 'Leh(Ladakh)_District_Boundary'
        ladakh_file = os.path.join(self.input_dir, f'{ladakh_file_and_layer_name}.json')

        new_district_filename = os.path.join(self.input_dir, 'districts_v4.topojson')
        # merge the files with mapshaper
        mapshaper_command = f"""mapshaper \
          -i {district_file.path} {j_k_file} '{ladakh_file}' snap combine-files \
          -o {new_district_filename}
        """
        subprocess.call(mapshaper_command, shell=True)

        # now need to do postprocessing to match what the dashboard expects
        with open(new_district_filename, 'r') as f:
            new_districts = json.loads(f.read())

        # pop out the two new states so we can work with them
        j_k_obj = new_districts['objects'].pop(j_k_file_and_layer_name)
        ladakh_obj = new_districts['objects'].pop(ladakh_file_and_layer_name)

        # copy custom properties from old data to new for all other states
        copy_custom_metadata(district_topojson, new_districts)

        # set id and name properties and clear everything else out that was in the import file
        for state_obj in [j_k_obj, ladakh_obj]:
            for geometry in state_obj['geometries']:
                imported_properties = geometry.pop('properties')
                geometry['properties'] = {
                    'name': imported_properties['DIST_NAME']
                }
                geometry['id'] = imported_properties['DIST_NAME']

        # add the states back to the root geometry with the new correct keys
        new_districts['objects'][J_AND_K] = j_k_obj
        new_districts['objects'][LADAKH] = ladakh_obj

        # finally, save the output again
        with open(new_district_filename, 'w+') as new_district_file:
            new_district_file.write(json.dumps(new_districts))

        print(f'new district topojson file written to {new_district_filename}')

    def _update_block_files(self):
        block_directory = os.path.join(self.input_dir, 'blocks')

        # like other parts of this command, assumes these files are also in the input directory.
        # to create these files:
        # 1. get the source data from https://app.asana.com/0/1160310200927866/1162209880990930
        # 2. upload the .shp and .dbf files to https://mapshaper.org/
        # 3. download the output as topojson
        j_k_file_and_layer_name = 'Jammu_&_Kashmir_Sub_District'
        j_k_file = os.path.join(self.input_dir, f'{j_k_file_and_layer_name}.json')
        ladakh_file_and_layer_name = 'Ladakh_Sub_District'
        ladakh_file = os.path.join(self.input_dir, f'{ladakh_file_and_layer_name}.json')

        # now need to do postprocessing to match what the dashboard expects
        jk_output_file = os.path.join(block_directory, 'jk_blocks_v4.topojson')
        ladakh_output_file = os.path.join(block_directory, 'ladakh_blocks_v4.topojson')
        output_files = {
            j_k_file: jk_output_file,
            ladakh_file: ladakh_output_file
        }
        for source_file in [j_k_file, ladakh_file]:
            # 1. wipe base layer name
            with open(source_file, 'r') as f:
                tmp_topojson = json.loads(f.read())
            assert len(tmp_topojson['objects']) == 1
            # move the current layer to an empty layer key
            tmp_topojson['objects'][''] = tmp_topojson['objects'].pop(list(tmp_topojson['objects'].keys())[0])
            # save to a temporary file
            tmp_filename = f'{source_file}.tmp'
            with open(tmp_filename, 'w+') as f:
                f.write(json.dumps(tmp_topojson))

            # 2. split base layer into districts
            split_layer_command = f'mapshaper "{tmp_filename}" -split DIST -o "{output_files[source_file]}" format=topojson'
            subprocess.call(split_layer_command, shell=True)

        # 3. Postprocess metadata on both files
        for output_file in [jk_output_file, ladakh_output_file]:
            with open(output_file, 'r') as f:
                new_blocks = json.loads(f.read())

            for district_name, district_geo in new_blocks['objects'].items():
                for block_obj in district_geo['geometries']:
                    imported_properties = block_obj.pop('properties')
                    block_obj['properties'] = {
                        'name': imported_properties['SUB_DIST_N']
                    }
                    block_obj['id'] = imported_properties['SUB_DIST_N']

            # finally rewrite the file one last time
            with open(output_file, 'w+') as new_block_file:
                new_block_file.write(json.dumps(new_blocks))

        print(f'new district topojson files written to {jk_output_file} and {ladakh_output_file}')
