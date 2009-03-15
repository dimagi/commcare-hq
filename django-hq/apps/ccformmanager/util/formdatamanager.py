class DataHandler
  def addForm(XSD/OurInternalFormDef form)
  should create all the tables necessary to save instances
  should update its metadata with enough information necessary to process instances (if necessary)

  def deleteForm()
  maybe not that necessary, delete all tables and data associated with a form.

  def saveData(XSD/OurInternalFormDef form, InstanceData instanced)
  should map all the instance data to the appropriate tables and save them.