COWIN_APPOINTMENT_DETAIL_XML = """
<detail id="{detail_id}">
    <title>
      <text>
        <locale id="cchq.cowin.appointment"/>
      </text>
    </title>
    <field>
      <header>
        <text>
          <locale id="m{module_id}.cowin.appointment.name.header"/>
        </text>
      </header>
      <template>
        <text>
          <xpath function="name"/>
        </text>
      </template>
      <sort type="string" order="4" direction="ascending">
        <text>
          <xpath function="name"/>
        </text>
      </sort>
    </field>
    <field>
      <header>
        <text>
          <locale id="m{module_id}.cowin.appointment.available_capacity.header"/>
        </text>
      </header>
      <template>
        <text>
          <xpath function="available_capacity"/>
        </text>
      </template>
      <sort type="int" order="1" direction="descending">
        <text>
          <xpath function="available_capacity"/>
        </text>
      </sort>
    </field>
    <field>
      <header>
        <text>
          <locale id="m{module_id}.cowin.appointment.available_capacity_dose1.header"/>
        </text>
      </header>
      <template>
        <text>
          <xpath function="available_capacity_dose1"/>
        </text>
      </template>
      <sort type="int" order="2" direction="descending">
        <text>
          <xpath function="available_capacity_dose1"/>
        </text>
      </sort>
    </field>
    <field>
      <header>
        <text>
          <locale id="m{module_id}.cowin.appointment.available_capacity_dose2.header"/>
        </text>
      </header>
      <template>
        <text>
          <xpath function="available_capacity_dose2"/>
        </text>
      </template>
      <sort type="int" order="3" direction="descending">
        <text>
          <xpath function="available_capacity_dose2"/>
        </text>
      </sort>
    </field>
    <field>
      <header>
        <text>
          <locale id="m{module_id}.cowin.appointment.vaccine.header"/>
        </text>
      </header>
      <template>
        <text>
          <xpath function="vaccine"/>
        </text>
      </template>
    </field>
</detail>
"""


COWIN_APPOINTMENT_LONG_DETAIL_XML = """
<detail id="{detail_id}">
    <title>
      <text>
        <locale id="cchq.cowin.appointment"/>
      </text>
    </title>
    <field>
      <header>
        <text>
          <locale id="m{module_id}.cowin.appointment.name.header"/>
        </text>
      </header>
      <template>
        <text>
          <xpath function="name"/>
        </text>
      </template>
    </field>
    <field>
      <header>
        <text>
          <locale id="m{module_id}.cowin.appointment.available_capacity.header"/>
        </text>
      </header>
      <template>
        <text>
          <xpath function="available_capacity"/>
        </text>
      </template>
    </field>
    <field>
      <header>
        <text>
          <locale id="m{module_id}.cowin.appointment.available_capacity_dose1.header"/>
        </text>
      </header>
      <template>
        <text>
          <xpath function="available_capacity_dose1"/>
        </text>
      </template>
    </field>
    <field>
      <header>
        <text>
          <locale id="m{module_id}.cowin.appointment.available_capacity_dose2.header"/>
        </text>
      </header>
      <template>
        <text>
          <xpath function="available_capacity_dose2"/>
        </text>
      </template>
    </field>
    <field>
      <header>
        <text>
          <locale id="m{module_id}.cowin.appointment.vaccine.header"/>
        </text>
      </header>
      <template>
        <text>
          <xpath function="vaccine"/>
        </text>
      </template>
    </field>
    <field>
      <header>
        <text>
          <locale id="m{module_id}.cowin.appointment.fee.header"/>
        </text>
      </header>
      <template>
        <text>
          <xpath function="fee"/>
        </text>
      </template>
    </field>
    <field>
      <header>
        <text>
          <locale id="m{module_id}.cowin.appointment.slots.header"/>
        </text>
      </header>
      <template>
        <text>
          <xpath function="slots"/>
        </text>
      </template>
    </field>
    <field>
      <header>
        <text>
          <locale id="m{module_id}.cowin.appointment.min_age_limit.header"/>
        </text>
      </header>
      <template>
        <text>
          <xpath function="min_age_limit"/>
        </text>
      </template>
    </field>
</detail>
"""
