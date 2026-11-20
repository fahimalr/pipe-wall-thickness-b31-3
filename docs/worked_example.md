# Worked example

A hand calculation for one line, used as the reference case in
`tests/test_pipe_wall.py`.

## Design basis

| Item | Value |
|---|---|
| Line size | NPS 6, D = 168.3 mm |
| Design pressure, P | 5.0 MPa(g) |
| Design temperature | 150 C (302 F) |
| Material | ASTM A106 Gr. B, seamless |
| Corrosion allowance, c | 3.0 mm |
| Quality factor, E | 1.0 (seamless) |
| Weld strength reduction, W | 1.0 (below the creep range) |
| Mill tolerance | 12.5% |

## 1. Allowable stress and Y

Table A-1 gives S = 20.0 ksi for A106 Gr. B at both 300 F and 400 F, so at
302 F:

    S = 20.0 ksi = 137.9 MPa

Table 304.1.1, ferritic steel at or below 482 C:

    Y = 0.4

## 2. Pressure design thickness, eq. (3a)

    t = P D / [2 (S E W + P Y)]
      = (5.0 x 168.3) / [2 x (137.9 x 1.0 x 1.0 + 5.0 x 0.4)]
      = 841.5 / 279.8
      = 3.01 mm

Check on the limits of eq. (3a): D/6 = 28.1 mm, so t < D/6, and
P/SE = 0.036, well under 0.385.

## 3. Minimum required thickness, eq. (2)

    tm = t + c = 3.01 + 3.0 = 6.01 mm

## 4. Schedule

The ordered pipe can be 12.5% under nominal, so the nominal wall has to be at
least

    6.01 / 0.875 = 6.87 mm

NPS 6 Sch 40 is 7.11 mm nominal, 6.22 mm minimum. 6.22 > 6.01, so Sch 40 is
acceptable.

Note that comparing tm with the nominal wall directly would be wrong: a
required tm of 6.5 mm looks fine against 7.11 mm but is not met by the
6.22 mm minimum, and the line would need Sch 80.

## 5. MAWP of Sch 40, corroded

Wall available for pressure after mill tolerance and corrosion:

    t = 7.11 x 0.875 - 3.0 = 3.22 mm

Eq. (3a) solved for P:

    P = 2 t S E W / (D - 2 t Y)
      = (2 x 3.22 x 137.9) / (168.3 - 2 x 3.22 x 0.4)
      = 888.3 / 165.7
      = 5.36 MPa(g)

That is 7% above the design pressure.

## 6. Hydrostatic test pressure, para. 345.4.2

The allowable stress at test temperature (20 C) equals the value at design
temperature, so ST/S = 1.0:

    PT = 1.5 P ST/S = 1.5 x 5.0 x 1.0 = 7.5 MPa(g)

Stress at test pressure on the minimum wall of new pipe:

    S = PT (D - 2 Y t) / (2 t)
      = 7.5 x (168.3 - 2 x 0.4 x 6.22) / (2 x 6.22)
      = 98 MPa

SMYS is 241 MPa, so the test pressure does not need to be reduced.

## Result

| Item | Hand | Program |
|---|---|---|
| t | 3.01 mm | 3.01 mm |
| tm | 6.01 mm | 6.01 mm |
| Schedule | 40 | 40 |
| MAWP | 5.36 MPa | 5.361 MPa |
| Test pressure | 7.5 MPa | 7.500 MPa |

## A case where temperature matters

The same calculation at 370 C (698 F) gives S = 16.5 ksi, and the test
pressure picks up the ratio ST/S = 20.0 / 16.5 = 1.21. Line `16-P-1005` in
`examples/line_list.csv` shows this: design pressure 14.0 MPa, test pressure
25.4 MPa instead of 21.0 MPa.
