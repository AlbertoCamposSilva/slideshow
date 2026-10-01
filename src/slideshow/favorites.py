"""Módulo para gerenciamento de curtidas (Likes/Favoritos) salvas em planilha Excel (.xlsx)."""

import os
from datetime import datetime
from pathlib import Path
from typing import Set, Optional, Dict, Any
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment


DEFAULT_FAVORITES_FILE = Path.home() / "slideshow_favoritos.xlsx"


class FavoritesManager:
    """Gerencia favoritos, unlikes e configurações persistentes em uma planilha Excel."""

    def __init__(self, excel_path: Optional[Path] = None):
        self.excel_path = Path(excel_path) if excel_path else DEFAULT_FAVORITES_FILE
        self._favorites: Set[str] = set()
        self._unlikes: Set[str] = set()
        self._load()

    def _normalize_path(self, path: str) -> str:
        """Normaliza caminho para comparação exata (insensível a maiúsculas no Windows)."""
        return os.path.normcase(os.path.abspath(path))

    def _setup_sheet_headers(self, ws, title: str, header_color: str):
        """Configura os cabeçalhos padrão para abas de Favoritos ou Unlikes."""
        ws.title = title
        headers = [
            "Caminho Completo",
            "Nome do Arquivo",
            "Data/Hora",
            "Resolução",
            "Tamanho (KB)",
            "Pasta de Origem"
        ]
        ws.append(headers)

        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color=header_color, end_color=header_color, fill_type="solid")
        center_align = Alignment(horizontal="center", vertical="center")

        for col_num, _ in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align

        col_widths = {1: 60, 2: 30, 3: 20, 4: 15, 5: 15, 6: 45}
        for col_num, width in col_widths.items():
            col_letter = openpyxl.utils.get_column_letter(col_num)
            ws.column_dimensions[col_letter].width = width

    def _ensure_file_exists(self):
        """Garante que a planilha exista com as abas Favoritos, Unlikes e Configuracoes."""
        if self.excel_path.exists():
            return

        wb = openpyxl.Workbook()
        # 1. Aba Favoritos
        ws_fav = wb.active
        self._setup_sheet_headers(ws_fav, "Favoritos", "2F5597")

        # 2. Aba Unlikes
        ws_unl = wb.create_sheet("Unlikes")
        self._setup_sheet_headers(ws_unl, "Unlikes", "C00000")

        # 3. Aba Configuracoes
        ws_cfg = wb.create_sheet("Configuracoes")
        ws_cfg.append(["Chave", "Valor", "Ultima_Atualizacao"])
        cfg_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        cfg_fill = PatternFill(start_color="375623", end_color="375623", fill_type="solid")
        for col_idx in (1, 2, 3):
            c = ws_cfg.cell(row=1, column=col_idx)
            c.font = cfg_font
            c.fill = cfg_fill
            c.alignment = Alignment(horizontal="center", vertical="center")
        ws_cfg.column_dimensions["A"].width = 25
        ws_cfg.column_dimensions["B"].width = 30
        ws_cfg.column_dimensions["C"].width = 22

        self.excel_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(self.excel_path)

    def _load(self):
        """Carrega caminhos favoritados e unliked da planilha Excel."""
        self._favorites.clear()
        self._unlikes.clear()
        if not self.excel_path.exists():
            return

        try:
            wb = openpyxl.load_workbook(self.excel_path, read_only=True)
            if "Favoritos" in wb.sheetnames:
                ws = wb["Favoritos"]
                for row in ws.iter_rows(min_row=2, values_only=True):
                    if row and row[0]:
                        self._favorites.add(self._normalize_path(str(row[0])))

            if "Unlikes" in wb.sheetnames:
                ws_unl = wb["Unlikes"]
                for row in ws_unl.iter_rows(min_row=2, values_only=True):
                    if row and row[0]:
                        self._unlikes.add(self._normalize_path(str(row[0])))

            wb.close()
        except Exception as e:
            print(f"[Favoritos] Erro ao carregar planilha '{self.excel_path}': {e}")

    # --- Métodos de Favoritos (Likes) ---

    def is_favorite(self, path: str) -> bool:
        """Verifica se o arquivo está favoritado."""
        return self._normalize_path(path) in self._favorites

    def add_favorite(self, path: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Adiciona aos favoritos e remove de unlikes se presente."""
        norm_path = self._normalize_path(path)
        if norm_path in self._favorites:
            return False

        if norm_path in self._unlikes:
            self.remove_unlike(path)

        self._append_row("Favoritos", path, norm_path, metadata)
        self._favorites.add(norm_path)
        return True

    def remove_favorite(self, path: str) -> bool:
        """Remove a imagem dos favoritos."""
        norm_path = self._normalize_path(path)
        if norm_path not in self._favorites:
            return False
        self._delete_row("Favoritos", path, norm_path)
        self._favorites.discard(norm_path)
        return True

    # --- Métodos de Unlikes (Dislikes) ---

    def is_unliked(self, path: str) -> bool:
        """Verifica se o arquivo está marcado com unlike."""
        return self._normalize_path(path) in self._unlikes

    def add_unlike(self, path: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Adiciona aos unlikes e remove de favoritos se presente."""
        norm_path = self._normalize_path(path)
        if norm_path in self._unlikes:
            return False

        if norm_path in self._favorites:
            self.remove_favorite(path)

        self._append_row("Unlikes", path, norm_path, metadata)
        self._unlikes.add(norm_path)
        return True

    def remove_unlike(self, path: str) -> bool:
        """Remove a imagem dos unlikes."""
        norm_path = self._normalize_path(path)
        if norm_path not in self._unlikes:
            return False
        self._delete_row("Unlikes", path, norm_path)
        self._unlikes.discard(norm_path)
        return True

    # --- Métodos Genéricos de Manipulação de Planilha ---

    def _append_row(self, sheet_name: str, raw_path: str, norm_path: str, metadata: Optional[Dict[str, Any]] = None):
        """Adiciona uma linha formatada à aba especificada."""
        self._ensure_file_exists()
        try:
            wb = openpyxl.load_workbook(self.excel_path)
            if sheet_name not in wb.sheetnames:
                ws = wb.create_sheet(sheet_name)
                color = "C00000" if sheet_name == "Unlikes" else "2F5597"
                self._setup_sheet_headers(ws, sheet_name, color)
            else:
                ws = wb[sheet_name]

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
        except Exception as e:
            print(f"[Favoritos] Erro ao adicionar linha em '{sheet_name}' na planilha: {e}")

    def _delete_row(self, sheet_name: str, raw_path: str, norm_path: str):
        """Remove uma linha da aba correspondente."""
        if not self.excel_path.exists():
            return

        try:
            wb = openpyxl.load_workbook(self.excel_path)
            if sheet_name not in wb.sheetnames:
                return
            ws = wb[sheet_name]

            row_to_delete = None
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                if row and row[0] and self._normalize_path(str(row[0])) == norm_path:
                    row_to_delete = row_idx
                    break

            if row_to_delete:
                ws.delete_rows(row_to_delete, 1)
                wb.save(self.excel_path)
        except Exception as e:
            print(f"[Favoritos] Erro ao remover linha de '{sheet_name}' na planilha: {e}")

    # --- Persistência de Configurações ---

    def load_config(self) -> Dict[str, Any]:
        """Carrega o dicionário de configurações salvas no Excel."""
        config: Dict[str, Any] = {}
        if not self.excel_path.exists():
            return config

        try:
            wb = openpyxl.load_workbook(self.excel_path, read_only=True)
            if "Configuracoes" in wb.sheetnames:
                ws = wb["Configuracoes"]
                for row in ws.iter_rows(min_row=2, values_only=True):
                    if row and row[0] is not None:
                        key = str(row[0]).strip()
                        val = row[1]
                        config[key] = val
            wb.close()
        except Exception as e:
            print(f"[Config] Erro ao carregar configurações de '{self.excel_path}': {e}")
        return config

    def save_config(self, config_dict: Dict[str, Any]):
        """Salva ou atualiza pares chave-valor na aba 'Configuracoes' do Excel."""
        self._ensure_file_exists()
        try:
            wb = openpyxl.load_workbook(self.excel_path)
            if "Configuracoes" not in wb.sheetnames:
                ws = wb.create_sheet("Configuracoes")
                ws.append(["Chave", "Valor", "Ultima_Atualizacao"])
                cfg_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
                cfg_fill = PatternFill(start_color="375623", end_color="375623", fill_type="solid")
                for col_idx in (1, 2, 3):
                    c = ws.cell(row=1, column=col_idx)
                    c.font = cfg_font
                    c.fill = cfg_fill
                    c.alignment = Alignment(horizontal="center", vertical="center")
            else:
                ws = wb["Configuracoes"]

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Mapeia linhas existentes por chave
            existing_keys: Dict[str, int] = {}
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                if row and row[0] is not None:
                    existing_keys[str(row[0]).strip()] = row_idx

            for key, val in config_dict.items():
                str_key = str(key).strip()
                if str_key in existing_keys:
                    row_idx = existing_keys[str_key]
                    ws.cell(row=row_idx, column=2, value=str(val))
                    ws.cell(row=row_idx, column=3, value=now_str)
                else:
                    ws.append([str_key, str(val), now_str])

            wb.save(self.excel_path)
        except Exception as e:
            print(f"[Config] Erro ao salvar configurações em '{self.excel_path}': {e}")

    @property
    def favorites_count(self) -> int:
        """Total de fotos favoritadas."""
        return len(self._favorites)

    @property
    def unlikes_count(self) -> int:
        """Total de fotos unliked."""
        return len(self._unlikes)
