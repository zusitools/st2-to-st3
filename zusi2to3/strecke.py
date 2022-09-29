#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import copy
import enum
import os
import math
import xml.etree.ElementTree as ET
from collections import defaultdict, namedtuple

from . import common, landschaft
from .common import readfloat, readfloatstr


class RefTyp(enum.IntEnum):
    AUFGLEISPUNKT = 0
    REGISTER = 2
    WEICHE = 3
    SIGNAL = 4
    AUFLOESEPUNKT = 5
    SIGNAL_GEGENRICHTUNG = 8
    WEICHE_GEGENRICHTUNG = 9


def get_ref_nr(elem_nr, ref_typ):
    return 10 * elem_nr + ref_typ


def allocate_refpunkt(n_strecke, elem_nr, ref_typ):
    n_re = ET.SubElement(n_strecke, "ReferenzElemente")
    n_re.attrib["ReferenzNr"] = str(get_ref_nr(elem_nr, ref_typ))
    n_re.attrib["StrElement"] = str(elem_nr)
    if ref_typ == RefTyp.SIGNAL_GEGENRICHTUNG:
        n_re.attrib["RefTyp"] = "4"
    elif ref_typ == RefTyp.WEICHE_GEGENRICHTUNG:
        n_re.attrib["RefTyp"] = "3"
    else:
        n_re.attrib["RefTyp"] = str(ref_typ)
        n_re.attrib["StrNorm"] = "1"

    return n_re


VerknParameter = namedtuple(
    "VerknParameter", ["dateiname_zusi", "x", "y", "z", "rx", "ry", "rz", "boundingr"]
)


class Signal:
    def __init__(self):
        self.elnr = 0
        self.block = ""
        self.gleis = ""
        self.matrix = []
        self.vsig_geschw = []
        self.hsig_geschw = []
        self.vsigs = []
        self.anzahl_sigframes = 0


class MatrixZeile:
    def __init__(self):
        self.block = ""
        self.gleis = ""
        self.vmax = 0
        self.spalten = []


class MatrixEintrag:
    def __init__(self):
        self.bild = 0
        self.vmax = 0
        self.id = 0
        self.er1 = 0
        self.er2 = 0


