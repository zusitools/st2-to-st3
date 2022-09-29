#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import math
import xml.etree.ElementTree as ET
from collections import namedtuple

from . import common
from .common import readfloat, readfloatstr

VerknParameter = namedtuple(
    "VerknParameter", ["dateiname_zusi", "x", "y", "z", "rx", "ry", "rz", "boundingr"]
)


def conv_ls_elemente(f, num_elemente, filename):
    outname_rel = common.z2rel_to_z3rel(filename)
    outname_abs = common.z3rel_to_abs(outname_rel)
    os.makedirs(os.path.dirname(outname_abs), exist_ok=True)
    print(f" - conv_ls_elemente {filename} -> {outname_abs}", file=sys.stderr)
    with open(outname_abs, "w") as fout2_ls:
        fout2_ls.write(f"2.3\r\n{num_elemente}\r\n#\r\n")

        inhalt_boundingr_sq = 0
        elemente = []
        min_x = float("+inf")
        min_y = float("+inf")
        max_x = float("-inf")
        max_y = float("-inf")
        for _ in range(num_elemente):
            typ = int(f.readline().strip())
            if typ == 0:
                # Lichtquelle
                for _2 in range(11):
                    f.readline()
            else:
                f.readline()
                vertices = []
                for _2 in range(typ):
                    x = readfloat(f)
                    y = readfloat(f)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    z = readfloat(f)
                    vertices.append((x, y, z))
                c = int(f.readline().strip())
                cnight = int(f.readline().strip())
                blink = readfloatstr(f)
                f.readline()
                typ = int(f.readline().strip())
                f.readline()
                f.readline()
                # elemente[c].append(vertices)
                elemente.append((c, cnight, blink, typ, vertices))

        centerx = (max_x + min_x) / 2.0
        centery = (max_y + min_y) / 2.0

        for c, cnight, blink, typ, vertices in elemente:
            fout2_ls.write(f"{len(vertices)}\r\n#\r\n")
            for x, y, z in vertices:
                localx = x - centerx
                localy = y - centery
                inhalt_boundingr_sq = max(
                    inhalt_boundingr_sq, localx * localx + localy * localy
                )
                fout2_ls.write(str(localx).replace(".", ","))
                fout2_ls.write("\r\n")
                fout2_ls.write(str(localy).replace(".", ","))
                fout2_ls.write("\r\n")
                fout2_ls.write(str(z).replace(".", ","))
                fout2_ls.write("\r\n")
            fout2_ls.write(f"{c}\r\n{cnight}\r\n{blink}\r\n0\r\n{typ}\r\n#\r\n#\r\n")
        print(
            f" - #elemente={len(elemente)} {centerx=} {centery=} boundingr={math.sqrt(inhalt_boundingr_sq)}",
            file=sys.stderr,
        )

    return VerknParameter(
        outname_rel, centerx, centery, 0, 0, 0, 0, math.sqrt(inhalt_boundingr_sq)
    )


