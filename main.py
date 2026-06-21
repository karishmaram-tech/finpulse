"""
FinPulse Intelligence Platform — Entrypoint
----------------------------------------------
Run with:  python main.py
This simply delegates to finpulse.core.app:main so the package
structure stays clean while still being runnable from the repo root.
"""

from finpulse.core.app import main

if __name__ == "__main__":
    main()
