import numpy as np


def groningen(score: int | float) -> float:
    """Converts an average score in the 0-1 range to a 0-10 grade using the
    University of Groningen standard, where only half-points are provided and
    a 5.5 is never given.
    """
    grade = 10 * score
    rounded_grade = round(grade * 2) / 2
    if rounded_grade == 5.5:
        rounded_grade = round(grade)
    return rounded_grade
