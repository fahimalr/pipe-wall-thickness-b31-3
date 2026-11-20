import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipe_wall as pw

MATS = pw.load_materials()
SCHED = pw.load_schedules()
A106B = MATS["A106-B"]


def test_eq_3a_hand_calc():
    # docs/worked_example.md, step 2
    t = pw.pressure_design_thickness(5.0, 168.3, 137.9, e=1.0, w=1.0, y=0.4)
    assert t == pytest.approx(3.008, abs=0.001)


def test_worked_example_end_to_end():
    r = pw.size_line("6", 5.0, 150.0, A106B, allowances=3.0, schedules=SCHED)
    assert r.tm == pytest.approx(6.01, abs=0.01)
    assert (r.schedule, r.wall) == ("40", 7.11)
    assert r.mawp == pytest.approx(5.36, abs=0.01)
    assert r.p_test == pytest.approx(7.5)
    assert not r.test_limited


def test_mawp_inverts_thickness():
    # a pipe with exactly the pressure design thickness left must rate at P
    p, od, s = 9.9, 219.1, 120.0
    t = pw.pressure_design_thickness(p, od, s)
    assert pw.mawp(t, od, s, mill_tol=0.0) == pytest.approx(p)


def test_allowable_table_points_and_interpolation():
    assert A106B.allowable(20.0) == pytest.approx(20.0 * pw.KSI_TO_MPA)
    assert A106B.allowable(pw.f_to_c(500)) == pytest.approx(18.9 * pw.KSI_TO_MPA)
    mid = A106B.allowable(pw.f_to_c(550))
    assert mid == pytest.approx(0.5 * (18.9 + 17.3) * pw.KSI_TO_MPA)


def test_allowable_not_extrapolated():
    with pytest.raises(ValueError, match="above"):
        A106B.allowable(pw.f_to_c(750))
    with pytest.raises(ValueError, match="below"):
        A106B.allowable(-46.0)


@pytest.mark.parametrize("family,temp,expected", [
    ("ferritic", 150, 0.4), ("ferritic", 482, 0.4), ("ferritic", 510, 0.5),
    ("ferritic", 524, 0.6), ("ferritic", 600, 0.7),
    ("austenitic", 566, 0.4), ("austenitic", 593, 0.5), ("austenitic", 700, 0.7),
])
def test_y_coefficient(family, temp, expected):
    assert pw.y_coefficient(family, temp) == pytest.approx(expected)


def test_thick_wall_rejected():
    with pytest.raises(ValueError, match="0.385"):
        pw.pressure_design_thickness(60.0, 60.3, 137.9)


def test_schedule_uses_minimum_wall_not_nominal():
    # NPS 6 Sch 40: nominal 7.11, minimum 6.22. tm = 6.5 must go to Sch 80.
    assert pw.select_schedule("6", 6.2, SCHED) == ("40", 7.11)
    assert pw.select_schedule("6", 6.5, SCHED) == ("80", 10.97)


def test_no_schedule_available():
    assert pw.select_schedule("2", 50.0, SCHED) is None


def test_hydrotest_temperature_ratio():
    s_design = A106B.allowable(pw.f_to_c(700))
    s_test = A106B.allowable(20.0)
    pt = pw.hydrotest_pressure(10.0, s_design, s_test)
    assert pt == pytest.approx(1.5 * 10.0 * 20.0 / 16.5)


def test_hydrotest_ratio_capped():
    assert pw.hydrotest_pressure(1.0, 10.0, 100.0) == pytest.approx(1.5 * 6.5)


def test_yield_limit_consistent_with_hoop_stress():
    od, wall = 168.3, 6.22
    p = pw.yield_limited_pressure(od, wall, 241.0)
    assert pw.hoop_stress(p, od, wall) == pytest.approx(241.0)


def test_dimension_table_sane():
    for nps, (od, walls) in SCHED.items():
        thick = [w for _, w in walls]
        assert thick == sorted(thick)
        assert all(0 < w < od / 2 for w in thick)
    assert math.isclose(SCHED["6"][0], 168.3)


def test_test_pressure_reduced_to_yield():
    # low-yield material so that 1.5 P ST/S overstresses the minimum wall
    soft = pw.Material("soft", "ferritic", smys=110.0, smts=300.0, min_temp_c=-29.0,
                       temps_c=[38.0, 400.0], allow=[100.0, 60.0])
    r = pw.size_line("6", 6.0, 400.0, soft, allowances=0.0, schedules=SCHED)
    assert r.test_limited
    assert r.test_stress == pytest.approx(110.0)
    assert r.p_test < 1.5 * 6.0 * 100.0 / 60.0


def test_line_list_reports_bad_rows(tmp_path):
    f = tmp_path / "lines.csv"
    f.write_text("line,nps,pressure_mpa,temp_c,material,allowance_mm,e\n"
                 "A,6,5,150,A106-B,3,1\n"
                 "B,6,5,150,NOPE,3,1\n"
                 "C,6,5,450,A106-B,3,1\n")
    out = pw.run_line_list(f, MATS, SCHED).splitlines()
    assert "40" in out[2]
    assert "unknown material" in out[3]
    assert "above the tabulated range" in out[4]
