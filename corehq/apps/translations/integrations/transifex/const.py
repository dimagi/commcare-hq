TRANSIFEX_SLUG_PREFIX_MAPPING = {
    'Menu': 'module',
    'Form': 'form',
}
SOURCE_LANGUAGE_MAPPING = {
    # HQ uses 3-letter codes with some exceptions, but Transifex uses 2-letter codes whenever possible
    # This maps HQ codes to their 2-letter equivalents where available in Transifex
    # Other languages may be unsupported by Transifex or require custom mapping
    # 'hq_code' : 'transifex_code'
    'abk': 'ab',  # Abkhazian
    'aka': 'ak',  # Akan
    'sqi': 'sq',  # Albanian
    'amh': 'am',  # Amharic
    'ara': 'ar',  # Arabic
    'arg': 'an',  # Aragonese
    'asm': 'as',  # Assamese
    'aym': 'ay',  # Aymara
    'aze': 'az',  # Azerbaijani
    'bak': 'ba',  # Bashkir
    'bam': 'bm',  # Bambara
    'eus': 'eu',  # Basque
    'bel': 'be',  # Belarusian
    'ben': 'bn',  # Bengali
    'bis': 'bi',  # Bislama
    'bos': 'bs',  # Bosnian
    'bre': 'br',  # Breton
    'bul': 'bg',  # Bulgarian
    'mya': 'my',  # Burmese
    'cat': 'ca',  # Catalan
    'cha': 'ch',  # Chamorro
    'che': 'ce',  # Chechen
    'zho': 'zh',  # Chinese
    'chv': 'cv',  # Chuvash
    'cor': 'kw',  # Cornish
    'cos': 'co',  # Corsican
    'ces': 'cs',  # Czech
    'dan': 'da',  # Danish
    'div': 'dv',  # Divehi
    'nld': 'nl',  # Dutch
    'dzo': 'dz',  # Dzongkha
    'epo': 'eo',  # Esperanto
    'est': 'et',  # Estonian
    'ewe': 'ee',  # Ewe
    'fao': 'fo',  # Faroese
    'fin': 'fi',  # Finnish
    'fra': 'fr',  # French
    'fry': 'fy',  # Western Frisian
    'ful': 'ff',  # Fulah
    'kat': 'ka',  # Georgian
    'deu': 'de',  # German
    'gla': 'gd',  # Gaelic
    'gle': 'ga',  # Irish
    'glg': 'gl',  # Galician
    'ell': 'el',  # Greek, Modern (1453-)
    'hat': 'ht',  # Haitian
    'hau': 'ha',  # Hausa
    'heb': 'he',  # Hebrew
    'hin': 'hi',  # Hindi
    'hrv': 'hr',  # Croatian
    'hun': 'hu',  # Hungarian
    'ibo': 'ig',  # Igbo
    'isl': 'is',  # Icelandic
    'ido': 'io',  # Ido
    'iku': 'iu',  # Inuktitut
    'ile': 'ie',  # Interlingue
    'ina': 'ia',  # Interlingua (International Auxiliary Language Association)
    'ind': 'id',  # Indonesian
    'ita': 'it',  # Italian
    'jav': 'jv',  # Javanese
    'jpn': 'ja',  # Japanese
    'kal': 'kl',  # Kalaallisut
    'kan': 'kn',  # Kannada
    'kas': 'ks',  # Kashmiri
    'kaz': 'kk',  # Kazakh
    'khm': 'km',  # Central Khmer
    'kik': 'ki',  # Kikuyu
    'kin': 'rw',  # Kinyarwanda
    'kir': 'ky',  # Kirghiz
    'kor': 'ko',  # Korean
    'kur': 'ku',  # Kurdish
    'lao': 'lo',  # Lao
    'lat': 'la',  # Latin
    'lav': 'lv',  # Latvian
    'lim': 'li',  # Limburgan
    'lin': 'ln',  # Lingala
    'lit': 'lt',  # Lithuanian
    'ltz': 'lb',  # Luxembourgish
    'lug': 'lg',  # Ganda
    'mkd': 'mk',  # Macedonian
    'mah': 'mh',  # Marshallese
    'mal': 'ml',  # Malayalam
    'mri': 'mi',  # Maori
    'mar': 'mr',  # Marathi
    'msa': 'ms',  # Malay
    'mlg': 'mg',  # Malagasy
    'mlt': 'mt',  # Maltese
    'mon': 'mn',  # Mongolian
    'nav': 'nv',  # Navajo
    'nbl': 'nr',  # Ndebele, South
    'nde': 'nd',  # Ndebele, North
    'nep': 'ne',  # Nepali
    'nno': 'nn',  # Norwegian Nynorsk
    'nob': 'nb',  # Bokml, Norwegian
    'nor': 'no',  # Norwegian
    'nya': 'ny',  # Chichewa
    'oci': 'oc',  # Occitan (post 1500)
    'ori': 'or',  # Oriya
    'orm': 'om',  # Oromo
    'oss': 'os',  # Ossetian
    'pan': 'pa',  # Panjabi
    'fas': 'fa',  # Persian
    'pol': 'pl',  # Polish
    'por': 'pt',  # Portuguese
    'pus': 'ps',  # Pushto
    'que': 'qu',  # Quechua
    'roh': 'rm',  # Romansh
    'ron': 'ro',  # Romanian
    'run': 'rn',  # Rundi
    'rus': 'ru',  # Russian
    'sag': 'sg',  # Sango
    'san': 'sa',  # Sanskrit
    'sin': 'si',  # Sinhala
    'slk': 'sk',  # Slovak
    'slv': 'sl',  # Slovenian
    'sme': 'se',  # Northern Sami
    'smo': 'sm',  # Samoan
    'sna': 'sn',  # Shona
    'snd': 'sd',  # Sindhi
    'som': 'so',  # Somali
    'sot': 'st',  # Sotho, Southern
    'srd': 'sc',  # Sardinian
    'srp': 'sr',  # Serbian
    'ssw': 'ss',  # Swati
    'sun': 'su',  # Sundanese
    'swe': 'sv',  # Swedish
    'tam': 'ta',  # Tamil
    'tat': 'tt',  # Tatar
    'tel': 'te',  # Telugu
    'tgk': 'tg',  # Tajik
    'tgl': 'tl',  # Tagalog
    'tha': 'th',  # Thai
    'bod': 'bo',  # Tibetan
    'tir': 'ti',  # Tigrinya
    'ton': 'to',  # Tonga (Tonga Islands)
    'tsn': 'tn',  # Tswana
    'tso': 'ts',  # Tsonga
    'tuk': 'tk',  # Turkmen
    'tur': 'tr',  # Turkish
    'uig': 'ug',  # Uighur
    'ukr': 'uk',  # Ukrainian
    'urd': 'ur',  # Urdu
    'uzb': 'uz',  # Uzbek
    'ven': 've',  # Venda
    'vie': 'vi',  # Vietnamese
    'vol': 'vo',  # Volapk
    'cym': 'cy',  # Welsh
    'wln': 'wa',  # Walloon
    'wol': 'wo',  # Wolof
    'xho': 'xh',  # Xhosa
    'yid': 'yi',  # Yiddish
    'yor': 'yo',  # Yoruba
    'zul': 'zu',  # Zulu
}
