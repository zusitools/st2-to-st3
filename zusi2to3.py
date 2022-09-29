#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

from zusi2to3 import strecke, fahrplan

(st3_name, rekursionstiefe) = strecke.conv_str(sys.argv[1])
for fpnname in sys.argv[2:]:
    fahrplan.conv_fpn(fpnname, st3_name, rekursionstiefe)
