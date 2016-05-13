def get_short_decimal_display(num):
    try:
        return round(num, 2)
    except:
        return num
