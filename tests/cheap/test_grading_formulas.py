from heymans.grading_formulas import ug_bss


def test_ug_bss():
    # Test cases from the docstring
    assert ug_bss(0.9) == 9.0
    assert ug_bss(0.91) == 9.0
    assert ug_bss(0.89) == 9.0
    assert ug_bss(0.75) == 7.5
    assert ug_bss(0.76) == 7.5
    assert ug_bss(0.74) == 7.5
    assert ug_bss(0.54) == 5.0
    assert ug_bss(0.55) == 5.5
    assert ug_bss(0.0) == 1.0

    # Additional test cases
    assert ug_bss(1.0) == 10.0
    assert ug_bss(0.549) == 5.0
    assert ug_bss(0.56) == 5.5
    assert ug_bss(0.574) == 5.5
    assert ug_bss(0.575) == 6
    assert ug_bss(0.749) == 7.5
    assert ug_bss(0.751) == 7.5
    assert ug_bss(0.775) == 8.0
    assert ug_bss(0.499) == 5.0
