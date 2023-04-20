def update_script(case_ids_to_exclude=[]):
    from corehq.form_processor.models import CommCareCase
    from corehq.apps.locations.models import SQLLocation
    from casexml.apps.case.mock import CaseBlock
    from corehq.apps.hqcase.utils import submit_case_blocks
    import os

    def submit_cases(case_blocks):
        submit_case_blocks(
            [cb.as_text() for cb in case_blocks],
            domain=DOMAIN,
            device_id='system',
        )

    DOMAIN = 'develop'
    CHILD_CASE_TYPE = 'membre'
    BULK_SIZE = 50

    total_case_ids = CommCareCase.objects.get_case_ids_in_domain(domain=DOMAIN, type=CHILD_CASE_TYPE)
    case_ids = [case_id for case_id in total_case_ids if case_id not in case_ids_to_exclude]

    total_cases = len(case_ids)
    cases_checked = -1

    error_log_file_path = os.path.expanduser("~/chris_script_error.log")
    success_log_file_path = os.path.expanduser("~/chris_script_success.log")
    with open(success_log_file_path, "a") as success_logfile:
        with open(error_log_file_path, "a") as logfile:

            case_blocks = []
            for child_case in CommCareCase.objects.iter_cases(case_ids, domain=DOMAIN):
                # --- Statistics
                cases_checked += 1
                progress = round(cases_checked / total_cases, 3)
                print(f"{progress}% complete")
                # --------------

                # child_case_helper = CaseHelper(domain=DOMAIN, case=child_case)
                
                """
                    Step 2 - Make sure that the case properties of both the child and parent cases correspond to te
                    village's hierarchy. The owner_id of both cases is the village id
                """
                try:
                    parent_case = child_case.parent
                    village_id = parent_case.owner_id
                except Exception:
                    logfile.write(f"Skipped {child_case.case_id}. Reason: No parent case\n")
                    continue

                try:
                    village = SQLLocation.objects.filter(location_id=village_id, domain=DOMAIN).first()
                    formation_sanitaire = village.parent
                    arrondissement = formation_sanitaire.parent
                    commune = arrondissement.parent
                    zone_sanitaire = commune.parent
                    departement = zone_sanitaire.parent
                except Exception as e:
                    logfile.write(f"Skipped {child_case.case_id}. Reason: Location hierarchy issue. {e}\n")
                    continue

                correct_properties = {
                    "hh_village_name": village.name,
                    "hh_formation_sanitaire_name": formation_sanitaire.name,
                    "hh_arrondissement_name": arrondissement.name,
                    "hh_commune_name": commune.name,
                    "hh_zone_sanitaire_name": zone_sanitaire.name,
                    "hh_departement_name": departement.name
                }

                # parent_case_helper = CaseHelper(domain=DOMAIN, case=parent_case)
                # case_helpers = (parent_case_helper, child_case_helper)

                try:
                    for case in (parent_case, child_case):
                        is_dirty = False
                        updated_properties = {}
                        for property_name, correct_property_value in correct_properties.items():
                            curr_case_property_value = case.get_case_property(property_name)

                            if (not curr_case_property_value) or (curr_case_property_value != correct_property_value):
                                updated_properties[property_name] = correct_property_value
                                is_dirty = True
                        
                        # update_dict = {'properties': updated_properties}
                        is_child_case = case.case_id == child_case.case_id
                        owner_ids_differ = case.owner_id != parent_case.owner_id
                        if is_child_case and owner_ids_differ:
                            is_dirty = True
                            # update_dict['owner_id'] = parent_case.owner_id

                        if is_dirty:
                            case_block = CaseBlock(
                                create=False,
                                case_id=case.case_id,
                                owner_id=parent_case.owner_id, # True for both child and parent case
                                update=updated_properties,
                            )
                            case_blocks.append(case_block)
                        
                        if len(case_blocks) == BULK_SIZE:
                            submit_cases(case_blocks)
                            for case_block in case_blocks:
                                success_logfile.write(f"{case_block.case_id}, ")
                            # Clear case_blocks
                            case_blocks = []
                
                except Exception as e:
                    logfile.write(f"Skipped {child_case.case_id}. Reason: Cannot update case. {e}\n")

            # We need to submit any remaining case blocks in case BULK_SIZE have not been reached
            try:
                submit_cases(case_blocks)
                for case_block in case_blocks:
                    success_logfile.write(f"{case_block.case_id}, ")
                # Clear case_blocks
                case_blocks = []
            except Exception as e:
                    logfile.write(f"Skipped {child_case.case_id}. Reason: Cannot update case. {e}\n")