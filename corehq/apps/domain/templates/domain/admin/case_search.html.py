BBBBBBB BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB
BBBB BBBBBBBBBBBBBB
BBBB BBBB

BBBBBBBBBBBBBB BBBBBBBBBBBBBBBBBBBBBBBBBBBB

BBBBB BBBBBBBBBBBB
  BBBBBBB BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB
  BBBBBBBBBBBBBBBBB BBBBBBBBBBBB BBBBBBBBBB
  BBBBBBBBBBBBBBBBB BBBBBBBB BBBBBB
  BBBBBBBBBBB BBBBBBBBBBBBBBBBBBBB BBBBBBBBBBBBBB
  XXXX gettext(u'Enable Case Search') XXXXX

  XXXX XXXXXXXXXXXX
    XXXX XXXXXXXXXXXXXXXXX
      XXXXX XXXXXXXXXXXXXXXXXXXXXXXX
        BBBBBBBBBB
        XXXX XXXXXXXXXXXXXXXXXXXXXX XXXXXXXXXXXXXXXXXX
        XX XXXXXXXXXXXXXXXXXXX

        XXX
           gettext(u"Enabling case search for the project will allow mobile users to look up cases\n            that don't necessarily belong to them, and claim them. Possible applications range from cases\n            for patients who move from one location to another, and other lost-to-follow-up scenarios, to\n            any scenario involving searching for information, products, people or items.") SSSSSSSS SSSS SSSSSS SSS SSS SSSSSSS SSSS SSSSS SSSSSS SSSSS SS SSSS SS SSSSS
            SSSS SSSSS SSSSSSSSSSS SSSSSS SS SSSSS SSS SSSSS SSSSS SSSSSSSS SSSSSSSSSSSS SSSSS SSSS SSSSS
            SSS SSSSSSSS SSS SSSS SSSS SSS SSSSSSSS SS SSSSSSSS SSS SSSSS SSSSSSSSSSSSSSSSS SSSSSSSSSS SS
            SSS SSSSSSSS SSSSSSSSS SSSSSSSSS SSS SSSSSSSSSSSS SSSSSSSSS SSSSSS SS SSSSSS
        XXXX
        XX XXXXXXXXXXXXXXXXXXXX
           gettext(u"WARNING: Enabling Case Search allows users to read the data of\n            other users' cases, and take ownership of them, from modules whose case lists are configured\n            for searching.") SSSSSSSS SSSSSSSS SSSS SSSSSS SSSSSS SSSSS SS SSSS SSS SSSS SS
            SSSSS SSSSSS SSSSSS SSS SSSS SSSSSSSSS SS SSSSS SSSS SSSSSSS SSSSS SSSS SSSSS SSS SSSSSSSSSS
            SSS SSSSSSSSSS
        XXXX

        XXX
          XXXXXX XXXXXXXXXXX XXXXXXXXXXXXXXX XXXXXXXXXXXXXXXXXXX XXXXXXXXXXXXXXXX
          XXXXXX XXXXXXXXXXXXX gettext(u'Enable Case Search') XXXXXXXX
        XXXX

        BB BBBBBBBBBBBBBBBBBBBBBBBBB
          XXXX XXXXXXXXXXXXXXXXXXX XXXXXXXXXXXXXXX
             gettext(u"\n              Visit <a href='%(case_search_url)s' target='_blank'>Case Search</a> to test out your configuration.\n            ") 
              SSSSS SS SSSSSSSSSSSSSSSSSSSSSSSSSS SSSSSSSSSSSSSSSSSSSS SSSSSSSSSS SS SSSS SSS SSSS SSSSSSSSSSSSSS
            
          XXXXXX
        BBBBB

        XXXX XXXXXXXXXXXXXXXX XXXXXXXXXXXXXXXXXXX XXXXXXXXXXXXXXX
          XXXX gettext(u'Fuzzy Search Properties') XXXXX
          XXX
             gettext(u'\n              Add a list of all fuzzy search properties by case type below. These are\n              properties that might be spelled inexactly by a user, e.g. "name".\n              <br><br>\n              When working with related case properties, add them to the case type that\n              you will be searching on, not the related case type. For example, if fuzzy matching\n              on the parent\'s case name, add <strong>parent/name</strong> here as a property of\n              the child case type.\n            ') 
              SSS S SSSS SS SSS SSSSS SSSSSS SSSSSSSSSS SS SSSS SSSS SSSSSS SSSSS SSS
              SSSSSSSSSS SSSS SSSSS SS SSSSSSS SSSSSSSSS SS S SSSSS SSSS SSSSSSS
              SSSSSSSS
              SSSS SSSSSSS SSSS SSSSSSS SSSS SSSSSSSSSSS SSS SSSS SS SSS SSSS SSSS SSSS
              SSS SSSS SS SSSSSSSSS SSS SSS SSS SSSSSSS SSSS SSSSS SSS SSSSSSSS SS SSSSS SSSSSSSS
              SS SSS SSSSSSSS SSSS SSSSS SSS SSSSSSSSSSSSSSSSSSSSSSSSSSSS SSSS SS S SSSSSSSS SS
              SSS SSSSS SSSS SSSSS
            
          XXXX

          XXXX XXXXXXXXXXXXXXXXXXXX X XXXXX XXXXXXXXXXXXXXXXXXXXX
                                    XXXXXXXX XXXXXXXXXXXXXXXX
                                    XXX XXXXXXXXXXXXXXX XXXXXXXXX
          XXXXXXX XXXXXXXXXXXXX
                  XXXXXXXXXX XXXXXXXXXXXX
                  XXXXXXXXXXXXXXXXX XXXXXXXXXXXXXXXXXXX
            XX XXXXXXXXX XXXXXXXXXXXXX  gettext(u'Add case type') 
          XXXXXXXXX
        XXXXXX

        XXXX XXXXXXXXXXXXXXXXXXX XXXXXXXXXXXXXXX
          XXXX gettext(u'Synchronous Web Apps Submissions') XXXXX
          XXX
            XXXXXX XXXXXXXXXXXXXXXXXX XXXXXXXXXXXXXXX XXXXXXXXXXXXXXXXXXX XXXXXXXXXXXXXXXXXXXXX
            XXXXXX XXXXXXXXXXXXXXXXXXXX
               gettext(u'\n                Update case search data immediately on web apps form submission.\n              ') 
                SSSSSS SSSS SSSSSS SSSS SSSSSSSSSSS SS SSS SSSS SSSS SSSSSSSSSSS
              
            XXXXXXXX
          XXXX
          XX XXXXXXXXXXXXXXXXXXX
             gettext(u'\n              This will slow down submissions but prevent case search data from going stale.\n            ') 
              SSSS SSSS SSSS SSSS SSSSSSSSSSS SSS SSSSSSS SSSS SSSSSS SSSS SSSS SSSSS SSSSSS
            
          XXXX
        XXXXXX

        XXXX XXXXXXXXXXXXXXXXXXX XXXXXXXXXXXXXXX
          XXXX gettext(u'Sync Cases On Form Entry') XXXXX
          XXX
            XXXXXX XXXXXXXXXXXXXXXXXXXXXXXXXXXX XXXXXXXXXXXXXXX XXXXXXXXXXXXXXXXXXX XXXXXXXXXXXXXXXXXXXXXX
            XXXXXX XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
               gettext(u'\n                Update local case data immediately before entering a web apps form.\n              ') 
                SSSSSS SSSSS SSSS SSSS SSSSSSSSSSS SSSSSS SSSSSSSS S SSS SSSS SSSSS
              
            XXXXXXXX
          XXXX
          XX XXXXXXXXXXXXXXXXXXX
             gettext(u'\n              This will slow down form entry, but will prevent stale case data from populating the form.\n            ') 
              SSSS SSSS SSSS SSSS SSSS SSSSSS SSS SSSS SSSSSSS SSSSS SSSS SSSS SSSS SSSSSSSSSS SSS SSSSS
            
          XXXX
        XXXXXX

        XXXX XXXXXXXXXXXXXXXXXXX XXXXXXXXXXXXXXX
          XXXX gettext(u'Remove Special Characters') XXXXX
          XXX
             gettext(u"\n              Remove characters from incoming search queries for particular case properties. For example, you can remove '+' from phone numbers or '-' from ID queries.\n            ") 
              SSSSSS SSSSSSSSSS SSSS SSSSSSSS SSSSSS SSSSSSS SSS SSSSSSSSSS SSSS SSSSSSSSSSS SSS SSSSSSSS SSS SSS SSSSSS SSS SSSS SSSSS SSSSSSS SS SSS SSSS SS SSSSSSSS
            
          XXXX
          XXXXXX XXXXXXXXXXXX XXXXXXXXXXXXXXX
            XXXXXXX
            XXXX
              XXXX XXXX
            XXXXX
            XXXX
              XXXX XXXXXXXX
            XXXXX
            XXXX
              XXXXXX XX XXXXXX
            XXXXX
            XXXXXXXXX
            XXXXXXXX
            XXXXXX XXXXXXXXXXXXXXXXXXX XXXXXXXXXXXXXXXX
            XXXX
              XXXX
                XXXXXXX XXXXXXXXXXXXXXXXXXXX XXXXXXXXXXXXXXXXXXX XXXXXXXXXXXXXXXX XXXXXX XXXXXXXXXXXXXXXXXXX
              XXXXX
              XXXX
                XXXXXX XXXXXXXXXXX XXXXXXXXXXXXXXXXXXXX XXXXXXXXXXXXXXXXX XXXXXXXXXXXXX XXXXXXXXXXXXXXXXX XXXXX XX
              XXXXX
              XXXX
                XXXXXX XXXXXXXXXXX XXXXXXXXXXXXXXXXXXXX XXXXXXXXXXXXXXXXX XXXXXX XXXXXXXXXXXXXXXXX XX XX
              XXXXX
              XXXX
                XXXXXXX XXXXXXXXXXXXX
                        XXXXXXXXXX XXXXXXXXXX XXXXXXXXXXX
                        XXXXXXXXXXXXXXXXX XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX XXXXXXXXXXXXXXXXXXXX
                  XX XXXXXXXXX XXXXXXXXXXXXXX
                XXXXXXXXX
              XXXXX
            XXXXX
            XXXXXXXX
          XXXXXXXX
          XXXXXXX XXXXXXXXXXXXX
                  XXXXXXXXXX XXXXXXXXXXXX
                  XXXXXXXXXXXXXXXXX XXXXXXXXXXXXXXXXXXX
            XX XXXXXXXXX XXXXXXXXXXXXX  gettext(u'Add case property') 
          XXXXXXXXX
        XXXXXX
      XXXXXXX
    XXXXXX
  XXXXXX

BBBBBBBB
