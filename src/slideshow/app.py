"""Módulo da interface gráfica principal do Slideshow em Tkinter."""

import os
import random
import time
import tkinter as tk
from tkinter import messagebox, simpledialog
from pathlib import Path
from typing import List, Optional, Dict, Any
from PIL import ImageTk, Image

from slideshow.vault import OneDriveVaultManager, diagnose_path
from slideshow.buffer import RAMImageBuffer, DEFAULT_RAM_LIMIT_MB
from slideshow.favorites import FavoritesManager
from slideshow.display import (
    FramingMode,
    TransitionMode,
    SortOrder,
    CaptionMode,
    prepare_canvas_image,
    blend_two_images,
    fade_to_black_image
)


class SlideshowApp:
    """Aplicação de apresentação de slides moderna e resiliente."""

    def __init__(
        self,
        root: tk.Tk,
        all_image_paths: List[str],
        delay_seconds: float = 3.0,
        framing_mode: FramingMode = FramingMode.FIT,
        transition_mode: TransitionMode = TransitionMode.CROSSFADE,
        sort_order: SortOrder = SortOrder.RANDOM,
        ram_limit_mb: int = DEFAULT_RAM_LIMIT_MB,
        is_vault: bool = False
    ):
        self.root = root
        self.raw_image_paths = list(all_image_paths)
        self.is_vault = is_vault
        self.delay_ms = int(delay_seconds * 1000)

        # Modos de exibição e controle
        self.framing_mode = framing_mode
        self.transition_mode = transition_mode
        self.sort_order = sort_order
        self.caption_mode = CaptionMode.NONE
        self.is_paused = False
        self.is_fullscreen = False
        self.is_always_on_top = False
        self.filter_only_favorites = False

        # Gerenciadores auxiliares
        self.buffer = RAMImageBuffer(ram_limit_mb=ram_limit_mb, is_vault=self.is_vault)
        self.favorites = FavoritesManager()

        # Estrutura de navegação e histórico infinito
        self.playlist: List[str] = []
        self.history: List[int] = []
        self.history_pos: int = -1

        # Estados de transição e animação
        self.current_pil_img: Optional[Image.Image] = None
        self.current_canvas_img: Optional[Image.Image] = None
        self.current_photo_tk: Optional[ImageTk.PhotoImage] = None
        self.scheduled_next = None
        self.pan_job = None
        self.transition_job = None
        self.pan_start_time = 0.0

        # Configuração da janela
        self.root.title("Slideshow Pro")
        self.root.configure(bg="black")
        self.root.attributes("-topmost", False)

        # Canvas principal de desenho para suporte a overlays e pans
        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Elementos visuais sobrepostos (overlays)
        self.caption_text_id = None
        self.toast_text_id = None
        self.toast_rect_id = None
        self.toast_timer = None

        # Previne suspensão do monitor pelo Windows durante a exibição
        OneDriveVaultManager.prevent_system_sleep()

        # Vinculação de eventos do teclado
        self._bind_shortcuts()

        # Inicializa a playlist de acordo com o modo de ordenação
        self._apply_sort_order(reset_history=True)

        # Pré-carregamento em RAM se for Vault
        if self.is_vault:
            self._preload_vault_images()

        # Inicia a exibição
        self.root.update_idletasks()
        self.next_slide(first_run=True)

    def _bind_shortcuts(self):
        """Configura os atalhos de teclado da aplicação."""
        self.root.bind("<F1>", self.toggle_help_window)
        self.root.bind("<F11>", self.toggle_fullscreen)
        self.root.bind("<Escape>", self.on_escape)
        self.root.bind("<space>", self.toggle_pause)
        self.root.bind("<Right>", lambda e: self.next_slide())
        self.root.bind("<Left>", lambda e: self.previous_slide())
        self.root.bind("<Up>", self.speed_up)
        self.root.bind("<Down>", self.speed_down)
        self.root.bind("<d>", self.prompt_custom_delay)
        self.root.bind("<D>", self.prompt_custom_delay)
        self.root.bind("<o>", self.cycle_sort_order)
        self.root.bind("<O>", self.cycle_sort_order)
        self.root.bind("<l>", self.toggle_like)
        self.root.bind("<L>", self.toggle_like)
        self.root.bind("<f>", self.toggle_filter_favorites)
        self.root.bind("<F>", self.toggle_filter_favorites)
        self.root.bind("<c>", self.cycle_caption)
        self.root.bind("<C>", self.cycle_caption)
        self.root.bind("<m>", self.cycle_framing_mode)
        self.root.bind("<M>", self.cycle_framing_mode)
        self.root.bind("<x>", self.cycle_transition_mode)
        self.root.bind("<X>", self.cycle_transition_mode)
        self.root.bind("<t>", self.toggle_topmost)
        self.root.bind("<T>", self.toggle_topmost)
        self.root.bind("<p>", self.toggle_topmost)
        self.root.bind("<P>", self.toggle_topmost)
        self.root.bind("<Configure>", self.on_window_resize)
        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)

    def _preload_vault_images(self):
        """Carrega fotos em RAM com barra de progresso caso estejam no Cofre Pessoal."""
        if not self.buffer.should_preload() or not self.raw_image_paths:
            return

        total = len(self.raw_image_paths)
        preload_win = tk.Toplevel(self.root)
        preload_win.title("Carregando Cofre Pessoal")
        preload_win.geometry("450x150")
        preload_win.configure(bg="#222")
        preload_win.resizable(False, False)
        preload_win.attributes("-topmost", True)

        lbl_info = tk.Label(
            preload_win,
            text="Detectado Cofre Pessoal do OneDrive.\nPré-carregando imagens na memória (Limite 1GB)...",
            bg="#222",
            fg="white",
            font=("Helvetica", 10)
        )
        lbl_info.pack(pady=10)

        lbl_progress = tk.Label(preload_win, text="Preparando...", bg="#222", fg="#aaa", font=("Helvetica", 9))
        lbl_progress.pack(pady=5)

        def on_progress(idx, tot, fname):
            if idx % 10 == 0 or idx == tot:
                lbl_progress.config(text=f"Carregando {idx}/{tot}: {fname[:35]}")
                preload_win.update()

        preload_win.update()
        loaded = self.buffer.preload_images(self.raw_image_paths, progress_callback=on_progress)
        preload_win.destroy()
        self.show_toast(f"Cofre: {loaded}/{total} fotos na RAM ({self.buffer.usage_mb:.1f} MB)", duration_ms=2500)

    def _apply_sort_order(self, reset_history: bool = True):
        """Reorganiza a lista ativa de exibição e reseta/ajusta o histórico de navegação."""
        base_paths = self.raw_image_paths

        if self.filter_only_favorites:
            base_paths = [p for p in base_paths if self.favorites.is_favorite(p)]
            if not base_paths:
                self.show_toast("Nenhuma foto favoritada nesta pasta!", duration_ms=2500)
                self.filter_only_favorites = False
                base_paths = self.raw_image_paths

        if self.sort_order == SortOrder.RANDOM:
            shuffled = list(base_paths)
            random.shuffle(shuffled)
            self.playlist = shuffled
        elif self.sort_order == SortOrder.DATE:
            def get_mtime(p):
                try:
                    return os.path.getmtime(p)
                except OSError:
                    return 0
            self.playlist = sorted(base_paths, key=get_mtime)
        elif self.sort_order == SortOrder.NAME:
            self.playlist = sorted(base_paths, key=lambda p: p.lower())

        if reset_history or not self.history:
            self.history = []
            self.history_pos = -1

    def get_current_image_path(self) -> Optional[str]:
        """Retorna o caminho do arquivo atualmente exibido."""
        if 0 <= self.history_pos < len(self.history):
            idx = self.history[self.history_pos]
            if 0 <= idx < len(self.playlist):
                return self.playlist[idx]
        return None

    def next_slide(self, first_run: bool = False):
        """Avança para o próximo slide com suporte a histórico infinito."""
        if not self.playlist:
            return

        self._cancel_scheduled_jobs()

        # Se estamos navegando no passado do histórico, avança um passo
        if self.history_pos < len(self.history) - 1:
            self.history_pos += 1
            playlist_idx = self.history[self.history_pos]
        else:
            # Caso contrário, pega o próximo item da playlist
            if not self.history:
                playlist_idx = 0
            else:
                last_idx = self.history[-1]
                playlist_idx = (last_idx + 1) % len(self.playlist)

            self.history.append(playlist_idx)
            self.history_pos = len(self.history) - 1

        self._render_current_slide(first_run=first_run)

    def previous_slide(self):
        """Retrocede no histórico de fotos exibidas (histórico infinito)."""
        if not self.playlist or len(self.history) <= 1 or self.history_pos <= 0:
            self.show_toast("Início do histórico", duration_ms=1000)
            return

        self._cancel_scheduled_jobs()
        self.history_pos -= 1
        self._render_current_slide()

    def _render_current_slide(self, first_run: bool = False):
        """Carrega e renderiza o slide atual com transições e suporte resiliente."""
        path = self.get_current_image_path()
        if not path:
            return

        # Carrega a imagem via buffer de memória ou disco
        new_pil = self.buffer.get_image(path)
        if new_pil is None:
            print(f"[Aviso] Pulando imagem inacessível: '{path}'")
            self.show_toast("Arquivo inacessível, pulando...", duration_ms=1500)
            self.next_slide()
            return

        win_w = self.canvas.winfo_width()
        win_h = self.canvas.winfo_height()
        if win_w <= 10 or win_h <= 10:
            win_w = self.root.winfo_width() or 1200
            win_h = self.root.winfo_height() or 800

        old_canvas_img = self.current_canvas_img
        new_canvas_img = prepare_canvas_image(new_pil, win_w, win_h, self.framing_mode, pan_progress=0.0)

        self.current_pil_img = new_pil
        self.current_canvas_img = new_canvas_img
        self.pan_start_time = time.time()

        # Decide o tipo de transição
        if first_run or self.transition_mode == TransitionMode.HARD or old_canvas_img is None:
            self._display_canvas_image(new_canvas_img)
            self._post_slide_render(path)
        elif self.transition_mode == TransitionMode.CROSSFADE:
            self._animate_crossfade(old_canvas_img, new_canvas_img, path, step=0, total_steps=8)
        elif self.transition_mode == TransitionMode.FADE_BLACK:
            self._animate_fade_black(old_canvas_img, new_canvas_img, path, step=0, total_steps=10)

    def _display_canvas_image(self, pil_img: Image.Image):
        """Converte a imagem PIL para PhotoImage e joga no Canvas."""
        self.current_photo_tk = ImageTk.PhotoImage(pil_img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.current_photo_tk)

    def _post_slide_render(self, path: str):
        """Finaliza renderização do slide: atualiza legendas e agenda próximo evento."""
        self._update_caption_overlay(path)

        # Se estiver no modo Panorâmico, inicia animação de pan contínuo
        if self.framing_mode == FramingMode.PANORAMIC and not self.is_paused:
            self._start_panoramic_tick()

        # Agenda o próximo slide
        if not self.is_paused:
            self.scheduled_next = self.root.after(self.delay_ms, self.next_slide)

    def _animate_crossfade(self, old_img: Image.Image, new_img: Image.Image, path: str, step: int, total_steps: int):
        """Executa interpolação gradual entre duas imagens (Crossfade)."""
        alpha = step / total_steps
        blended = blend_two_images(old_img, new_img, alpha)
        self._display_canvas_image(blended)

        if step < total_steps:
            self.transition_job = self.root.after(
                35,
                self._animate_crossfade,
                old_img,
                new_img,
                path,
                step + 1,
                total_steps
            )
        else:
            self._display_canvas_image(new_img)
            self._post_slide_render(path)

    def _animate_fade_black(self, old_img: Image.Image, new_img: Image.Image, path: str, step: int, total_steps: int):
        """Executa esmaecimento suave para o preto e retorno à nova imagem."""
        half = total_steps // 2
        if step <= half:
            p = step / half
            frame = fade_to_black_image(old_img, p)
        else:
            p = 1.0 - ((step - half) / half)
            frame = fade_to_black_image(new_img, p)

        self._display_canvas_image(frame)

        if step < total_steps:
            self.transition_job = self.root.after(
                35,
                self._animate_fade_black,
                old_img,
                new_img,
                path,
                step + 1,
                total_steps
            )
        else:
            self._display_canvas_image(new_img)
            self._post_slide_render(path)

    def _start_panoramic_tick(self):
        """Atualiza periodicamente o frame panorâmico (efeito Ken Burns)."""
        if self.framing_mode != FramingMode.PANORAMIC or self.is_paused:
            return

        elapsed = time.time() - self.pan_start_time
        progress = elapsed / (self.delay_ms / 1000.0)

        if progress <= 1.0 and self.current_pil_img:
            win_w = self.canvas.winfo_width()
            win_h = self.canvas.winfo_height()
            panned = prepare_canvas_image(self.current_pil_img, win_w, win_h, FramingMode.PANORAMIC, pan_progress=progress)
            self._display_canvas_image(panned)
            path = self.get_current_image_path()
            if path:
                self._update_caption_overlay(path)
            self.pan_job = self.root.after(40, self._start_panoramic_tick)

    def _cancel_scheduled_jobs(self):
        """Cancela timers ativos para evitar colisões durante transições."""
        if self.scheduled_next:
            self.root.after_cancel(self.scheduled_next)
            self.scheduled_next = None
        if self.pan_job:
            self.root.after_cancel(self.pan_job)
            self.pan_job = None
        if self.transition_job:
            self.root.after_cancel(self.transition_job)
            self.transition_job = None

    # --- Overlays e Notificações (Toast / Caption) ---

    def show_toast(self, message: str, duration_ms: int = 1500):
        """Exibe uma notificação visual elegante na parte inferior da tela."""
        if self.toast_timer:
            self.root.after_cancel(self.toast_timer)

        self.canvas.delete("toast")
        win_w = self.canvas.winfo_width()
        win_h = self.canvas.winfo_height()

        x = win_w // 2
        y = win_h - 45

        # Cria retângulo translúcido/escuro e texto
        padding_x = 20
        font = ("Helvetica", 11, "bold")
        text_id = self.canvas.create_text(x, y, text=message, fill="white", font=font, tags="toast")
        bbox = self.canvas.bbox(text_id)

        if bbox:
            rect_id = self.canvas.create_rectangle(
                bbox[0] - padding_x,
                bbox[1] - 6,
                bbox[2] + padding_x,
                bbox[3] + 6,
                fill="#111111",
                outline="#444444",
                width=1,
                tags="toast"
            )
            self.canvas.tag_raise(text_id, rect_id)

        self.toast_timer = self.root.after(duration_ms, lambda: self.canvas.delete("toast"))

    def _update_caption_overlay(self, path: str):
        """Atualiza a legenda do arquivo atual no topo da tela conforme o modo ativo."""
        self.canvas.delete("caption")
        if self.caption_mode == CaptionMode.NONE:
            return

        win_w = self.canvas.winfo_width()
        filename = os.path.basename(path)
        current_num = self.history_pos + 1
        total_num = len(self.playlist)

        is_fav = " ❤️" if self.favorites.is_favorite(path) else ""

        if self.caption_mode == CaptionMode.COMPACT:
            text = f"[{current_num}/{total_num}] {filename}{is_fav}"
        elif self.caption_mode == CaptionMode.DETAILED:
            res_str = f"{self.current_pil_img.size[0]}x{self.current_pil_img.size[1]}" if self.current_pil_img else ""
            parent_dir = os.path.basename(os.path.dirname(path))
            text = f"[{current_num}/{total_num}] {parent_dir}/{filename} ({res_str}){is_fav}"
        else:
            return

        x = win_w // 2
        y = 25
        padding_x = 15

        text_id = self.canvas.create_text(x, y, text=text, fill="#EEEEEE", font=("Helvetica", 10), tags="caption")
        bbox = self.canvas.bbox(text_id)
        if bbox:
            rect_id = self.canvas.create_rectangle(
                bbox[0] - padding_x,
                bbox[1] - 4,
                bbox[2] + padding_x,
                bbox[3] + 4,
                fill="#151515",
                outline="#333333",
                tags="caption"
            )
            self.canvas.tag_raise(text_id, rect_id)

    # --- Controles e Ações de Teclado ---

    def toggle_like(self, event=None):
        """Alterna o status de favorito (Like) e grava na planilha Excel."""
        path = self.get_current_image_path()
        if not path:
            return

        metadata = {}
        if self.current_pil_img:
            metadata["resolution"] = f"{self.current_pil_img.size[0]}x{self.current_pil_img.size[1]}"
        try:
            metadata["size_kb"] = round(os.path.getsize(path) / 1024, 2)
        except OSError:
            pass

        is_liked = self.favorites.toggle_favorite(path, metadata)
        if is_liked:
            self.show_toast("Favoritada! ❤️ Salva no Excel.", duration_ms=1800)
        else:
            self.show_toast("Descurtida! 🤍 Removida do Excel.", duration_ms=1800)

        self._update_caption_overlay(path)

    def toggle_filter_favorites(self, event=None):
        """Alterna o filtro para exibir apenas as fotos favoritas."""
        self.filter_only_favorites = not self.filter_only_favorites
        if self.filter_only_favorites:
            self.show_toast("Filtrando: Apenas Favoritas ❤️", duration_ms=1800)
        else:
            self.show_toast("Exibindo: Todas as Fotos", duration_ms=1800)

        self._apply_sort_order(reset_history=True)
        self.next_slide()

    def prompt_custom_delay(self, event=None):
        """Abre janela para digitação direta do tempo de transição em segundos."""
        self._cancel_scheduled_jobs()
        was_paused = self.is_paused
        self.is_paused = True

        current_sec = self.delay_ms / 1000.0
        val = simpledialog.askfloat(
            "Tempo de Transição",
            f"Digite o intervalo entre as fotos (em segundos):\n(Atual: {current_sec:.2f} s)",
            initialvalue=current_sec,
            minvalue=0.2,
            maxvalue=300.0,
            parent=self.root
        )

        if val is not None:
            self.delay_ms = int(val * 1000)
            self.show_toast(f"Novo intervalo: {val:.2f} segundos", duration_ms=2000)

        self.is_paused = was_paused
        if not self.is_paused:
            self.scheduled_next = self.root.after(self.delay_ms, self.next_slide)

    def cycle_sort_order(self, event=None):
        """Alterna o modo de ordenação em tempo de execução."""
        orders = [SortOrder.RANDOM, SortOrder.DATE, SortOrder.NAME]
        curr_idx = orders.index(self.sort_order)
        self.sort_order = orders[(curr_idx + 1) % len(orders)]
        self._apply_sort_order(reset_history=True)
        self.show_toast(f"Ordem: {self.sort_order.value}", duration_ms=2000)
        self.next_slide()

    def cycle_framing_mode(self, event=None):
        """Alterna o modo de enquadramento (Fit, Fill, Panorâmico)."""
        modes = [FramingMode.FIT, FramingMode.FILL, FramingMode.PANORAMIC]
        curr_idx = modes.index(self.framing_mode)
        self.framing_mode = modes[(curr_idx + 1) % len(modes)]
        self.show_toast(f"Enquadramento: {self.framing_mode.value}", duration_ms=2000)
        self._cancel_scheduled_jobs()
        self._render_current_slide()

    def cycle_transition_mode(self, event=None):
        """Alterna o modo de transição (Crossfade, Dura, Fade Preto)."""
        transitions = [TransitionMode.CROSSFADE, TransitionMode.HARD, TransitionMode.FADE_BLACK]
        curr_idx = transitions.index(self.transition_mode)
        self.transition_mode = transitions[(curr_idx + 1) % len(transitions)]
        self.show_toast(f"Transição: {self.transition_mode.value}", duration_ms=2000)

    def cycle_caption(self, event=None):
        """Alterna a exibição da legenda na tela."""
        modes = [CaptionMode.NONE, CaptionMode.COMPACT, CaptionMode.DETAILED]
        curr_idx = modes.index(self.caption_mode)
        self.caption_mode = modes[(curr_idx + 1) % len(modes)]
        self.show_toast(f"Legenda: {self.caption_mode.value}", duration_ms=1500)
        path = self.get_current_image_path()
        if path:
            self._update_caption_overlay(path)

    def toggle_fullscreen(self, event=None):
        """Alterna o modo de tela cheia com F11."""
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes("-fullscreen", self.is_fullscreen)
        self.show_toast("Tela Cheia: Ativada" if self.is_fullscreen else "Tela Cheia: Desativada", duration_ms=1200)

    def on_escape(self, event=None):
        """Se estiver em tela cheia sai dela; caso contrário fecha a aplicação."""
        if self.is_fullscreen:
            self.toggle_fullscreen()
        else:
            self.quit_app()

    def toggle_pause(self, event=None):
        """Pausa ou retoma a apresentação."""
        self.is_paused = not self.is_paused
        if self.is_paused:
            self._cancel_scheduled_jobs()
            self.show_toast("⏸ Apresentação Pausada", duration_ms=1500)
        else:
            self.show_toast("▶ Apresentação Retomada", duration_ms=1200)
            self.pan_start_time = time.time()
            if self.framing_mode == FramingMode.PANORAMIC:
                self._start_panoramic_tick()
            self.scheduled_next = self.root.after(self.delay_ms, self.next_slide)

    def speed_up(self, event=None):
        """Acelera o intervalo do slide."""
        if self.delay_ms > 400:
            self.delay_ms = max(int(self.delay_ms * 0.75), 400)
            self.show_toast(f"Velocidade: {self.delay_ms / 1000:.2f} s", duration_ms=1000)

    def speed_down(self, event=None):
        """Desacelera o intervalo do slide."""
        self.delay_ms = min(int(self.delay_ms * 1.35), 60000)
        self.show_toast(f"Velocidade: {self.delay_ms / 1000:.2f} s", duration_ms=1000)

    def toggle_topmost(self, event=None):
        """Alterna fixação da janela no topo."""
        self.is_always_on_top = not self.is_always_on_top
        self.root.attributes("-topmost", self.is_always_on_top)
        self.show_toast("Janela no Topo: Ativada" if self.is_always_on_top else "Janela no Topo: Desativada", duration_ms=1200)

    def on_window_resize(self, event):
        """Trata redimensionamento da janela recalculando o canvas."""
        if event.widget == self.root:
            if self.current_pil_img and not self.transition_job:
                self._cancel_scheduled_jobs()
                self._render_current_slide()

    def toggle_help_window(self, event=None):
        """Abre janela flutuante com a documentação de atalhos e funções."""
        help_win = tk.Toplevel(self.root)
        help_win.title("Atalhos e Ajuda do Slideshow")
        help_win.geometry("540x520")
        help_win.configure(bg="#1E1E1E")
        help_win.resizable(False, False)
        help_win.attributes("-topmost", True)

        title_lbl = tk.Label(
            help_win,
            text="Slideshow Pro - Atalhos de Teclado",
            bg="#1E1E1E",
            fg="#4FC3F7",
            font=("Helvetica", 14, "bold")
        )
        title_lbl.pack(pady=12)

        help_data = [
            ("F1", "Abrir / Fechar esta tela de ajuda"),
            ("F11", "Alternar Tela Cheia"),
            ("Espaço", "Pausar / Retomar apresentação"),
            ("Seta Esquerda", "Foto Anterior (Histórico Infinito)"),
            ("Seta Direita", "Próxima Foto"),
            ("Seta Cima / Baixo", "Acelerar / Desacelerar intervalo"),
            ("D", "Digitar intervalo de tempo personalizado"),
            ("O", "Alternar Ordem (Aleatória / Data / Alfabética)"),
            ("L", "Dar Like / Descurtir (salva em Excel)"),
            ("F", "Filtrar: Exibir apenas fotos Favoritas"),
            ("C", "Alternar Legenda (Oculta / Nome / Detalhada)"),
            ("M", "Modo Enquadramento (Ajustar / Zoom / Panorâmico)"),
            ("X", "Modo Transição (Suave Crossfade / Dura / Fade)"),
            ("T / P", "Alternar Janela sempre no Topo (Sempre Visível)"),
            ("Esc", "Sair da Tela Cheia ou Fechar programa"),
        ]

        frame_table = tk.Frame(help_win, bg="#2A2A2A", padx=10, pady=10)
        frame_table.pack(padx=20, pady=5, fill=tk.BOTH, expand=True)

        for row, (key, desc) in enumerate(help_data):
            lbl_key = tk.Label(
                frame_table,
                text=key,
                bg="#3A3A3A",
                fg="#FFD54F",
                font=("Helvetica", 9, "bold"),
                padx=8,
                pady=2,
                relief=tk.RIDGE
            )
            lbl_key.grid(row=row, column=0, padx=5, pady=2, sticky=tk.W)

            lbl_desc = tk.Label(
                frame_table,
                text=desc,
                bg="#2A2A2A",
                fg="#E0E0E0",
                font=("Helvetica", 9),
                padx=5
            )
            lbl_desc.grid(row=row, column=1, padx=5, pady=2, sticky=tk.W)

        btn_close = tk.Button(
            help_win,
            text="Fechar (Esc)",
            command=help_win.destroy,
            bg="#333",
            fg="white",
            relief=tk.FLAT,
            font=("Helvetica", 10, "bold"),
            padx=15,
            pady=4
        )
        btn_close.pack(pady=10)
        help_win.bind("<Escape>", lambda e: help_win.destroy())
        help_win.bind("<F1>", lambda e: help_win.destroy())

    def quit_app(self, event=None):
        """Finaliza a aplicação restaurando as configurações de energia."""
        self._cancel_scheduled_jobs()
        OneDriveVaultManager.restore_system_sleep()
        self.root.destroy()
