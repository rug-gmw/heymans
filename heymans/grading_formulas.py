import math


def ug_bss(score: float) -> float:
    """Converts an average score in the 0-1 range to a 0-10 grade using the
    University of Groningen BSS regulations on rounding and knowledge rate.
    These regulations are such that grades are rounded to half a point, using 
    mathematical rounding (not bankers rounding). An exception is made for 
    5.5. Any value between 5 (inclusive) and 5.5 (exclusive) is rounded down 
    to a 5.0. The minimum possible grade is a 1.
    
    This is based on the RUG Bachelor and Master Psychology OER 2024 - 2025.

    Examples
    --------
    >>> ug_bss(0.9) # Integer grade without rounding
    9.0
    >>> ug_bss(0.91) # Integer grade with rounding down
    9.0
    >>> ug_bss(0.89) # Integer grade with rounding up
    9.0
    >>> ug_bss(0.75) # Half point grade without rounding
    7.5
    >>> ug_bss(0.76) # Grade rounds to nearest half point (7.5)
    7.5
    >>> ug_bss(0.74) # Grade rounds to nearest half point (7.5)
    7.5
    >>> ug_bss(0.54) # Exception: rounded down to 5.0
    5.0
    >>> ug_bss(0.55) # 5.5 exists and is not rounded down
    5.5
    >>> ug_bss(0) # The minimum grade is a 1
    1
    """
    grade = score * 10
    if 5.0 <= grade < 5.5:
        return 5.0
    scaled_grade = grade * 2
    rounded_scaled = _round_half_up(scaled_grade)
    rounded_grade = rounded_scaled / 2
    return max(1.0, rounded_grade)
    
    
def _round_half_up(n):
    """Round a number to the nearest integer, with ties rounded up. This
    implements mathematical rounding, not bankers rounding. This is
    necessary because Python's built-in round() function uses bankers 
    rounding.
    """
    integer_part = math.floor(n)
    fractional_part = n - integer_part
    if fractional_part >= 0.5:
        return integer_part + 1
    else:
        return integer_part    
