1. Introduce a postgres django model that saves documents to both couch and postgres
2. Save all existing couch docs of that type to postgres
3. Changing all query code so that it pulls data from postgres
4. Removing the couch views
5. Stop saving to couch

Document | Owner | Phase
---------|-------|------
Toggle | @emord | 1