def conv_ereignis(er_nr, parent_node):
    if er_nr == 0:  # Kein Ereignis
        pass
    elif (
        er_nr >= 1 and er_nr <= 499
    ):  # Bedingte Entgleisung, wird ausgelöst bei "Fahrt-Geschwindigkeit in km/h größer Ereigniswert" (+Toleranz)
        return ET.SubElement(
            parent_node, "Ereignis", {"Er": "1", "Wert": str(er_nr / 3.6)}
        )
    elif er_nr == 500:  # PZB 500 Hz-Beeinflussung
        return ET.SubElement(parent_node, "Ereignis", {"Er": "500"})
    elif er_nr == 1000:  # PZB 1000 Hz-Beeinflussung
        return ET.SubElement(parent_node, "Ereignis", {"Er": "1000"})
    elif (
        er_nr >= 1001 and er_nr <= 1500
    ):  # Bedingte 1000 Hz-PZB-Beeinflussung, wird ausgelöst bei "Fahrt-Geschwindigkeit in km/h größer (Ereigniswert - 1000)", also z.B. 1105: 1000 Hz Beeinflussung bei 105 km/h und mehr
        return ET.SubElement(
            parent_node, "Ereignis", {"Er": "1000", "Wert": str(er_nr - 1000)}
        )
    elif er_nr == 2000:  # PZB 2000 Hz-Beeinflussung
        return ET.SubElement(parent_node, "Ereignis", {"Er": "2000"})
    elif (
        er_nr >= 2001 and er_nr <= 2500
    ):  # Bedingte 2000 Hz-PZB-Beeinflussung (Geschwindigkeitsprüfabschnitt), wird ausgelöst bei "Fahrt-Geschwindigkeit in km/h größer (Ereigniswert - 2000)"
        return ET.SubElement(
            parent_node, "Ereignis", {"Er": "2000", "Wert": str(er_nr - 2000)}
        )
    elif (
        er_nr == 3001
    ):  # Fahrstraße anfordern (wird standardmäßig nicht gebraucht, da die Züge automatisch anfordern)
        pass
    elif er_nr == 3002:  # Fahrstraße auflösen
        pass
    elif (
        er_nr == 3003
    ):  # Zug entfernen (Zug wird sofort entfernt und der belegte Blockabschnitt freigegeben)
        pass
    elif er_nr == 3004:  # Zwangshalt
        pass
    elif er_nr == 3005:  # Langsamfahrt Ende
        pass
    elif er_nr == 3006:  # Betriebsstelle
        pass
    elif er_nr == 3007:  # Haltepunkt erwarten
        pass
    elif er_nr == 3008:  # Bahnsteigmitte, s. auch
        pass
    elif er_nr == 3009:  # Bahnsteigende, s. auch
        pass
    elif er_nr == 3010:  # Langsamfahrt Anfang
        pass
    elif er_nr == 3011:  # Pfeifen, Kurz vorher Pfeifen - Mißachtung führt zu Punktabzug
        pass
    elif er_nr == 3012:  # LZB-Anfang (Zug wird in die LZB aufgenommen)
        pass
    elif (
        er_nr == 3013
    ):  # LZB-Ende (Zug wird am vorhergehenden Hauptsignal aus der LZB entlassen)
        pass
    elif (
        er_nr == 3021
    ):  # Vorher keine Fahrstraße (Bis der Zug dieses Ereignis überquert hat, wird ihm keine Fahrstraße mehr gestellt), Hinweise
        pass
    elif (
        er_nr == 3022
    ):  # Zp9-Signal (muß in den Eigenschaften eines Fahrstraßensignals gesetzt werden, dann wird dieses erst beim Abfahrtauftrag auf "Fahrt" gestellt)
        pass
    elif (
        er_nr == 3023
    ):  # Weiterfahrt nach Halt, Überfahren ohne vorigen Halt führt zu Punktabzug
        pass
    elif er_nr == 3024:  # Signum Warnung
        pass
    elif er_nr == 3025:  # Signum Halt
        pass
    elif (
        er_nr == 3026
    ):  # Sich nähernder Zug bekommt frühestens 1000m vor diesem Ereignis die nächste Fahrstraße, Hinweise
        pass
    elif (
        er_nr == 3027
    ):  # Sich nähernder Zug bekommt frühestens 2000m vor diesem Ereignis die nächste Fahrstraße, Hinweise
        pass
    elif (
        er_nr == 3028
    ):  # Sich nähernder Zug bekommt frühestens 3000m vor diesem Ereignis die nächste Fahrstraße, Hinweise
        pass
    elif (
        er_nr == 3029
    ):  # Vorher keine Vorsignalverknüpfung - Hauptsignal ignoriert beim Verknüpfen der Signallogik alle Vorsignale vor diesem Ereignis
        pass
    elif er_nr == 3030:  # Ereignis ohne Funktion
        pass
    elif er_nr == 3031:  # Befehl A
        pass
    elif er_nr == 3032:  # Befehl A (Stillstand)
        pass
    elif er_nr == 3033:  # Befehl B
        pass
    elif er_nr == 3034:  # Befehl B (Stillstand)
        pass
    elif er_nr == 3035:  # Langsamfahrtende (Zuganfang)
        pass
    elif (
        er_nr == 3036
    ):  # Wendepunkt (wird nur im Fahrplaneditor benötigt, Kennzeichnet Wendepunkte, muß hinter dem Wende-HSig liegen)
        pass
    elif (
        er_nr == 3037
    ):  # Wendepunkt auf anderen Blocknamen (wenn das Hsig vor dem Wendemanöver einen anderen Blocknamen hat als das nach dem Wenden)
        pass
    elif (
        er_nr == 3038
    ):  # Signal ist zugbedient (muß in den Eigenschaften eines Fahrstraßensignals gesetzt werden, dann wird dieses durch Ereignis 3039 gestellt), s. auch hier
        pass
    elif er_nr == 3039:  # Zugbedientes Signal schalten, s. auch hier
        pass
    elif er_nr == 3040:  # Streckensound, Sound-Datei unter "Beschreibung" angeben
        pass
    elif er_nr == 3041:  # Abrupt-Halt: Zug wird schlagartig gestoppt
        pass
    elif er_nr == 4000:  # GNT: Keine Geschwindigkeitserhöhung
        pass
    elif er_nr == 4001:  # GNT-Anfang
        pass
    elif er_nr == 4002:  # GNT-Ende
        pass
    elif (
        er_nr == 4003
    ):  # GNT: PZB-Unterdrückung auf 150 m (alle PZB-Magnete werden auf den nächsten 150 m unterdrückt)
        pass
    elif (
        er_nr >= 4004 and er_nr <= 4500
    ):  # GNT: Erhöhung der GNT-Geschwindigkeit gegenüber normaler Geschwindigkeit
        pass


