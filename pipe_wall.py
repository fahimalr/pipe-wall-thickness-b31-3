"""
Straight pipe wall thickness and leak test pressure to ASME B31.3.

Covers internal pressure design of straight pipe (para. 304.1.2, eq. 3a),
selection of a B36.10M schedule, back-calculated MAWP and the hydrostatic
test pressure of para. 345.4.2.

Units are SI throughout: MPa (gauge), mm, deg C.

Not covered: external pressure, t >= D/6, bends, branches, flange ratings
or sustained/expansion stress checks.
"""

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

KSI_TO_MPA = 6.894757
MILL_TOL_DEFAULT = 0.125  # A106 / A53 / API 5L seamless under-tolerance on wall


def f_to_c(temp_f):
    return (temp_f - 32.0) / 1.8


def _interp(x, xs, ys):
    """Linear interpolation, no extrapolation."""
    if x < xs[0] or x > xs[-1]:
        raise ValueError(f"{x:g} is outside the tabulated range {xs[0]:g} to {xs[-1]:g}")
    for i in range(1, len(xs)):
        if x <= xs[i]:
            frac = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + frac * (ys[i] - ys[i - 1])
    return ys[-1]


# --- Materials -------------------------------------------------------------

@dataclass
class Material:
    name: str
    family: str          # "ferritic" or "austenitic", used for Y
    smys: float          # MPa
    smts: float          # MPa
    min_temp_c: float    # Table A-1 minimum temperature
    temps_c: list        # metal temperature points
    allow: list          # basic allowable stress S at those points, MPa

    def allowable(self, temp_c):
        """Basic allowable stress S at temperature. Between the minimum
        temperature and the first point the first value applies (Table A-1
        'min. temp. to 100 F' column)."""
        if temp_c < self.min_temp_c:
            raise ValueError(f"{temp_c:.0f} C is below the minimum temperature "
                             f"for {self.name} ({self.min_temp_c:.0f} C)")
        if temp_c > self.temps_c[-1]:
            raise ValueError(f"{temp_c:.0f} C is above the tabulated range "
                             f"for {self.name} ({self.temps_c[-1]:.0f} C)")
        if temp_c <= self.temps_c[0]:
            return self.allow[0]
        return _interp(temp_c, self.temps_c, self.allow)


def load_materials(path=DATA_DIR / "materials.csv"):
    """Read the allowable stress table. The file keeps the customary units
    of Table A-1 (deg F, ksi) so it can be checked against the code directly."""
    mats = {}
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            temps_f = [float(v) for v in row["temps_f"].split()]
            s_ksi = [float(v) for v in row["s_ksi"].split()]
            if len(temps_f) != len(s_ksi):
                raise ValueError(f"{row['name']}: temperature and stress columns differ in length")
            mats[row["name"]] = Material(
                name=row["name"],
                family=row["family"],
                smys=float(row["smys_ksi"]) * KSI_TO_MPA,
                smts=float(row["smts_ksi"]) * KSI_TO_MPA,
                min_temp_c=f_to_c(float(row["min_temp_f"])),
                temps_c=[f_to_c(t) for t in temps_f],
                allow=[s * KSI_TO_MPA for s in s_ksi],
            )
    return mats


# --- Pipe dimensions -------------------------------------------------------

def load_schedules(path=DATA_DIR / "pipe_schedules.csv"):
    """B36.10M dimensions as {nps: (od_mm, [(schedule, wall_mm), ...])},
    walls sorted thin to thick."""
    table = {}
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            nps = row["nps"]
            od = float(row["od_mm"])
            table.setdefault(nps, (od, []))[1].append((row["schedule"], float(row["wall_mm"])))
    for nps in table:
        table[nps][1].sort(key=lambda sw: sw[1])
    return table


# --- 304.1 Straight pipe under internal pressure ----------------------------

_Y_TABLE = {
    # Table 304.1.1, valid for t < D/6
    "ferritic":   ([482.0, 510.0, 538.0], [0.4, 0.5, 0.7]),
    "austenitic": ([566.0, 593.0, 621.0], [0.4, 0.5, 0.7]),
}


def y_coefficient(family, temp_c):
    try:
        temps, ys = _Y_TABLE[family]
    except KeyError:
        raise ValueError(f"no Y coefficient data for material family '{family}'") from None
    if temp_c <= temps[0]:
        return ys[0]
    if temp_c >= temps[-1]:
        return ys[-1]
    return _interp(temp_c, temps, ys)


