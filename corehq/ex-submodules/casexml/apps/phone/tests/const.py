"""
Some constants used in tests.
"""


CREATE_SHORT = """
    <case>
        <case_id>asdf</case_id>
        <date_modified>2010-06-29T13:42:50.000000Z</date_modified>
        <create>
            <case_type_id>test_case_type</case_type_id>
            <user_id>foo</user_id>
            <case_name>test case name</case_name>
            <external_id>someexternal</external_id>
        </create>
    </case>"""

UPDATE_SHORT = """
    <case>
        <case_id>asdf</case_id>
        <date_modified>2010-06-30T13:42:50.000000Z</date_modified>
        <update>
            <case_type_id>test_case_type</case_type_id>
            <user_id>foo</user_id>
            <case_name>test case name</case_name>
            <external_id>someexternal</external_id>
            <somenewthing>update!</somenewthing>
        </update>
   </case>"""
