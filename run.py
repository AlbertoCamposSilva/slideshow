"""Script de inicialização direta para execução e compilação do executável."""

import sys
from pathlib import Path

# Adiciona o diretório 'src' ao sys.path para garantir importação em qualquer ambiente
src_path = str(Path(__file__).resolve().parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from slideshow.cli import main

if __name__ == "__main__":
    main()
