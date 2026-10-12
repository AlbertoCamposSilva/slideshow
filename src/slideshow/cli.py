"""Interface de linha de comando (CLI) para o Slideshow."""

import argparse
import sys
from pathlib import Path
from slideshow.core import run_slideshow
from slideshow.vault import diagnose_path, main_diag


def main():
    parser = argparse.ArgumentParser(
        prog="slideshow",
        description="Slideshow Pro - Visualizador de fotos resiliente, moderno e com suporte a OneDrive Personal Vault."
    )
    parser.add_argument(
        "-p", "--path",
        dest="folder",
        type=str,
        default=None,
        help="Caminho para o diretório de imagens. Se omitido, abre o seletor gráfico."
    )
    parser.add_argument(
        "-d", "--delay",
        dest="delay",
        type=float,
        default=3.0,
        help="Intervalo em segundos entre cada foto (padrão: 3.0)."
    )
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="Inicia a apresentação diretamente em tela cheia."
    )
    parser.add_argument(
        "-m", "--framing",
        dest="framing",
        choices=["fit", "fill", "panoramic"],
        default="fit",
        help="Modo de enquadramento: 'fit' (ajustar), 'fill' (zoom central), 'panoramic' (Ken Burns pan)."
    )
    parser.add_argument(
        "-t", "--transition",
        dest="transition",
        choices=["crossfade", "hard", "fade_black"],
        default="crossfade",
        help="Estilo de transição: 'crossfade' (suave), 'hard' (corte seco), 'fade_black' (esmaecer)."
    )
    parser.add_argument(
        "-o", "--order",
        dest="order",
        choices=["random", "date", "name"],
        default="random",
        help="Ordem das fotos: 'random' (aleatória), 'date' (data), 'name' (alfabética por arquivo)."
    )
    parser.add_argument(
        "--ram-limit",
        dest="ram_limit_mb",
        type=int,
        default=1024,
        help="Limite de memória RAM em MB para cache de fotos do Cofre (padrão: 1024 MB)."
    )
    parser.add_argument(
        "--check-vault",
        action="store_true",
        help="Executa rotina rápida de diagnóstico de caminho e Cofre Pessoal e encerra."
    )
    parser.add_argument(
        "--export-favorites",
        dest="export_xlsx",
        metavar="ARQUIVO.xlsx",
        default=None,
        help="Exporta favoritos, unlikes e configurações para uma planilha Excel e encerra."
    )
    parser.add_argument(
        "--import-favorites",
        dest="import_xlsx",
        metavar="ARQUIVO.xlsx",
        default=None,
        help="Importa uma planilha Excel SUBSTITUINDO todo o conteúdo do banco e encerra."
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version="Slideshow Pro 1.3.0"
    )

    args = parser.parse_args()

    if args.export_xlsx or args.import_xlsx:
        from slideshow.favorites import FavoritesManager
        fav = FavoritesManager()
        try:
            if args.export_xlsx:
                likes, unlikes = fav.export_xlsx(Path(args.export_xlsx))
                print(f"Exportado para '{args.export_xlsx}': {likes} favoritos, {unlikes} unlikes.")
            if args.import_xlsx:
                likes, unlikes = fav.import_xlsx(Path(args.import_xlsx))
                print(f"Importado de '{args.import_xlsx}': {likes} favoritos, {unlikes} unlikes.")
        except Exception as e:
            print(f"[Erro] {e}")
            sys.exit(1)
        sys.exit(0)

    if args.check_vault:
        default_vault = str(Path.home() / "OneDrive" / "Cofre Pessoal" / "Outras Imagens")
        target = args.folder or default_vault
        print(f"\n[Diagnóstico] Verificando: {target}")
        diag = diagnose_path(target)
        for k, v in diag.items():
            if k != "advice":
                print(f"  {k}: {v}")
        if diag["advice"]:
            print("\nRecomendações:")
            for a in diag["advice"]:
                print(f"  * {a}")
        sys.exit(0)

    run_slideshow(
        folder=args.folder,
        delay=args.delay,
        fullscreen=args.fullscreen,
        framing=args.framing,
        transition=args.transition,
        order=args.order,
        ram_limit_mb=args.ram_limit_mb
    )


if __name__ == "__main__":
    main()
