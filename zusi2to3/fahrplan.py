#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import xml.etree.ElementTree as ET

from . import common


def conv_fpn(fpnname, st3_name, rekursionstiefe):
    seen_nrs = set()
    with open(fpnname, "r", encoding="iso-8859-1") as f:
        f.readline()

        inname2_rel = (
            os.path.relpath(fpnname, common.Z2ABS).replace(os.sep, "\\")[:-1] + "n"
        )
        outname2_rel = common.z2rel_to_z3rel(inname2_rel)
        outname2_abs = common.z3rel_to_abs(outname2_rel)

        print(f"{fpnname} -> {outname2_abs}", file=sys.stderr)
        n_root = ET.Element("Zusi")
        tree = ET.ElementTree(n_root)
        n_fahrplan = ET.SubElement(
            n_root, "Fahrplan", {"AnfangsZeit": f.readline().strip()}
        )
        ET.SubElement(
            ET.SubElement(n_fahrplan, "StrModul"), "Datei", {"Dateiname": st3_name}
        )

        while (zugdatei := f.readline()) :
            n_trn = ET.SubElement(
                n_fahrplan, "trn", {"Rekursionstiefe": str(rekursionstiefe)}
            )
            with open(
                os.path.join(
                    os.path.dirname(fpnname), zugdatei.strip().replace("\\", os.sep)
                ),
                "r",
                encoding="iso-8859-1",
            ) as f2:
                f2.readline()
                orig_zugnr = f2.readline().strip()
                zugnr = orig_zugnr
                i = 1
                while zugnr in seen_nrs:
                    zugnr = f"{orig_zugnr}_{i}"
                    i += 1
                seen_nrs.add(zugnr)
                n_trn.attrib["Nummer"] = zugnr
                n_trn.attrib["Gattung"] = f2.readline().strip()
                f2.readline().strip()  # TODO Bremsstellung
                n_fahrzeuge_minus_1 = int(f2.readline())
                lok_gedreht = f2.readline().strip() == "-1"
                f2.readline()
                n_trn.attrib["spZugNiedriger"] = str(float(f2.readline()) / 3.6)
                f2.readline()
                f2.readline()  # Lok
                while f2.readline().strip() != "#IF":  # PZB-Modus
                    pass
                n_trn.attrib["Prio"] = f2.readline().strip()
                f2.readline()  # Einsatzreferenz
                f2.readline()  # Treibstoffvorrat
                f2.readline()  # reserviert
                f2.readline()  # reserviert
                f2.readline()  # Zugtyp
                n_trn.attrib["Zuglauf"] = f2.readline().strip()
                f2.readline()  # Türsystem
                for i in range(6):
                    f2.readline()  # reserviert
                erster_eintrag = True
                hat_zugwende = False
                while (betrst := f2.readline().strip()) != "#IF":
                    n_fahrplaneintrag = ET.SubElement(
                        n_trn, "FahrplanEintrag", {"Betrst": betrst}
                    )
                    n_fahrplaneintrag.attrib["Ank"] = f2.readline().strip()
                    n_fahrplaneintrag.attrib["Abf"] = f2.readline().strip()
                    while (gleis := f2.readline().strip()) != "#":
                        ET.SubElement(
                            n_fahrplaneintrag,
                            "FahrplanSignalEintrag",
                            {"FahrplanSignal": gleis},
                        )
                        if erster_eintrag:
                            erster_eintrag = False
                            n_trn.attrib[
                                "FahrstrName"
                            ] = f"Aufgleispunkt -> {betrst} {gleis}"
                    if hat_zugwende:
                        n_trn.remove(n_fahrplaneintrag)  # TODO
                    while (spezialaktion := f2.readline().strip()) != "#":
                        if spezialaktion in ["1", "2"]:
                            print(
                                f'{n_trn.attrib["Gattung"]} {n_trn.attrib["Nummer"]}: Zugwende {n_fahrplaneintrag.attrib["Betrst"]}',
                                file=sys.stderr,
                            )
                            hat_zugwende = True
                        f2.readline()
                        f2.readline()
                    f2.readline()

                for i in range(n_fahrzeuge_minus_1):
                    f2.readline()
                    f2.readline()
                    f2.readline()

            ET.SubElement(
                ET.SubElement(
                    ET.SubElement(
                        n_trn,
                        "FahrzeugVarianten",
                        {"Bezeichnung": "default", "ZufallsWert": "1"},
                    ),
                    "FahrzeugInfo",
                    {"IDHaupt": "1", "IDNeben": "1"},
                ),
                "Datei",
                {
                    "Dateiname": r"rollingstock\Deutschland\Epoche5\Dieseltriebwagen\RegioShuttle\RS1.rv.fzg"
                },
            )

        tree.write(outname2_abs, encoding="unicode")