def conv_str(strname):
    elements = {}
    nodes = {}
    signale = {}
    anonymesignale = {}
    fahrstrsignale = set()
    regnr = 20000  # TODO

    n_root = ET.Element("Zusi")
    tree = ET.ElementTree(n_root)
    n_strecke = ET.SubElement(n_root, "Strecke")

    f = open(strname, "r", encoding="iso-8859-1")
    inname_rel = os.path.relpath(f.name[:-1] + "3", common.Z2ABS).replace(os.sep, "\\")
    outname_rel = common.z2rel_to_z3rel(inname_rel)

    zusiversion = f.readline().strip()
    if zusiversion != "2.3":
        print("Version", zusiversion, "wird nicht gelesen")
        sys.exit()

    for i in range(0, 2):
        f.readline()

    rekursionstiefe = int(f.readline())

    for i in range(0, 2):
        while not f.readline().startswith("#"):
            pass

    f.readline()
    ls_datei = f.readline().strip()

    ET.SubElement(
        n_strecke,
        "Datei",
        {
            "Dateiname": landschaft.conv_ls(ls_datei, no_displacement=True)[0],
        },
    )

    aufgleispunkte = {}
    while not (refnr := f.readline()).startswith("#"):
        elem_nr = int(f.readline())
        aufgleispunkte[int(refnr)] = elem_nr
        beschr = f.readline().strip()
        n_re = allocate_refpunkt(n_strecke, elem_nr, RefTyp.AUFGLEISPUNKT)
        n_re.attrib["Info"] = beschr

    while not f.readline().startswith("#"):
        pass

    while True:
        elem_nr = f.readline()

        if elem_nr == "":
            break
        else:
            elem_nr = int(elem_nr)

        n_str_element = ET.SubElement(n_strecke, "StrElement")
        nodes[elem_nr] = n_str_element
        n_str_element.attrib["Nr"] = str(elem_nr)
        n_str_element.attrib["Anschluss"] = str(0xFF00)

        # "Keine Fahrstraße einrichten" in Gegenrichtung -- sollte nicht notwendig sein,
        # weil nicht der 3D-Editor die Fahrstraßen erzeugt, sondern dieses Skript.
        if False:
            n_gegen = ET.SubElement(n_str_element, "InfoGegenRichtung")
            ET.SubElement(n_gegen, "Ereignis").attrib["Er"] = "21"
            ET.SubElement(n_gegen, "Ereignis").attrib["Er"] = "22"
            ET.SubElement(n_gegen, "Ereignis").attrib["Er"] = "45"

        n_norm = ET.SubElement(n_str_element, "InfoNormRichtung")

        # 32945,2  Kilometrierung in m
        # +  Zählrichtung der Kilometrierung, zulässige Werte: + (aufsteigend), - (absteigend)
        # Rehbergtunnel  Landschaftsbezeichnung, # wiederholt die Bezeichnung vom Vorgängerelement
        # 3007  Ereignis, Codierung s. Ereignisse
        # 3214,451  x-Anfangs-Standortkoordinate
        # 318,345  y-Anfangs-Standortkoordinate
        # 30,853  z-Anfangs-Standortkoordinate
        # 3193,437  x-End-Standortkoordinate
        # 312,234  y-End-Standortkoordinate
        # 31,439  z-End-Standortkoordinate
        # -0,0231  Überhöhung in rad
        n_norm.attrib["km"] = str(readfloat(f) / 1000)
        if f.readline().strip() == "+":
            n_norm.attrib["pos"] = "1"

        f.readline()
        er_nr = int(f.readline())
        conv_ereignis(er_nr, n_norm)

        n_g = ET.SubElement(n_str_element, "g")
        n_g.attrib["X"] = readfloatstr(f)
        n_g.attrib["Y"] = readfloatstr(f)
        n_g.attrib["Z"] = readfloatstr(f)

        n_b = ET.SubElement(n_str_element, "b")
        n_b.attrib["X"] = readfloatstr(f)
        n_b.attrib["Y"] = readfloatstr(f)
        n_b.attrib["Z"] = readfloatstr(f)

        n_str_element.attrib["Ueberh"] = readfloatstr(f)

        succ = [
            x
            for x in [int(f.readline()), int(f.readline()), int(f.readline())]
            if x != 0
        ]
        for nr in succ:
            ET.SubElement(n_str_element, "NachNorm").attrib["Nr"] = str(nr)

        if len(succ) > 1:
            allocate_refpunkt(n_strecke, elem_nr, RefTyp.WEICHE)

        block = None
        gleis = None

        n_norm.attrib["vMax"] = str(readfloat(f) / 3.6)
        for i in range(0, 4):
            f.readline()

        if (fstrsig_x := readfloatstr(f)) is not None:
            # Fahrstraßensignal wird in die Gegenrichtung des Elements eingebaut.
            # So kommen einander Fahrstraßensignal und Kombisignal nicht in die Quere.
            # Aktiviere "Fahrstraßensignal gilt für beide Fahrtrichtungen" und
            # die BÜ-Steuerung. Fahrstraßensignale in Zusi 2 haben immer eine eingebaute BÜ-Steuerung.
            fahrstrsignale.add(elem_nr)
            n_gegen = ET.SubElement(n_str_element, "InfoGegenRichtung")
            n_signal = ET.SubElement(n_gegen, "Signal")
            n_signal.attrib["SignalFlags"] = "9"
            allocate_refpunkt(n_strecke, elem_nr, RefTyp.SIGNAL_GEGENRICHTUNG)
            boundingr = 0

            n_p = ET.SubElement(n_signal, "p")
            n_p.attrib["X"] = fstrsig_x
            n_p.attrib["Y"] = readfloatstr(f)
            n_p.attrib["Z"] = readfloatstr(f)

            n_phi = ET.SubElement(n_signal, "phi")
            n_phi.attrib["X"] = readfloatstr(f)
            n_phi.attrib["Y"] = str(-readfloat(f))  # TODO warum?
            n_phi.attrib["Z"] = readfloatstr(f)

            for i in range(6):
                f.readline()

            sigframe_statisch = f.readline().strip()
            n_sigframe_statisch = ET.SubElement(n_signal, "SignalFrame")
            conv = landschaft.conv_ls(sigframe_statisch, no_displacement=True)
            ET.SubElement(n_sigframe_statisch, "Datei").attrib[
                "Dateiname"
            ] = conv.dateiname_zusi
            boundingr = max(boundingr, conv.boundingr)

            f.readline()  # ohne Funktion
            if not (sigframe_nicht_gestellt := f.readline()).startswith("#"):
                n_sigframe_nicht_gestellt = ET.SubElement(n_signal, "SignalFrame")
                conv = landschaft.conv_ls(
                    sigframe_nicht_gestellt.strip(), no_displacement=True
                )
                ET.SubElement(n_sigframe_nicht_gestellt, "Datei").attrib[
                    "Dateiname"
                ] = conv.dateiname_zusi
                boundingr = max(boundingr, conv.boundingr)
                f.readline()  # ohne Funktion

                sigframe_gestellt = f.readline().strip()
                n_sigframe_gestellt = ET.SubElement(n_signal, "SignalFrame")
                conv = landschaft.conv_ls(sigframe_gestellt, no_displacement=True)
                ET.SubElement(n_sigframe_gestellt, "Datei").attrib[
                    "Dateiname"
                ] = conv.dateiname_zusi
                boundingr = max(boundingr, conv.boundingr)
                f.readline()  # ohne Funktion

                f.readline()  # Signalbilder-Endmarke

            fstrsig_er_nr = int(f.readline())  # TODO

            ET.SubElement(n_signal, "HsigBegriff", {"FahrstrTyp": "1"})

            ET.SubElement(
                n_signal,
                "HsigBegriff",
                {
                    "HsigGeschw": "-1",
                    "FahrstrTyp": "1",  # Fahrweg
                },
            )
            ET.SubElement(n_signal, "VsigBegriff", {"VsigGeschw": "-1"})

            me = ET.SubElement(
                n_signal,
                "MatrixEintrag",
                {
                    "MatrixGeschw": "-1",
                    "Signalbild": "3",
                },
            )
            conv_ereignis(fstrsig_er_nr, me)

            me = ET.SubElement(
                n_signal,
                "MatrixEintrag",
                {
                    "MatrixGeschw": "-1",
                    "Signalbild": "5",
                },
            )
            conv_ereignis(fstrsig_er_nr, me)

            n_signal.attrib["BoundingR"] = str(int(math.ceil(boundingr)))

            f.readline()  # Am Signal angekündigte Geschwindigkeit
            if (fstrsig_koppelsignal_element := int(f.readline())) != 0:
                ET.SubElement(
                    ET.SubElement(
                        n_signal,
                        "KoppelSignal",
                        {
                            "ReferenzNr": str(
                                get_ref_nr(
                                    fstrsig_koppelsignal_element,
                                    RefTyp.SIGNAL_GEGENRICHTUNG,
                                )
                            )
                        },
                    ),
                    "Datei",
                    {"Dateiname": outname_rel, "NurInfo": "1"},
                )

        if (x1 := readfloat(f)) is not None:
            # Kombisignal
            sig = Signal()
            n_signal = ET.SubElement(n_norm, "Signal")
            boundingr = 0

            y1 = readfloat(f)
            z1 = readfloat(f)
            rx1 = readfloatstr(f)
            ry1 = readfloatstr(f)
            rz1 = readfloatstr(f)

            x2 = readfloat(f)
            y2 = readfloat(f)
            z2 = readfloat(f)
            rx2 = readfloatstr(f)
            ry2 = readfloatstr(f)
            rz2 = readfloatstr(f)

            if not x1 and not y1 and not z1:
                xorigin, yorigin, zorigin = x2, y2, z2
            elif not x2 and not y2 and not z2:
                xorigin, yorigin, zorigin = x1, y1, z1
            else:
                xorigin, yorigin, zorigin = (
                    (x1 + x2) / 2.0,
                    (y1 + y2) / 2.0,
                    (z1 + z2) / 2.0,
                )

            ET.SubElement(
                n_signal,
                "p",
                {
                    "X": str(xorigin),
                    "Y": str(yorigin),
                    "Z": str(zorigin),
                },
            )

            # Erste .ls-Datei
            sigframes = []
            while not (lsdatei := f.readline().strip()).startswith("#"):
                sig.anzahl_sigframes += 1
                n_signalframe = ET.Element("SignalFrame")
                sigframes.append(n_signalframe)
                conv = landschaft.conv_ls(lsdatei, no_displacement=True)
                ET.SubElement(
                    n_signalframe, "Datei", {"Dateiname": conv.dateiname_zusi}
                )
                boundingr = max(boundingr, conv.boundingr)
                # Position
                if f.readline().startswith("2"):
                    ET.SubElement(
                        n_signalframe,
                        "p",
                        {
                            "X": str(x2 - xorigin),
                            "Y": str(y2 - yorigin),
                            "Z": str(z2 - zorigin),
                        },
                    )
                    ET.SubElement(
                        n_signalframe,
                        "phi",
                        {
                            "X": str(rx2),
                            "Y": str(ry2),
                            "Z": str(rz2),
                        },
                    )
                else:
                    ET.SubElement(
                        n_signalframe,
                        "p",
                        {
                            "X": str(x1 - xorigin),
                            "Y": str(y1 - yorigin),
                            "Z": str(z1 - zorigin),
                        },
                    )
                    ET.SubElement(
                        n_signalframe,
                        "phi",
                        {
                            "X": str(rx1),
                            "Y": str(ry1),
                            "Z": str(rz1),
                        },
                    )

            sig.elnr = elem_nr
            sig.block = f.readline().strip()
            sig.gleis = f.readline().strip()

            numzeilen = int(f.readline()) + 1
            numspalten = int(f.readline()) + 1

            sig.matrix = []

            seen_blocks = set()
            for i in range(0, numzeilen):
                # Fahrziel-Block, Fahrziel-Gleis, vmax, #, #
                mz = MatrixZeile()
                mz.block = f.readline().strip()
                mz.gleis = f.readline().strip()
                if mz.block or mz.gleis:
                    assert f"{mz.block} {mz.gleis}" not in seen_blocks
                    seen_blocks.add(f"{mz.block} {mz.gleis}")
                mz.vmax = int(f.readline())
                sig.matrix.append(mz)
                f.readline()
                f.readline()

                if True:  # mz.vmax == 0 or mz.block or mz.gleis:
                    n_hsig_begriff = ET.SubElement(
                        n_signal,
                        "HsigBegriff",
                        {
                            "FahrstrTyp": "6",
                            "HsigGeschw": "0" if mz.vmax == 0 else str(mz.vmax / 3.6),
                        },
                    )

            # if any(mz.vmax == 0 for mz in sig.matrix):
            #    ET.SubElement(n_norm, "Ereignis", {"Er":"29", "Beschr": f"{sig.block} {sig.gleis}"})

            for i in range(0, numspalten):
                vsig_geschw = int(f.readline())
                sig.vsig_geschw.append(vsig_geschw)
                n_vsig_begriff = ET.SubElement(
                    n_signal,
                    "VsigBegriff",
                    {
                        "VsigGeschw": "-1"
                        if vsig_geschw == -1
                        else str(vsig_geschw / 3.6),
                    },
                )

            # Aus bei Hp0
            f.readline()

            for i in range(0, numzeilen):
                mz = sig.matrix[i]
                for j in range(0, numspalten):
                    me = MatrixEintrag()
                    me.bild = int(f.readline())
                    me.vmax = int(f.readline())
                    if me.vmax == 0 and sig.matrix[i].vmax != 0:
                        print(
                            f"Element {elem_nr}, Zeile {i}, Spalte {j}: v=0, aber Zeile v!=0",
                            file=sys.stderr,
                        )
                    me.id = int(f.readline())
                    me.er1 = int(f.readline())
                    me.er2 = int(f.readline())
                    f.readline()

                    sig.matrix[i].spalten.append(me)

                    if True:  # mz.vmax == 0 or mz.block or mz.gleis:
                        n_me = ET.SubElement(
                            n_signal,
                            "MatrixEintrag",
                            {
                                "MatrixGeschw": "-1"
                                if me.vmax == -1
                                else str(me.vmax / 3.6),
                                "Signalbild": str(me.bild),
                            },
                        )

            ersatz_bild = int(f.readline())
            ersatz_vmax = int(f.readline())
            ersatz_id = int(f.readline())
            ersatz_er1 = int(f.readline())
            ersatz_er2 = int(f.readline())
            ersatz_reserviert = f.readline()
            f.readline()  # Wahrsch. Ersatzsignal

            vsig = f.readline()
            while not vsig.startswith("#"):
                sig.vsigs.append(int(vsig))
                vsig = f.readline()

            f.readline()  # reserviert

            if sig.block != "" and sig.gleis != "":
                n_signal.attrib["NameBetriebsstelle"] = sig.block
                n_signal.attrib["Stellwerk"] = sig.block
                n_signal.attrib["Signalname"] = sig.gleis
                signale[elem_nr] = sig
            else:
                n_signal.attrib["Signalname"] = f"Element {elem_nr}"
                anonymesignale[elem_nr] = sig

            for sigframe in sigframes:
                n_signal.append(sigframe)

            n_signal.attrib["BoundingR"] = str(int(math.ceil(boundingr)))

            allocate_refpunkt(n_strecke, elem_nr, RefTyp.SIGNAL)

        register = int(f.readline())

        if er_nr == 3002:
            allocate_refpunkt(n_strecke, elem_nr, RefTyp.AUFLOESEPUNKT)

            if register == 0:
                print(
                    f"kein Register an Auflöseelement {elem_nr}, erfinde eins",
                    file=sys.stderr,
                )
                register = regnr
                regnr += 1

        if block is not None and gleis is not None:
            elements[elem_nr]["block"] = block
            elements[elem_nr]["gleis"] = gleis

        if register != 0:
            n_norm.attrib["Reg"] = str(register)
            allocate_refpunkt(n_strecke, elem_nr, RefTyp.REGISTER)

        elements[elem_nr] = {
            "succ": succ,
            "register": register,
            "aufloesepunkt": er_nr == 3002,
        }

    for elem_nr, element in elements.items():
        for succ in element["succ"]:
            ET.SubElement(nodes[succ], "NachGegen").attrib["Nr"] = str(elem_nr)
            try:
                preds = elements[succ]["pred"]
            except KeyError:
                elements[succ]["pred"] = [elem_nr]
                continue

            if len(preds) == 1:
                allocate_refpunkt(n_strecke, succ, RefTyp.WEICHE_GEGENRICHTUNG)
            preds.append(elem_nr)

    # Fahrstraßen

    def v_kleiner(v1, v2):
        if v2 == -1:
            return True
        elif v1 == -1:
            return False
        else:
            return v1 < v2

    def get_vsig_spalte(sig, v, ID):
        id_counter = 0
        for idx, vsig_geschw in enumerate(sig.vsig_geschw):
            if v == vsig_geschw:
                if id_counter == ID:
                    return idx
                else:
                    id_counter += 1

        spalte = 0
        spalte_geschw = -1
        for idx, vsig_geschw in enumerate(sig.vsig_geschw):
            if v != 0 and vsig_geschw != 0:
                if v_kleiner(vsig_geschw, v):
                    if vsig_geschw > spalte_geschw:
                        spalte = idx
                        spalte_geschw = vsig_geschw

        return spalte

    def get_aufloesepunkte_rek(elnr, startnr, n_fahrstrasse):
        while True:
            element = elements[elnr]
            if elnr != startnr:
                if element["aufloesepunkt"]:
                    ET.SubElement(
                        ET.SubElement(
                            n_fahrstrasse,
                            "FahrstrAufloesung",
                            {"Ref": str(get_ref_nr(elnr, 5))},
                        ),
                        "Datei",
                        {"Dateiname": outname_rel, "NurInfo": "1"},
                    )
                    break

                if elnr in signale:
                    sig = signale[elnr]
                    if any(mz.vmax == 0 for mz in sig.matrix):
                        break

            succs = element["succ"]
            if not succs:
                break
            for idx in range(1, len(succs)):
                get_aufloesepunkte_rek(startnr, succs[idx], n_fahrstrasse)
            elnr = succs[0]

    def get_fahrstr_rek(startnrs, elnr, n_fahrstrasse):
        while True:
            element = elements[elnr]
            if elnr != startnrs[-1]:
                if element["register"]:
                    ET.SubElement(
                        ET.SubElement(
                            n_fahrstrasse,
                            "FahrstrRegister",
                            {"Ref": str(get_ref_nr(elnr, 2))},
                        ),
                        "Datei",
                        {"Dateiname": outname_rel, "NurInfo": "1"},
                    )

                if element["aufloesepunkt"]:
                    ET.SubElement(
                        ET.SubElement(
                            n_fahrstrasse,
                            "FahrstrTeilaufloesung",
                            {"Ref": str(get_ref_nr(elnr, 5))},
                        ),
                        "Datei",
                        {"Dateiname": outname_rel, "NurInfo": "1"},
                    )

                if elnr in fahrstrsignale:
                    ET.SubElement(
                        ET.SubElement(
                            n_fahrstrasse,
                            "FahrstrSignal",
                            {
                                "FahrstrSignalZeile": "1",
                                "Ref": str(
                                    get_ref_nr(elnr, RefTyp.SIGNAL_GEGENRICHTUNG)
                                ),
                            },
                        ),
                        "Datei",
                        {"Dateiname": outname_rel, "NurInfo": "1"},
                    )

                if elnr in signale:
                    sig = signale[elnr]
                    if True:  # if any(mz.vmax == 0 for mz in sig.matrix):
                        # TODO gibt es diese Unterscheidung auch in Zusi 2?
                        try:
                            startsig = signale[startnrs[-1]]
                        except KeyError:
                            startsig = None  # Aufgleispunkt

                        # Zielsignal verknüpfen
                        try:
                            zeile_v0 = next(
                                idx for idx, mz in enumerate(sig.matrix) if mz.vmax == 0
                            )
                        except StopIteration:
                            print(f"Signal ohne Zeile v=0", file=sys.stderr)
                            zeile_v0 = 0

                        ET.SubElement(
                            ET.SubElement(
                                n_fahrstrasse,
                                "FahrstrSignal",
                                {
                                    "FahrstrSignalZeile": str(zeile_v0),
                                    "Ref": str(get_ref_nr(elnr, 4)),
                                },
                            ),
                            "Datei",
                            {"Dateiname": outname_rel, "NurInfo": "1"},
                        )

                        # Startsignal und Vorsignale verknüpfen
                        if startsig is not None:
                            for idx, mz in enumerate(startsig.matrix):
                                if mz.block != sig.block or mz.gleis != sig.gleis:
                                    continue

                                ET.SubElement(
                                    ET.SubElement(
                                        n_fahrstrasse,
                                        "FahrstrSignal",
                                        {
                                            "FahrstrSignalZeile": str(idx),
                                            "Ref": str(get_ref_nr(startnrs[-1], 4)),
                                        },
                                    ),
                                    "Datei",
                                    {"Dateiname": outname_rel, "NurInfo": "1"},
                                )

                                # signalisierte Geschwindigkeit
                                hsig_geschw = None
                                ID = 0
                                for spalte, vsig_geschw in enumerate(
                                    startsig.vsig_geschw
                                ):
                                    if vsig_geschw == 0:
                                        hsig_geschw = (
                                            startsig.matrix[idx].spalten[spalte].vmax
                                        )
                                        ID = startsig.matrix[idx].spalten[spalte].id
                                        break
                                else:
                                    hsig_geschw = startsig.matrix[idx].spalten[0].vmax
                                    ID = startsig.matrix[idx].spalten[0].id

                                for vsig_nr in startsig.vsigs:
                                    try:
                                        vsig = signale[vsig_nr]
                                    except KeyError:
                                        try:
                                            vsig = anonymesignale[vsig_nr]
                                        except KeyError:
                                            print(
                                                f"Kein Vorsignal an Element {vsig_nr}"
                                            )
                                            continue

                                    ET.SubElement(
                                        ET.SubElement(
                                            n_fahrstrasse,
                                            "FahrstrVSignal",
                                            {
                                                "FahrstrSignalSpalte": str(
                                                    get_vsig_spalte(
                                                        vsig, hsig_geschw, ID
                                                    )
                                                ),
                                                "Ref": str(get_ref_nr(vsig_nr, 4)),
                                            },
                                        ),
                                        "Datei",
                                        {"Dateiname": outname_rel, "NurInfo": "1"},
                                    )
                                if hsig_geschw == 0:
                                    print(
                                        f" -> {sig.block} {sig.gleis}: vmax == 0 -> weiter",
                                        file=sys.stderr,
                                    )
                                    get_fahrstr_rek(
                                        startnrs + [elnr], elnr, n_fahrstrasse
                                    )
                                    return

                                break
                            else:
                                print(
                                    f"{startnrs[-1]}: keine zeile für Fahrweg nach {elnr} ({sig.block} {sig.gleis}) gefunden",
                                    file=sys.stderr,
                                )
                                return

                        ET.SubElement(
                            ET.SubElement(
                                n_fahrstrasse,
                                "FahrstrZiel",
                                {"Ref": str(get_ref_nr(elnr, 4))},
                            ),
                            "Datei",
                            {"Dateiname": outname_rel, "NurInfo": "1"},
                        )
                        fname = ""
                        for startnr in startnrs:
                            try:
                                startsig = signale[startnr]
                                fname += f"{startsig.block} {startsig.gleis} -> "
                            except KeyError:
                                fname += f"Aufgleispunkt -> "
                        fname += f"{sig.block} {sig.gleis}"
                        n_fahrstrasse.attrib["FahrstrName"] = fname

                        get_aufloesepunkte_rek(elnr, elnr, n_fahrstrasse)

                        n_fahrstrasse.attrib["FahrstrTyp"] = f"TypZug"
                        n_strecke.append(n_fahrstrasse)
                        print(f" -> {fname}", file=sys.stderr)
                        break

            succs = element["succ"]
            for idx, succ in enumerate(succs):
                if len(succs) == 1:
                    n_fahrstrasse2 = n_fahrstrasse
                else:
                    n_fahrstrasse2 = copy.deepcopy(n_fahrstrasse)

                succ_preds = elements[succ]["pred"]
                if len(succ_preds) > 1:
                    ET.SubElement(
                        ET.SubElement(
                            n_fahrstrasse2,
                            "FahrstrWeiche",
                            {
                                "FahrstrWeichenlage": str(succ_preds.index(elnr) + 1),
                                "Ref": str(
                                    get_ref_nr(succ, RefTyp.WEICHE_GEGENRICHTUNG)
                                ),
                            },
                        ),
                        "Datei",
                        {"Dateiname": outname_rel, "NurInfo": "1"},
                    )

                if len(succs) == 1:
                    elnr = succs[0]
                    break
                else:
                    ET.SubElement(
                        ET.SubElement(
                            n_fahrstrasse2,
                            "FahrstrWeiche",
                            {
                                "FahrstrWeichenlage": str(idx + 1),
                                "Ref": str(get_ref_nr(elnr, 3)),
                            },
                        ),
                        "Datei",
                        {"Dateiname": outname_rel, "NurInfo": "1"},
                    )
                    get_fahrstr_rek(startnrs, succ, n_fahrstrasse2)
            else:
                break

    for elnr, sig in signale.items():
        if any(mz.vmax == 0 for mz in sig.matrix):
            # Hsig
            print(f"{sig.block} {sig.gleis}", file=sys.stderr)
            n_fahrstrasse = ET.Element("Fahrstrasse")
            ET.SubElement(
                ET.SubElement(
                    n_fahrstrasse, "FahrstrStart", {"Ref": str(get_ref_nr(elnr, 4))}
                ),
                "Datei",
                {"Dateiname": outname_rel, "NurInfo": "1"},
            )
            get_fahrstr_rek([elnr], elnr, n_fahrstrasse)

    for elnr in aufgleispunkte.values():
        print(f"Aufgleispunkt {elnr}", file=sys.stderr)
        n_fahrstrasse = ET.Element("Fahrstrasse")
        ET.SubElement(
            ET.SubElement(
                n_fahrstrasse,
                "FahrstrStart",
                {"Ref": str(get_ref_nr(elnr, RefTyp.AUFGLEISPUNKT))},
            ),
            "Datei",
            {"Dateiname": outname_rel, "NurInfo": "1"},
        )
        get_fahrstr_rek([elnr], elnr, n_fahrstrasse)

    outname_abs = common.z3rel_to_abs(outname_rel)
    print(f"writing {outname_abs}", file=sys.stderr)
    os.makedirs(os.path.dirname(outname_abs), exist_ok=True)
    tree.write(outname_abs, encoding="unicode")
    print(f"done", file=sys.stderr)

    return (outname_rel, rekursionstiefe)
