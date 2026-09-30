# Guia de Compilação de Executáveis (.exe)

O **Slideshow Pro** oferece suporte completo e automatizado para geração de executáveis para Windows tanto pelo **Nuitka** (método preferencial, gera código C nativo otimizado e mais rápido) quanto pelo **PyInstaller** (método tradicional).

---

## 🛠️ Por que o Nuitka falhava anteriormente?

Ao compilar aplicações Tkinter e Pillow no Windows, o Nuitka requer flags específicas que frequentemente causam erros se omitidas:
1. **Falta do plugin Tkinter** (`--enable-plugin=tk-inter`): Sem este plugin, o Nuitka não empacota os arquivos de suporte `init.tcl`, bibliotecas Tcl/Tk e DLLs, resultando em erro `TclError: Can't find a usable init.tcl` ao abrir o executável.
2. **Empacotamento de pacotes dinâmicos** (`--include-package=PIL`, `--include-package=openpyxl`, `--include-package=slideshow`): Pillow e openpyxl carregam submódulos dinamicamente que precisam ser incluídos explicitamente.
3. **Ausência de compilador C no Windows**: O Nuitka compila Python para C e precisa de um compilador (MSVC ou MinGW64). Com a flag `--assume-yes-for-downloads`, o Nuitka baixa e configura automaticamente o MinGW64 oficial sem requerer nenhuma intervenção manual.
4. **Modo sem console para GUI**: `--windows-console-mode=disable` oculta a janela preta de terminal do DOS.

Todos esses parâmetros já foram integrados e automatizados no [`build.py`](build.py).

---

## 🚀 Como Compilar

### Opção 1: Via Scripts `.bat` (Um Clique)

- Para compilar com **Nuitka** (Preferencial):
  Basta dar um duplo-clique no arquivo:
  `build_nuitka.bat`

- Para compilar com **PyInstaller**:
  Basta dar um duplo-clique no arquivo:
  `build_pyinstaller.bat`

---

### Opção 2: Via Terminal com `uv`

Com o `uv` instalado, execute no terminal:

```bash
# Compilação preferencial com Nuitka
uv run --with nuitka --with zstandard python build.py --nuitka

# Compilação com PyInstaller
uv run --with pyinstaller python build.py --pyinstaller

# Compilar ambos
uv run --with nuitka --with pyinstaller --with zstandard python build.py --all

# Limpar artefatos temporários de compilação
uv run python build.py --clean
```

---

## 📂 Onde encontrar os executáveis gerados?

Após a compilação, os arquivos `.exe` estarão disponíveis na pasta:
- `dist/Slideshow-Nuitka.exe`
- `dist/Slideshow-PyInstaller.exe`

Os executáveis são autônomos (*standalone onefile*) e podem ser transportados para qualquer computador com Windows sem necessidade de ter o Python ou o `uv` instalados.
