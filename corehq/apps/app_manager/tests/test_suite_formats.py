import hashlib

import commcare_translations

from django.test import SimpleTestCase

from corehq.apps.app_manager.models import (
    Application,
    DetailColumn,
    MappingItem,
    Module,
)
from corehq.apps.app_manager.tests.util import TestXmlMixin, patch_get_xform_resource_overrides


@patch_get_xform_resource_overrides()
class SuiteFormatsTest(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'suite')

    def _test_media_format(self, detail_format, template_form):
        app = Application.wrap(self.get_json('app_audio_format'))
        details = app.get_module(0).case_details
        details.short.get_column(0).format = detail_format
        details.long.get_column(0).format = detail_format

        expected = """
        <partial>
          <template form="{0}">
            <text>
              <xpath function="picproperty"/>
            </text>
          </template>
          <template form="{0}">
            <text>
              <xpath function="picproperty"/>
            </text>
          </template>
        </partial>
        """.format(template_form)
        self.assertXmlPartialEqual(expected, app.create_suite(), "./detail/field/template")

    def test_audio_format(self, *args):
        self._test_media_format('audio', 'audio')

    def test_image_format(self, *args):
        self._test_media_format('picture', 'image')

    def test_case_detail_conditional_enum(self, *args):
        app = Application.new_app('domain', 'Untitled Application')

        module = app.add_module(Module.new_module('Unititled Module', None))
        module.case_type = 'patient'

        module.case_details.short.columns = [
            DetailColumn(
                header={'en': 'Gender'},
                model='case',
                field='gender',
                format='conditional-enum',
                enum=[
                    MappingItem(key="gender = 'male' and age <= 21", value={'en': 'Boy'}),
                    MappingItem(key="gender = 'female' and age <= 21", value={'en': 'Girl'}),
                    MappingItem(key="gender = 'male' and age > 21", value={'en': 'Man'}),
                    MappingItem(key="gender = 'female' and age > 21", value={'en': 'Woman'}),
                ],
            ),
        ]

        key1_varname = hashlib.md5("gender = 'male' and age <= 21".encode('utf-8')).hexdigest()[:8]
        key2_varname = hashlib.md5("gender = 'female' and age <= 21".encode('utf-8')).hexdigest()[:8]
        key3_varname = hashlib.md5("gender = 'male' and age > 21".encode('utf-8')).hexdigest()[:8]
        key4_varname = hashlib.md5("gender = 'female' and age > 21".encode('utf-8')).hexdigest()[:8]

        icon_mapping_spec = """
        <partial>
          <template>
            <text>
              <xpath function="if(gender = 'male' and age &lt;= 21, $h{key1_varname}, if(gender = 'female' and age &lt;= 21, $h{key2_varname}, if(gender = 'male' and age &gt; 21, $h{key3_varname}, if(gender = 'female' and age &gt; 21, $h{key4_varname}, ''))))">
                <variable name="h{key4_varname}">
                  <locale id="m0.case_short.case_gender_1.enum.h{key4_varname}"/>
                </variable>
                <variable name="h{key2_varname}">
                  <locale id="m0.case_short.case_gender_1.enum.h{key2_varname}"/>
                </variable>
                <variable name="h{key3_varname}">
                  <locale id="m0.case_short.case_gender_1.enum.h{key3_varname}"/>
                </variable>
                <variable name="h{key1_varname}">
                  <locale id="m0.case_short.case_gender_1.enum.h{key1_varname}"/>
                </variable>
              </xpath>
            </text>
          </template>
        </partial>
        """.format(  # noqa: #501
            key1_varname=key1_varname,
            key2_varname=key2_varname,
            key3_varname=key3_varname,
            key4_varname=key4_varname,
        )
        # check correct suite is generated
        self.assertXmlPartialEqual(
            icon_mapping_spec,
            app.create_suite(),
            './detail[@id="m0_case_short"]/field/template'
        )
        # check app strings mapped correctly
        app_strings = commcare_translations.loads(app.create_app_strings('en'))
        self.assertEqual(
            app_strings['m0.case_short.case_gender_1.enum.h{key1_varname}'.format(key1_varname=key1_varname, )],
            'Boy'
        )
        self.assertEqual(
            app_strings['m0.case_short.case_gender_1.enum.h{key2_varname}'.format(key2_varname=key2_varname, )],
            'Girl'
        )
        self.assertEqual(
            app_strings['m0.case_short.case_gender_1.enum.h{key3_varname}'.format(key3_varname=key3_varname, )],
            'Man'
        )
        self.assertEqual(
            app_strings['m0.case_short.case_gender_1.enum.h{key4_varname}'.format(key4_varname=key4_varname, )],
            'Woman'
        )

    def test_case_detail_calculated_conditional_enum(self, *args):
        app = Application.new_app('domain', 'Untitled Application')

        module = app.add_module(Module.new_module('Unititled Module', None))
        module.case_type = 'patient'

        module.case_details.short.columns = [
            DetailColumn(
                header={'en': 'Gender'},
                model='case',
                field="if(gender = 'male', 'boy', 'girl')",
                format='enum',
                enum=[
                    MappingItem(key="boy", value={'en': 'Boy'}),
                    MappingItem(key="girl", value={'en': 'Girl'}),
                ],
            ),
        ]

        icon_mapping_spec = """
        <partial>
          <template>
            <text>
              <xpath function="replace(join(' ', if(selected(if(gender = 'male', 'boy', 'girl'), 'boy'), $kboy, ''), if(selected(if(gender = 'male', 'boy', 'girl'), 'girl'), $kgirl, '')), '\\s+', ' ')">
                <variable name="kboy">
                  <locale id="m0.case_short.case_if(gender  'male', 'boy', 'girl')_1.enum.kboy"/>
                </variable>
                <variable name="kgirl">
                  <locale id="m0.case_short.case_if(gender  'male', 'boy', 'girl')_1.enum.kgirl"/>
                </variable>
              </xpath>
            </text>
          </template>
        </partial>
        """  # noqa: #501
        # check correct suite is generated
        self.assertXmlPartialEqual(
            icon_mapping_spec,
            app.create_suite(),
            './detail[@id="m0_case_short"]/field/template'
        )
        # check app strings mapped correctly
        app_strings = commcare_translations.loads(app.create_app_strings('en'))
        self.assertEqual(
            app_strings["m0.case_short.case_if(gender  'male', 'boy', 'girl')_1.enum.kboy"],
            'Boy'
        )
        self.assertEqual(
            app_strings["m0.case_short.case_if(gender  'male', 'boy', 'girl')_1.enum.kgirl"],
            'Girl'
        )

    def test_case_detail_icon_mapping(self, *args):
        app = Application.new_app('domain', 'Untitled Application')

        module = app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = 'patient'

        module.case_details.short.columns = [
            DetailColumn(
                header={'en': 'Age range'},
                model='case',
                field='age',
                format='enum-image',
                enum=[
                    MappingItem(key='10', value={'en': 'jr://icons/10-year-old.png'}),
                    MappingItem(key='age > 50', value={'en': 'jr://icons/old-icon.png'}),
                    MappingItem(key='15%', value={'en': 'jr://icons/percent-icon.png'}),
                ],
            ),
        ]

        key1_varname = '10'
        key2_varname = hashlib.md5('age > 50'.encode('utf-8')).hexdigest()[:8]
        key3_varname = hashlib.md5('15%'.encode('utf-8')).hexdigest()[:8]

        icon_mapping_spec = """
            <partial>
              <template form="image" width="13%">
                <text>
                  <xpath function="if(age = '10', $k{key1_varname}, if(age > 50, $h{key2_varname}, if(age = '15%', $h{key3_varname}, '')))">
                    <variable name="h{key2_varname}">
                      <locale id="m0.case_short.case_age_1.enum.h{key2_varname}"/>
                    </variable>
                    <variable name="h{key3_varname}">
                      <locale id="m0.case_short.case_age_1.enum.h{key3_varname}"/>
                    </variable>
                    <variable name="k{key1_varname}">
                      <locale id="m0.case_short.case_age_1.enum.k{key1_varname}"/>
                    </variable>
                  </xpath>
                </text>
              </template>
            </partial>
        """.format(  # noqa: #501
            key1_varname=key1_varname,
            key2_varname=key2_varname,
            key3_varname=key3_varname,
        )
        # check correct suite is generated
        self.assertXmlPartialEqual(
            icon_mapping_spec,
            app.create_suite(),
            './detail/field/template[@form="image"]'
        )
        # check icons map correctly
        app_strings = commcare_translations.loads(app.create_app_strings('en'))
        self.assertEqual(
            app_strings['m0.case_short.case_age_1.enum.h{key3_varname}'.format(key3_varname=key3_varname,)],
            'jr://icons/percent-icon.png'
        )
        self.assertEqual(
            app_strings['m0.case_short.case_age_1.enum.h{key2_varname}'.format(key2_varname=key2_varname,)],
            'jr://icons/old-icon.png'
        )
        self.assertEqual(
            app_strings['m0.case_short.case_age_1.enum.k{key1_varname}'.format(key1_varname=key1_varname,)],
            'jr://icons/10-year-old.png'
        )

    def test_case_detail_address_popup(self, *args):
        app = Application.new_app('domain', 'Untitled Application')

        module = app.add_module(Module.new_module('Unititled Module', None))
        module.case_type = 'patient'

        module.case_details.short.columns = [
            DetailColumn(
                header={'en': 'Address'},
                model='case',
                field="address",
                format='address',
            ),
            DetailColumn(
                header={'en': 'Address Popup'},
                model='case',
                field="address",
                format='address-popup',
            ),
        ]

        suite = app.create_suite()

        address_template = """
            <partial>
              <template form="address">
                <text>
                  <xpath function="address"/>
                </text>
              </template>
            </partial>
            """
        # check correct suite is generated
        self.assertXmlPartialEqual(
            address_template,
            suite,
            './detail[@id="m0_case_short"]/field[1]/template'
        )

        address_popup_template = """
            <partial>
              <template form="address-popup">
                <text>
                  <xpath function="address"/>
                </text>
              </template>
            </partial>
            """
        # check correct suite is generated
        self.assertXmlPartialEqual(
            address_popup_template,
            suite,
            './detail[@id="m0_case_short"]/field[2]/template'
        )
