# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import uuid
from collections import OrderedDict
from copy import copy
from xml.etree import cElementTree as ElementTree

from django.db import models, transaction
from django.utils.functional import cached_property

import six
from six import StringIO

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2, V2_NAMESPACE
from casexml.apps.phone.xml import get_case_xml

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.blobs import CODES, get_blob_db
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors


class CaseTemplate(models.Model):
    template_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.CharField(max_length=256, null=False, blank=False, db_index=True)
    name = models.CharField(max_length=256, null=False)
    comment = models.TextField(null=True)
    created_by = models.CharField(max_length=256, blank=True)
    created_on = models.DateTimeField(auto_now_add=True)

    def __repr__(self):
        return (
            "CaseTemplate("
            "template_id='{self.template_id}', "
            "domain='{self.domain}', "
            "name='{self.name}', "
            "comment='{self.comment}', "
            "created_by='{self.created_by}', "
            "created_on='{self.created_on}'"
            ")"
        ).format(self=self)

    @classmethod
    def create(cls, domain, root_case_id, name, user_id, comment=None):
        template = cls.objects.create(domain=domain, name=name, created_by=user_id, comment=comment)
        template.save_template_xml(cls._generate_case_xml(domain, root_case_id))
        return template

    @staticmethod
    def _generate_case_xml(domain, root_case_id):
        """Returns a blob of XML containing all the cases in the case hierarchy starting with `root_case_id`
        """
        root_case = CaseAccessors(domain).get_case(root_case_id)
        case_xml_blocks = (
            get_case_xml(case, ('create', 'update'), V2) for case in get_case_hierarchy(root_case)
        )
        return "<template-cases>{}</template-cases>".format("".join(case_xml_blocks))

    @property
    def _blob_key(self):
        return "case-template-{}-{}".format(self.domain, self.template_id)

    def save_template_xml(self, case_xml):
        """saves the case_xml to the blobdb
        """
        blob_meta_args = {
            "name": "{}.xml".format(self._blob_key),
            "parent_id": self.template_id,
            "domain": self.domain,
            "type_code": CODES.case_template,
            "key": self._blob_key,
        }
        return get_blob_db().put(StringIO(case_xml), **blob_meta_args)

    @cached_property
    def prototype_cases(self):
        """Dict of cases, keyed by case ID, contained in the template
        """
        case_blocks = (
            CaseBlock.from_xml(node)
            for node in self._get_template_xml().findall("{%s}case" % V2_NAMESPACE)
        )
        return OrderedDict((case.case_id, case) for case in case_blocks)

    def num_cases(self):
        return len(self.prototype_cases)

    def _get_template_xml(self):
        """get case xml from the blobdb
        """
        with get_blob_db().get(self._blob_key) as file_obj:
            template_xml = ElementTree.fromstring(file_obj.read())
        return template_xml

    def create_instance(self, suffix=None):
        """Creates cases based on the prototype stored in this template. Returns the
        case_id of the root in the tree

        """
        cases = []
        root_id = list(self.prototype_cases.keys())[0]
        if suffix is None:
            suffix = (self.instance_cases.count() // self.num_cases()) + 1
        with transaction.atomic():
            for case_id, case in six.iteritems(self.prototype_cases):
                new_case_id = six.text_type(uuid.uuid4())
                new_case = copy(case)
                new_case.create = True
                new_case.case_id = new_case_id
                new_case.case_name = "{}-{}".format(case.case_name, suffix)
                new_case.update['cc_template_id'] = six.text_type(self.template_id)
                new_case.update['cc_template_ancestor_id'] = root_id
                cases.append(new_case.as_string().decode('utf-8'))

                instance = CaseTemplateInstanceCase(case_id=new_case_id, ancestor_id=root_id, template=self)
                instance.save()

            submit_case_blocks(cases, self.domain, device_id=__name__ + '.create_template_instance')
        return root_id

    def get_instance_cases_for_root(self, root_id):
        return [instance_case.get_case() for instance_case in self.instance_cases.filter(ancestor_id=root_id)]

    def delete(self, *args, **kwargs):
        case_accessor = CaseAccessors(self.domain)

        case_ids = list(self.instance_cases.all().values_list('case_id', flat=True))
        form_ids = set()
        for case_id in case_ids:
            form_ids.update(case_accessor.get_case_xform_ids(case_id))

        with transaction.atomic():
            FormAccessors(self.domain).soft_delete_forms(list(form_ids))
            case_accessor.soft_delete_cases(case_ids)
            super(CaseTemplate, self).delete(*args, **kwargs)


class CaseTemplateInstanceCase(models.Model):
    template = models.ForeignKey(CaseTemplate, on_delete=models.CASCADE, related_name='instance_cases')
    case_id = models.CharField(max_length=255, unique=True, db_index=True)
    ancestor_id = models.CharField(max_length=255, db_index=True)

    def __repr__(self):
        return (
            "CaseTemplateInstanceCase("
            "case_id='{self.case_id}', "
            "ancestor_id='{self.ancestor_id}', "
            "template_id='{self.template_id}'"
            ")"
        ).format(self=self)

    def get_case(self):
        return CaseAccessors(self.template.domain).get_case(self.case_id)


def get_case_hierarchy(case):
    new_subcases = list(case.get_subcases())
    all_subcases = []
    while new_subcases:
        all_subcases.extend(new_subcases)
        new_subcases = [
            subcase
            for new_case in new_subcases
            for subcase in list(new_case.get_subcases())
            if list(new_case.get_subcases())
        ]
    return [case] + list(all_subcases)