def pressure_design_thickness(p, od, s, e=1.0, w=1.0, y=0.4):
    """Eq. (3a): t = P D / [2 (S E W + P Y)].

    p   internal design gauge pressure, MPa
    od  outside diameter, mm
    s   basic allowable stress at design temperature, MPa
    e   quality factor (Table A-1A / A-1B)
    w   weld joint strength reduction factor (302.3.5(e))
    y   coefficient from Table 304.1.1
    """
    if p <= 0:
        raise ValueError("design pressure must be positive")
    if p / (s * e) > 0.385:
        raise ValueError("P/SE > 0.385: outside eq. (3a), see para. 304.1.2(b)")
    t = p * od / (2.0 * (s * e * w + p * y))
    if t >= od / 6.0:
        raise ValueError("t >= D/6: outside eq. (3a), see para. 304.1.2(b)")
    return t


def min_required_thickness(t, allowances):
    """Eq. (2): tm = t + c. 'allowances' is the sum of corrosion, erosion and
    thread or groove depth."""
    return t + allowances


def mawp(wall_nominal, od, s, e=1.0, w=1.0, y=0.4, allowances=0.0, mill_tol=MILL_TOL_DEFAULT):
    """Eq. (3a) solved for P using the wall left after mill tolerance and
    allowances are taken off the nominal."""
    t = wall_nominal * (1.0 - mill_tol) - allowances
    if t <= 0:
        raise ValueError("no wall left after mill tolerance and allowances")
    return 2.0 * t * s * e * w / (od - 2.0 * t * y)


def select_schedule(nps, tm, schedules, mill_tol=MILL_TOL_DEFAULT):
    """Lightest listed wall whose minimum (nominal less mill tolerance) is
    at least tm. Returns (schedule, nominal wall) or None."""
    od, walls = schedules[nps]
    for sched, wall in walls:
        if wall * (1.0 - mill_tol) >= tm:
            return sched, wall
    return None


# --- 345 Leak testing ------------------------------------------------------

def hydrotest_pressure(p, s_design, s_test):
    """Para. 345.4.2, eq. (24): PT = 1.5 P ST / S, with ST/S not taken above 6.5."""
    ratio = min(s_test / s_design, 6.5)
    return 1.5 * p * ratio


def hoop_stress(p, od, wall, y=0.4):
    """Stress from eq. (3a) rearranged, with E = W = 1."""
    return p * (od - 2.0 * y * wall) / (2.0 * wall)


def yield_limited_pressure(od, wall_min, yield_at_test, y=0.4):
    """Pressure at which the eq. (3a) stress reaches yield at test
    temperature. Para. 345.2.1(a) allows the test pressure to be reduced
    to this (345.4.2(c) in older editions)."""
    return 2.0 * wall_min * yield_at_test / (od - 2.0 * y * wall_min)


# --- One line, start to finish ---------------------------------------------

@dataclass
class LineResult:
    line: str
    nps: str
    od: float
    s: float
    y: float
    t: float
    tm: float
    t_nominal_req: float
    schedule: str
    wall: float
    mawp: float
    p_test: float
    test_stress: float
    test_limited: bool


def size_line(nps, p, temp_c, material, allowances=0.0, e=1.0, w=1.0,
              mill_tol=MILL_TOL_DEFAULT, test_temp_c=20.0, schedules=None, line=""):
    schedules = schedules or load_schedules()
    if nps not in schedules:
        raise ValueError(f"NPS {nps} is not in the dimension table")
    od = schedules[nps][0]

    s = material.allowable(temp_c)
    y = y_coefficient(material.family, temp_c)
    t = pressure_design_thickness(p, od, s, e, w, y)
    tm = min_required_thickness(t, allowances)

    pick = select_schedule(nps, tm, schedules, mill_tol)
    if pick is None:
        raise ValueError(f"NPS {nps}: no listed schedule gives tm = {tm:.2f} mm")
    sched, wall = pick

    s_test = material.allowable(test_temp_c)
    p_test = hydrotest_pressure(p, s, s_test)
    wall_min = wall * (1.0 - mill_tol)
    y_test = y_coefficient(material.family, test_temp_c)
    limit = yield_limited_pressure(od, wall_min, material.smys, y_test)
    limited = p_test > limit
    if limited:
        p_test = limit

    return LineResult(
        line=line, nps=nps, od=od, s=s, y=y, t=t, tm=tm,
        t_nominal_req=tm / (1.0 - mill_tol),
        schedule=sched, wall=wall,
        mawp=mawp(wall, od, s, e, w, y, allowances, mill_tol),
        p_test=p_test,
        test_stress=hoop_stress(p_test, od, wall_min, y_test),
        test_limited=limited,
    )


