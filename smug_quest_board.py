#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backwards-compatible launcher for Smug Guild Board."""

import sys
from smug_guild_board import SmugGuildBoard, main

SmugQuestBoard = SmugGuildBoard
SakuraGuildBoard = SmugGuildBoard

if __name__ == "__main__":
    sys.exit(main())
