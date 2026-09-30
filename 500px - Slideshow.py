"""Wrapper de compatibilidade para o antigo 500px - Slideshow.py.
Executa a nova engine modular do Slideshow Pro.
"""

import sys
from pathlib import Path

# Garante inclusão de src no caminho de busca
src_path = str(Path(__file__).resolve().parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from slideshow.cli import main

if __name__ == "__main__":
    main()