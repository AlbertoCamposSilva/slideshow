"""Módulo para gerenciamento de curtidas (Likes/Favoritos) salvas em planilha Excel (.xlsx)."""

import os
from datetime import datetime
from pathlib import Path
from typing import Set, Optional, Dict, Any
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment


DEFAULT_FAVORITES_FILE = Path.home() / "slideshow_favoritos.xlsx"


class FavoritesManager:
    """Gerencia a leitura, adição e remoção de favoritos em uma planilha Excel."""

    def __init__(self, excel_path: Optional[Path] = None):
        self.excel_path = Path(excel_path) if excel_path else DEFAULT_FAVORITES_FILE
        self._favorites: Set[str] = set()
        self._load()

    def _normalize_path(self, path: str) -> str:
        """Normaliza caminho para comparação exata (insensível a maiúsculas no Windows)."""
        return os.path.normcase(os.path.abspath(path))

    def _ensure_file_exists(self):
        """Cria o arquivo Excel com cabeçalhos formatados caso ainda não exista."""
        if self.excel_path.exists():
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Favoritos"

        headers = [
            "Caminho Completo",
            "Nome do Arquivo",
            "Data/Hora do Like",
            "Resolução",
            "Tamanho (KB)",
            "Pasta de Origem"
        ]
        ws.append(headers)

        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
        center_align = Alignment(horizontal="center", vertical="center")

        for col_num, _ in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align

        # Ajuste de larguras de coluna
        col_widths = {1: 60, 2: 30, 3: 20, 4: 15, 5: 15, 6: 45}
        for col_num, width in col_widths.items():
            col_letter = openpyxl.utils.get_column_letter(col_num)
            ws.column_dimensions[col_letter].width = width

        self.excel_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(self.excel_path)

    def _load(self):
        """Carrega todos os caminhos favoritados do arquivo Excel."""
        self._favorites.clear()
        if not self.excel_path.exists():
            return

        try:
            wb = openpyxl.load_workbook(self.excel_path, read_only=True)
            ws = wb.active
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row and row[0]:
                    norm_path = self._normalize_path(str(row[0]))
                    self._favorites.add(norm_path)
            wb.close()
        except Exception as e:
            print(f"[Favoritos] Erro ao carregar planilha '{self.excel_path}': {e}")

    def is_favorite(self, path: str) -> bool:
        """Verifica se o arquivo já está favoritado."""
        return self._normalize_path(path) in self._favorites

    def add_favorite(self, path: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Adiciona a imagem aos favoritos caso ainda não esteja presente.
        Retorna True se foi adicionada, ou False se já constava nos favoritos.
        """
        norm_path = self._normalize_path(path)
        if norm_path in self._favorites:
            return False
        self._add_favorite(path, norm_path, metadata)
        return True

    def remove_favorite(self, path: str) -> bool:
        """
        Remove a imagem dos favoritos caso esteja presente.
        Retorna True se foi removida, ou False se não estava nos favoritos.
        """
        norm_path = self._normalize_path(path)
        if norm_path not in self._favorites:
            return False
        self._remove_favorite(path, norm_path)
        return True

    def toggle_favorite(self, path: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Alterna o estado de favorito da imagem.
        Retorna True se foi adicionado aos favoritos, ou False se foi removido.
        """
        norm_path = self._normalize_path(path)
        if norm_path in self._favorites:
            self._remove_favorite(path, norm_path)
            return False
        else:
            self._add_favorite(path, norm_path, metadata)
            return True

    def _add_favorite(self, raw_path: str, norm_path: str, metadata: Optional[Dict[str, Any]] = None):
        """Adiciona uma nova linha com os dados da foto na planilha Excel."""
        self._ensure_file_exists()

        try:
            wb = openpyxl.load_workbook(self.excel_path)
            ws = wb.active

            filename = os.path.basename(raw_path)
            folder = os.path.dirname(raw_path)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            resolution = ""
            size_kb = 0.0

            if metadata:
                resolution = metadata.get("resolution", "")
                size_kb = metadata.get("size_kb", 0.0)
            else:
                try:
                    size_kb = round(os.path.getsize(raw_path) / 1024, 2)
                except OSError:
                    pass

            row_data = [raw_path, filename, now_str, resolution, size_kb, folder]
            ws.append(row_data)
            wb.save(self.excel_path)

            self._favorites.add(norm_path)
            print(f"[Favoritos] Foto favoritada: {filename}")
        except Exception as e:
            print(f"[Favoritos] Erro ao salvar like em '{self.excel_path}': {e}")

    def _remove_favorite(self, raw_path: str, norm_path: str):
        """Remove a linha correspondente à foto do arquivo Excel."""
        if not self.excel_path.exists():
            self._favorites.discard(norm_path)
            return

        try:
            wb = openpyxl.load_workbook(self.excel_path)
            ws = wb.active

            row_to_delete = None
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                if row and row[0] and self._normalize_path(str(row[0])) == norm_path:
                    row_to_delete = row_idx
                    break

            if row_to_delete:
                ws.delete_rows(row_to_delete, 1)
                wb.save(self.excel_path)

            self._favorites.discard(norm_path)
            print(f"[Favoritos] Like removido: {os.path.basename(raw_path)}")
        except Exception as e:
            print(f"[Favoritos] Erro ao remover like de '{self.excel_path}': {e}")

    @property
    def favorites_count(self) -> int:
        """Total de fotos favoritadas."""
        return len(self._favorites)
