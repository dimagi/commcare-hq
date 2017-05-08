import json
import jsonobject
from corehq.apps.motech.openmrs.concepts.models import OpenmrsConcept
from corehq.apps.motech.openmrs.restclient.listapi import OpenmrsListApi


def sync_concepts_from_openmrs(account):
    requests = account.get_requests_object()
    OpenmrsConcept.objects.filter(account=account).delete()
    api = OpenmrsListApi(requests, 'concept')
    answers_relationships = []
    for concept in api.get_all():
        concept = openmrs_concept_json_from_api_json(concept)
        concept, answer_uuids = openmrs_concept_from_concept_json(account, concept)
        if answer_uuids:
            answers_relationships.append((concept, answer_uuids))
        concept.save()

    for concept, answer_uuids in answers_relationships:
        answer_concepts = OpenmrsConcept.objects.filter(account=account, uuid__in=answer_uuids).all()
        assert set(answer_concept.uuid for answer_concept in answer_concepts) == set(answer_uuids)
        concept.answers = answer_concepts
        concept.save()


class OpenmrsConceptJSON(jsonobject.JsonObject):
    """
    Intermediate model used for validation
    """
    uuid = jsonobject.StringProperty()
    display = jsonobject.StringProperty()
    concept_class = jsonobject.StringProperty()
    retired = jsonobject.BooleanProperty()
    datatype = jsonobject.StringProperty()
    answers = jsonobject.ListProperty(unicode)
    descriptions = jsonobject.ListProperty(unicode)
    names = jsonobject.ListProperty(lambda: OpenmrsConceptName)


class OpenmrsConceptJSONWithAnswers(OpenmrsConceptJSON):
    answers = jsonobject.ListProperty(OpenmrsConceptJSON)


class OpenmrsConceptName(jsonobject.JsonObject):
    display = jsonobject.StringProperty()
    locale = jsonobject.StringProperty()


def openmrs_concept_json_from_api_json(api_json):
    concept_json = OpenmrsConceptJSON(
        uuid=api_json['uuid'],
        display=api_json['display'],
        concept_class=api_json['conceptClass']['display'],
        retired=api_json['retired'],
        datatype=api_json['datatype']['display'],
        answers=[answer['uuid'] for answer in api_json['answers']
                 if '/drug/' not in ''.join(link['uri'] for link in answer['links'])],
        descriptions=[description['display']
                      for description in api_json['descriptions']],
        names=[OpenmrsConceptName(display=name['display'], locale=name['locale'])
               for name in api_json['names']],
    )

    return concept_json


def openmrs_concept_from_concept_json(account, concept_json):
    return (OpenmrsConcept(
        account=account,
        uuid=concept_json.uuid,
        display=concept_json.display,
        concept_class=concept_json.concept_class,
        retired=concept_json.retired,
        datatype=concept_json.datatype,
        descriptions=json.dumps(concept_json.descriptions),
        names=json.dumps([name.to_json() for name in concept_json.names]),
    ), concept_json.answers)


def openmrs_concept_json_with_answers_from_concept(concept):
    return OpenmrsConceptJSONWithAnswers(
        uuid=concept.uuid,
        display=concept.display,
        concept_class=concept.concept_class,
        retired=concept.retired,
        datatype=concept.datatype,
        answers=[openmrs_concept_json_from_concept(answer) for answer in concept.answers.all()],
        descriptions=json.loads(concept.descriptions),
        names=[OpenmrsConceptName(name) for name in json.loads(concept.names)],
    )


def openmrs_concept_json_from_concept(concept):
    return OpenmrsConceptJSON(
        uuid=concept.uuid,
        display=concept.display,
        concept_class=concept.concept_class,
        retired=concept.retired,
        datatype=concept.datatype,
        answers=[answer.uuid for answer in concept.answers.all()],
        descriptions=json.loads(concept.descriptions),
        names=[OpenmrsConceptName(name) for name in json.loads(concept.names)],
    )
