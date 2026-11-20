# Pipe Wall Thickness and Hydrotest Calculator (ASME B31.3)

Sizes straight process pipe for internal pressure to ASME B31.3 and picks the
lightest ASME B36.10M schedule that meets it. For the selected pipe it also
reports the corroded MAWP and the hydrostatic test pressure.

The numbers are checked against a hand calculation in
[docs/worked_example.md](docs/worked_example.md), which is also the reference
case for the tests.

## What it does

- Pressure design thickness, `t`, from para. 304.1.2 eq. (3a)
- Minimum required thickness, `tm = t + c`, eq. (2)
- Schedule selection on **minimum** wall (nominal less mill tolerance), not nominal
- MAWP of the selected schedule in the corroded condition
- Hydrotest pressure from para. 345.4.2, including the `ST/S` temperature
  correction, and the check against yield at test temperature (para. 345.2.1)
- Single line from the command line, or a whole line list from a CSV

## Methods

| Step | Reference | Notes |
|---|---|---|
| Allowable stress `S` | Table A-1 | Linear interpolation between tabulated temperatures, no extrapolation |
| Coefficient `Y` | Table 304.1.1-1 | Ferritic and austenitic steels, `t < D/6` |
| Thickness `t` | 304.1.2, eq. (3a) | `t = P D / [2 (S E W + P Y)]` |
| Required `tm` | 304.1.1, eq. (2) | `c` = corrosion + erosion + thread or groove depth |
| Mill tolerance | Material spec. | 12.5% default (A106, A53, API 5L seamless) |
| Test pressure | 345.4.2, eq. (24) | `PT = 1.5 P ST/S`, not less than `1.5 P` |
| Yield limit at test | 345.2.1(a) | Test pressure reduced if the stress on minimum wall would exceed yield |

Clause, table and equation numbers follow ASME B31.3-2024. Earlier editions
number some of them differently.

Units are SI: MPa(g), mm and deg C. The allowable stress file is kept in
deg F and ksi so it can be compared line by line with Table A-1.

## Running it

Python 3.9 or later. No third-party packages are needed to run it.

One line:

```
python pipe_wall.py --nps 6 --pressure 5.0 --temp 150 --allowance 3.0
```

```
Design pressure, P                      5.000 MPa(g)
Design temperature                      150 C
Material                                A106-B
NPS / outside diameter, D               6 / 168.3 mm
Allowable stress, S                     137.9 MPa
Quality factor, E                       1.00
Weld strength reduction, W              1.00
Coefficient, Y                          0.40
Pressure design thickness, t  [eq. 3a]  3.01 mm
Allowances, c                           3.00 mm
Minimum required, tm = t + c  [eq. 2]   6.01 mm
Nominal required at 12.5% mill tol.     6.87 mm
Selected                                Sch 40, 7.11 mm
MAWP of selected pipe, corroded         5.361 MPa(g)
Hydrotest pressure  [345.4.2]           7.500 MPa(g)
Stress at test pressure / SMYS          98 / 241 MPa
```

A line list:

```
python pipe_wall.py --line-list examples/line_list.csv
```

```
Line            NPS       P     T      tm   Sch    Wall    MAWP   Ptest
-----------------------------------------------------------------------
2-P-1001          2    5.00   150    4.08    80    5.54    8.66    7.50
6-P-1002          6    5.00   150    6.01    40    7.11    5.36    7.50
8-P-1003          8    9.90   260   11.08    80   12.70    9.94   15.71
12-P-1004        12    9.90   343   14.82    80   17.48   10.26   17.47
1-U-2001          1    1.90    60    1.83    40    3.38   11.59    2.85
16-P-1005        16   14.00   370   26.81   120   30.96   14.18   25.42
```

As a module:

```python
import pipe_wall as pw

mat = pw.load_materials()["A106-B"]
r = pw.size_line("8", 9.9, 260, mat, allowances=3.0)
print(r.schedule, r.wall, round(r.mawp, 2))
```

Tests:

```
pip install pytest
pytest
```

## Line list format

| Column | Meaning |
|---|---|
| `line` | Line number or tag |
| `nps` | Nominal pipe size (`0.5`, `1.5`, `6`, ...) |
| `pressure_mpa` | Design pressure, MPa(g) |
| `temp_c` | Design temperature, deg C |
| `material` | Name from `data/materials.csv` |
| `allowance_mm` | Corrosion plus mechanical allowance, mm |
| `e` | Quality factor `E` (1.0 for seamless) |

## Data

- `data/pipe_schedules.csv`: outside diameters and wall thicknesses from
  ASME B36.10M, NPS 1/2 to 16, Sch 40 and heavier for NPS 6 and below.
  Light-wall schedules (5, 10) are left out, so "lightest schedule" means
  lightest of those listed. NPS 10 and 12 use the B36.10M outside diameters
  (273.0 and 323.8 mm); API 5L rounds these to 273.1 and 323.9 mm.
- `data/materials.csv`: basic allowable stresses for A106 Gr. B and A53 Gr. B
  seamless, -20 F to 700 F. Temperatures outside that range are rejected.
  Add a row to add a material.

## Limitations

- Straight pipe under internal pressure only. No external pressure, bends,
  mitres, branch reinforcement, flange ratings or flexibility analysis.
- Eq. (3a) only. Cases with `t >= D/6` or `P/SE > 0.385` are rejected rather
  than calculated.
- Allowable stresses change between code editions. The values in
  `data/materials.csv` must be checked against the edition that governs the
  job before the output is relied on.
- The yield check at test pressure uses SMYS and the minimum (uncorroded)
  wall of the selected schedule.
- Test pressure is worked out line by line. A real test system takes in
  several lines and components, and its pressure is set by the weakest of them.
- No impact test or minimum design metal temperature assessment beyond the
  Table A-1 minimum temperature.
- This is a learning and portfolio project. It is not a substitute for the
  code or for a checked project calculation.

## Author

Fahim Al-Rashid Chowdhury, M.Sc. Mechanical Engineering, University of Alberta.

## Licence

MIT. See [LICENSE](LICENSE).
