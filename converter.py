#!/usr/bin/env python3
"""
ArcCW to ARC9 Converter
CLI & GUI runner script
"""
import sys

if __name__ == "__main__":
    if len(sys.argv) == 1 or "--gui" in sys.argv:
        from arccw_to_arc9.gui import launch_gui
        launch_gui()
    else:
        from arccw_to_arc9.cli import main
        main()
