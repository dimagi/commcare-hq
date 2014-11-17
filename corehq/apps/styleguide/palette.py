class PaletteColorGroup(object):
    """This defines a group of palette colors that fall under
    the same classification"""
    def __init__(self, name, slug, primary, light, dark,
                 usage=None):
        self.name = name
        self.slug = slug
        self.primary = primary
        self.light = light
        self.dark = dark


class PaletteColor(object):
    """This defines the different color values of a color
    """
    def __init__(self, hex_val, cmyk=None, pantone=None, usage=None, name=None):
        self.hex = hex_val
        self.rgb = {
            'r': int(hex_val[0:2], 16),
            'g': int(hex_val[2:4], 16),
            'b': int(hex_val[4:6], 16),
        }
        if cmyk is not None:
            self.cmyk = {
                'c': cmyk[0],
                'm': cmyk[1],
                'y': cmyk[2],
                'k': cmyk[3],
            }
        else:
            self.cmyk = None
        self.pantone = pantone
        self.usage = usage
        self.name = name


class Palette(object):
    """This defines the structure of the CCHQ Color Palette
    """
    def __init__(self, color_groups, text_color, bg_color):
        self.color_groups = color_groups
        self.text_color = text_color
        self.bg_color = bg_color
