"""Script de automação de compilação do executável com Nuitka e PyInstaller."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
ENTRY_POINT = ROOT_DIR / "run.py"
DIST_DIR = ROOT_DIR / "dist"


def run_command(cmd, desc):
    print(f"\n==================================================")
    print(f"[{desc}] Executando: {' '.join(cmd)}")
    print(f"==================================================\n")
    res = subprocess.run(cmd, cwd=str(ROOT_DIR))
    if res.returncode != 0:
        print(f"\n[ERRO] Falha ao executar: {desc} (Código {res.returncode})")
        sys.exit(res.returncode)
    print(f"\n[SUCESSO] {desc} concluído com sucesso!")


def clean_artifacts():
    print("[Limpeza] Removendo pastas de compilação temporárias...")
    dirs_to_clean = [
        ROOT_DIR / "build",
        ROOT_DIR / "run.build",
        ROOT_DIR / "run.dist",
        ROOT_DIR / "run.onefile-build",
        ROOT_DIR / "Slideshow.build",
        ROOT_DIR / "Slideshow.dist",
        ROOT_DIR / "Slideshow.onefile-build",
    ]
    for d in dirs_to_clean:
        if d.exists() and d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
            print(f" - Removido: {d.name}")


def build_nuitka():
    clean_artifacts()
    DIST_DIR.mkdir(exist_ok=True)
    icon_path = ROOT_DIR / "src" / "slideshow" / "assets" / "icon.ico"

    # Parâmetros otimizados do Nuitka para Tkinter, Pillow e openpyxl no Windows
    cmd = [
        sys.executable,
        "-m", "nuitka",
        "--onefile",
        "--windows-console-mode=disable",
        "--enable-plugin=tk-inter",
        "--include-package=slideshow",
        "--include-package-data=slideshow",
        "--include-package=PIL",
        "--include-package=openpyxl",
        "--assume-yes-for-downloads",
        f"--output-dir={DIST_DIR}",
        "--output-filename=Slideshow-Nuitka.exe",
    ]
    # Localiza pasta Tcl para garantir empacotamento sem erros no Windows
    prefix = Path(sys.base_prefix)
    tcl_cand = prefix / "tcl"
    tcl_dir = None
    if tcl_cand.exists():
        for sub in tcl_cand.iterdir():
            if sub.is_dir() and sub.name.lower().startswith("tcl"):
                tcl_dir = str(sub)
                break

    if tcl_dir:
        cmd.append(f"--tcl-library-dir={tcl_dir}")

    if icon_path.exists():
        cmd.append(f"--windows-icon-from-ico={icon_path}")

    cmd.append(str(ENTRY_POINT))
    run_command(cmd, "Compilação com Nuitka")
    print(f"\nExecutável gerado em: {DIST_DIR / 'Slideshow-Nuitka.exe'}")


def build_pyinstaller():
    clean_artifacts()
    DIST_DIR.mkdir(exist_ok=True)
    icon_path = ROOT_DIR / "src" / "slideshow" / "assets" / "icon.ico"

    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--clean",
        "--name", "Slideshow-PyInstaller",
        f"--distpath={DIST_DIR}",
        f"--paths={ROOT_DIR / 'src'}",
        "--collect-all", "slideshow",
        "--collect-all", "PIL",
        "--collect-all", "openpyxl",
    ]
    if icon_path.exists():
        cmd.append(f"--icon={icon_path}")

    cmd.append(str(ENTRY_POINT))
    run_command(cmd, "Compilação com PyInstaller")
    print(f"\nExecutável gerado em: {DIST_DIR / 'Slideshow-PyInstaller.exe'}")


def main():
    parser = argparse.ArgumentParser(description="Automação de compilação do Slideshow Pro")
    parser.add_argument("--nuitka", action="store_true", help="Compilar executável usando Nuitka (Preferencial)")
    parser.add_argument("--pyinstaller", action="store_true", help="Compilar executável usando PyInstaller")
    parser.add_argument("--all", action="store_true", help="Compilar ambas as versões (Nuitka e PyInstaller)")
    parser.add_argument("--clean", action="store_true", help="Apenas limpar arquivos e pastas temporárias de build")

    args = parser.parse_args()

    if args.clean:
        clean_artifacts()
        return

    if args.all:
        build_nuitka()
        build_pyinstaller()
    elif args.nuitka:
        build_nuitka()
    elif args.pyinstaller:
        build_pyinstaller()
    else:
        # Padrão: compilar preferencialmente com Nuitka
        print("Nenhuma opção especificada. Utilizando Nuitka por padrão.")
        build_nuitka()


if __name__ == "__main__":
    main()