# --- Reporting -------------------------------------------------------------

def calc_sheet(r, p, temp_c, material, allowances, e, w, mill_tol):
    rows = [
        ("Design pressure, P", f"{p:.3f} MPa(g)"),
        ("Design temperature", f"{temp_c:.0f} C"),
        ("Material", material.name),
        ("NPS / outside diameter, D", f"{r.nps} / {r.od:.1f} mm"),
        ("Allowable stress, S", f"{r.s:.1f} MPa"),
        ("Quality factor, E", f"{e:.2f}"),
        ("Weld strength reduction, W", f"{w:.2f}"),
        ("Coefficient, Y", f"{r.y:.2f}"),
        ("Pressure design thickness, t  [eq. 3a]", f"{r.t:.2f} mm"),
        ("Allowances, c", f"{allowances:.2f} mm"),
        ("Minimum required, tm = t + c  [eq. 2]", f"{r.tm:.2f} mm"),
        (f"Nominal required at {mill_tol * 100:.1f}% mill tol.", f"{r.t_nominal_req:.2f} mm"),
        ("Selected", f"Sch {r.schedule}, {r.wall:.2f} mm"),
        ("MAWP of selected pipe, corroded", f"{r.mawp:.3f} MPa(g)"),
        ("Hydrotest pressure  [345.4.2]", f"{r.p_test:.3f} MPa(g)"
            + ("  (reduced to yield limit)" if r.test_limited else "")),
        ("Stress at test pressure / SMYS", f"{r.test_stress:.0f} / {material.smys:.0f} MPa"),
    ]
    width = max(len(k) for k, _ in rows)
    return "\n".join(f"{k:<{width}}  {v}" for k, v in rows)


def run_line_list(path, materials, schedules):
    header = f"{'Line':<14}{'NPS':>5}{'P':>8}{'T':>6}{'tm':>8}{'Sch':>6}{'Wall':>8}{'MAWP':>8}{'Ptest':>8}"
    out = [header, "-" * len(header)]
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            p = float(row["pressure_mpa"])
            temp = float(row["temp_c"])
            try:
                if row["material"] not in materials:
                    raise ValueError(f"unknown material '{row['material']}'")
                r = size_line(
                    row["nps"], p, temp, materials[row["material"]],
                    allowances=float(row.get("allowance_mm") or 0.0),
                    e=float(row.get("e") or 1.0),
                    schedules=schedules, line=row["line"],
                )
            except ValueError as err:
                out.append(f"{row['line']:<14}{row['nps']:>5}{p:>8.2f}{temp:>6.0f}  ** {err}")
                continue
            out.append(
                f"{r.line:<14}{r.nps:>5}{p:>8.2f}{temp:>6.0f}{r.tm:>8.2f}"
                f"{r.schedule:>6}{r.wall:>8.2f}{r.mawp:>8.2f}{r.p_test:>8.2f}"
            )
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="B31.3 straight pipe wall thickness and hydrotest pressure")
    ap.add_argument("--line-list", help="CSV of lines to size (see examples/line_list.csv)")
    ap.add_argument("--nps", help="nominal pipe size, e.g. 6 or 1.5")
    ap.add_argument("--pressure", type=float, help="design pressure, MPa(g)")
    ap.add_argument("--temp", type=float, help="design temperature, C")
    ap.add_argument("--material", default="A106-B")
    ap.add_argument("--allowance", type=float, default=0.0, help="corrosion + thread/groove allowance, mm")
    ap.add_argument("--e", type=float, default=1.0, help="quality factor E")
    ap.add_argument("--w", type=float, default=1.0, help="weld joint strength reduction factor W")
    ap.add_argument("--mill-tol", type=float, default=MILL_TOL_DEFAULT)
    args = ap.parse_args(argv)

    materials = load_materials()
    schedules = load_schedules()

    if args.line_list:
        print(run_line_list(args.line_list, materials, schedules))
        return 0

    if args.nps is None or args.pressure is None or args.temp is None:
        ap.error("give --line-list, or --nps, --pressure and --temp")
    if args.material not in materials:
        ap.error(f"unknown material '{args.material}'. Available: {', '.join(materials)}")

    mat = materials[args.material]
    try:
        r = size_line(args.nps, args.pressure, args.temp, mat, args.allowance,
                      args.e, args.w, args.mill_tol, schedules=schedules)
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    print(calc_sheet(r, args.pressure, args.temp, mat, args.allowance, args.e, args.w, args.mill_tol))
    return 0


if __name__ == "__main__":
    sys.exit(main())