def conv_ls(filename, no_displacement=False):
    outname_rel = (
        common.z2rel_to_z3rel(filename)[:-3]
        + (".nd" if no_displacement else "")
        + ".ls3"
    )
    outname_abs = common.z3rel_to_abs(outname_rel)
    print(f"conv_ls {filename} -> {outname_abs}", file=sys.stderr)
    if no_displacement and os.path.exists(outname_abs):
        boundingr = 0
        with open(outname_abs) as f:
            root = ET.parse(f)
            for node in root.findall("Landschaft/Verknuepfte"):
                boundingr = max(boundingr, float(node.attrib.get("BoundingR", 0)))
        return VerknParameter(outname_rel, 0, 0, 0, 0, 0, 0, boundingr)

    os.makedirs(os.path.dirname(outname_abs), exist_ok=True)
    with open(outname_abs, "w") as fout:
        fout.write("<Zusi><Landschaft>\n")

        verknuepfungen = []
        with open(common.z2rel_to_abs(filename), "r") as f:
            f.readline()
            num_elemente = int(f.readline().strip())

            # Verknüpfte ls-Dateien
            while (datei := f.readline().strip()) != "#":
                verknuepfung = conv_ls(datei)
                x = readfloat(f)
                y = readfloat(f)
                z = readfloat(f)
                rx = readfloat(f)
                ry = readfloat(f)
                rz = readfloat(f)

                # https://stackoverflow.com/questions/14607640/rotating-a-vector-in-3d-space
                # In 3D rotating around the Z-axis would be
                #
                #     |cos θ   −sin θ   0| |x|   |x cos θ − y sin θ|   |x'|
                #     |sin θ    cos θ   0| |y| = |x sin θ + y cos θ| = |y'|
                #     |  0       0      1| |z|   |        z        |   |z'|
                #
                # around the Y-axis would be
                #
                #     | cos θ    0   sin θ| |x|   | x cos θ + z sin θ|   |x'|
                #     |   0      1       0| |y| = |         y        | = |y'|
                #     |−sin θ    0   cos θ| |z|   |−x sin θ + z cos θ|   |z'|
                #
                # around the X-axis would be
                #
                #     |1     0           0| |x|   |        x        |   |x'|
                #     |0   cos θ    −sin θ| |y| = |y cos θ − z sin θ| = |y'|
                #     |0   sin θ     cos θ| |z|   |y sin θ + z cos θ|   |z'|
                #

                # Rotiere den Verschiebungsvektor der Verknüpfung
                if rx or ry or rz:
                    x2 = verknuepfung.x * math.cos(rz) - verknuepfung.y * math.sin(rz)
                    y2 = verknuepfung.x * math.sin(rz) + verknuepfung.y * math.cos(rz)
                    z2 = verknuepfung.z

                    x3 = x2 * math.cos(ry) + z2 * math.sin(ry)
                    y3 = y2
                    z3 = -x2 * math.sin(ry) + z2 * math.cos(ry)

                    x4 = x3
                    y4 = y3 * math.cos(rx) - z3 * math.sin(rx)
                    z4 = y3 * math.sin(rx) + z3 * math.cos(rx)
                else:
                    x4 = verknuepfung.x
                    y4 = verknuepfung.y
                    z4 = verknuepfung.z

                verknuepfungen.append(
                    verknuepfung._replace(
                        x=x4 + x,
                        y=y4 + y,
                        z=z4 + z,
                        rx=rx,
                        ry=ry,
                        rz=rz,
                    )
                )

            # Inhalt der ls-Datei
            if num_elemente != 0:
                # liest den Rest von f
                verknuepfungen.append(conv_ls_elemente(f, num_elemente, filename))

        print(f"conv_ls {filename}: verknuepfungen:", file=sys.stderr)
        for verkn in verknuepfungen:
            print(f" - {verkn}", file=sys.stderr)

        if not len(verknuepfungen) or no_displacement:
            centerx = centery = 0
        else:
            centerx = (
                max(verkn.x + verkn.boundingr for verkn in verknuepfungen)
                + min(verkn.x - verkn.boundingr for verkn in verknuepfungen)
            ) / 2.0
            centery = (
                max(verkn.y + verkn.boundingr for verkn in verknuepfungen)
                + min(verkn.y - verkn.boundingr for verkn in verknuepfungen)
            ) / 2.0

        if len(verknuepfungen):
            # TODO fix bounding-Berechnung (Kreis, nicht Rechteck)
            max_x = max(
                max(
                    abs(verkn.x - centerx + verkn.boundingr),
                    abs(verkn.x - centerx - verkn.boundingr),
                )
                for verkn in verknuepfungen
            )
            max_y = max(
                max(
                    abs(verkn.y - centery + verkn.boundingr),
                    abs(verkn.y - centery - verkn.boundingr),
                )
                for verkn in verknuepfungen
            )
            boundingr = math.sqrt(max_x * max_x + max_y * max_y)

            for verkn in verknuepfungen:
                fout.write(
                    f'<Verknuepfte SichtbarBis="3000" BoundingR="{verkn.boundingr}"><Datei Dateiname="{verkn.dateiname_zusi}"/><p X="{verkn.x-centerx}" Y="{verkn.y-centery}" Z="{verkn.z}"/><phi X="{verkn.rx}" Y="{verkn.ry}" Z="{verkn.rz}"/></Verknuepfte>\n'
                )
        else:
            boundingr = 0

        print(f"{centerx=} {centery=} {boundingr=}", file=sys.stderr)
        fout.write("</Landschaft></Zusi>")

        return VerknParameter(outname_rel, centerx, centery, 0, 0, 0, 0, boundingr)
