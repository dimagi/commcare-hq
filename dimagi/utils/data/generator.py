import random

# these lists arbitrarily generated once from http://www.generatedata.com/

FIRST_NAMES = [ "Abraham", "Adam", "Adena", "Alana", "Alexandra", "Alvin", "Amos",
                "Anthony", "Ariel", "Beck", "Beverly", "Branden", "Brian", "Brooke", "Burton",
                "Cain", "Camilla", "Carissa", "Castor", "Cedric", "Celeste", "Christopher",
                "Ciaran", "Colorado", "Dakota", "Dara", "David", "Desiree", "Dominic",
                "Dustin", "Echo", "Elton", "Fay", "Fleur", "Gary", "Gavin", "Grace",
                "Hashim", "Haviva", "Hilel", "Howard", "Ian", "Idola", "Idola", "Isaac",
                "Jael", "Jane", "Jeanette", "Jescie", "Joan", "Joelle", "Judah", "Kai", "Kasimir",
                "Kendall", "Kenneth", "Kylie", "Kylynn", "Lacota", "Lance", "Lee", "Leigh",
                "Lila", "Lillian", "Lillian", "Linus", "Lucas", "Malachi", "Martha", "Martin",
                "McKenzie", "Melanie", "Mercedes", "Michelle", "Moana", "Nelle", "Pearl",
                "Petra", "Preston", "Priscilla", "Quon", "Rahim", "Rebekah", "Rhiannon",
                "Ronan", "Ryan", "Rylee", "Sara", "Serina", "Shafira", "Shaine", "Silas",
                "Sloane", "Stuart", "Troy", "Unity", "Venus", "William", "Yeo" ]

LAST_NAMES = [ "Acevedo", "Acosta", "Andrews", "Baldwin", "Ball", "Barton", "Bean", "Berger",
               "Blackburn", "Blevins", "Burgess", "Burris", "Calderon", "Cantrell", "Carlson", "Carpenter",
               "Carver", "Christensen", "Clayton", "Conrad", "Cummings", "Delacruz", "Dillard", "Dorsey",
               "Elliott", "Floyd", "French", "Guthrie", "Guy", "Hale", "Haney", "Hardin",
               "Harvey", "Holden", "Hunt", "Irwin", "Jacobson", "Jefferson", "Johns", "Johnston",
               "Jones", "Keith", "Keith", "Lambert", "Levine", "Lucas", "Lyons", "Manning",
               "Mcbride", "Mcfadden", "Mcfarland", "Mcgowan", "Mckee", "Miller", "Montoya", "Morales",
               "Nash", "Nielsen", "Owen", "Page", "Parks", "Parsons", "Paul", "Pena",
               "Perkins", "Pittman", "Reese", "Reilly", "Rhodes", "Riddle", "Roberts", "Robinson",
               "Rollins", "Rosa", "Rosales", "Ruiz", "Rush", "Sampson", "Schneider", "Sellers",
               "Shannon", "Simpson", "Snyder", "Stevenson", "Swanson", "Tate", "Thornton", "Turner",
               "Vinson", "Waller", "Webster", "William", "Wilson", "Wong" ]

def random_firstname():
    return random.choice(FIRST_NAMES) 

def random_lastname():
    return random.choice(LAST_NAMES) 

def random_fullname():
    return "%s %s" % (random_firstname(), random_lastname())

def random_username():
    return username_from_name(random_fullname())

def username_from_name(name):
    if " " not in name:
        return name.lower()
    splits = name.split(" ")
    return ("%s%s" % (splits[0][0], splits[-1])).lower()

def random_phonenumber(numdigits=11):
    return "+" + "".join(str(random.randint(0,9)) for i in range(numdigits))

