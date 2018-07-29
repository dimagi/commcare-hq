def get_short_decimal_display(num):
    try:
        if num % 1 == 0:
            return int(num)
        return round(num, 2)
    except:
        return num
