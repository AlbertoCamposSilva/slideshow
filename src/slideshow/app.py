import os
import sys
import ctypes
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
    pre_scale_panoramic,
    crop_panoramic_frame,
    blend_two_images,
    fade_to_black_image
)

# Pausa de assentamento (ms) após a transição terminar antes de iniciar o movimento panorâmico
SETTLE_PAUSE_MS = 350


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
        self.filter_mode: str = "ALL"  # "ALL", "FAVORITES", "UNLIKES"
        self.enhancement_enabled = True
        self.show_status_icons = True
        self.help_window: Optional[tk.Toplevel] = None

        # Gerenciadores auxiliares
        self.buffer = RAMImageBuffer(ram_limit_mb=ram_limit_mb, is_vault=self.is_vault)
        self.favorites = FavoritesManager()

        # Carrega configurações previamente salvas na planilha do usuário
        self._load_saved_config()

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
        self.settle_job = None
        self.transition_job = None
        self.pan_start_time = 0.0
        self.pan_duration_sec = max(1.0, self.delay_ms / 1000.0)

        # Cache de imagem pré-escalada para modo Panorâmico a 60 FPS
        self.pan_scaled_img: Optional[Image.Image] = None
        self.pan_max_dx: int = 0
        self.pan_max_dy: int = 0

        # Configura AppUserModelID no Windows para garantir ícone exclusivo na barra de tarefas
        if sys.platform == "win32":
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Antigravity.Slideshow.Pro.Viewer.1.0")
            except Exception:
                pass

        # Configuração da janela
        self.root.title("Slideshow Pro")
        self.root.configure(bg="black")
        if self.is_always_on_top:
            self.root.attributes("-topmost", True)
        if self.is_fullscreen:
            self.root.attributes("-fullscreen", True)

        # Carrega o ícone oficial da aplicação
        self._load_app_icon()

        # Canvas principal de desenho para suporte a overlays e pans
        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Item gráfico de imagem persistente para evitar flicker e recriação
        self.canvas_img_id = self.canvas.create_image(0, 0, anchor=tk.NW)

        # Elementos visuais sobrepostos (overlays)
        self.caption_text_id = None
        self.status_icon_id = None
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
        self.root.bind("<l>", self.add_like)
        self.root.bind("<L>", self.add_like)
        self.root.bind("<u>", self.remove_like)
        self.root.bind("<U>", self.remove_like)
        self.root.bind("<f>", self.toggle_filter)
        self.root.bind("<F>", self.toggle_filter)
        self.root.bind("<i>", self.toggle_status_icons)
        self.root.bind("<I>", self.toggle_status_icons)
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
        self.root.bind("<e>", self.toggle_enhancement)
        self.root.bind("<E>", self.toggle_enhancement)
        self.root.bind("<Delete>", self.handle_delete_action)
        self.root.bind("<Shift-Delete>", self.delete_all_unlikes)
        self.root.bind("<Configure>", self.on_window_resize)
        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)

    def _load_app_icon(self):
        """Carrega e define o ícone do programa na barra de tarefas e título do Windows."""
        assets_dir = Path(__file__).resolve().parent / "assets"
        ico_file = assets_dir / "icon.ico"
        png_file = assets_dir / "icon.png"

        if png_file.exists():
            try:
                self._icon_photo = ImageTk.PhotoImage(file=str(png_file))
                self.root.iconphoto(True, self._icon_photo)
            except Exception as e:
                print(f"[Icon] Erro ao carregar iconphoto: {e}")

        if sys.platform == "win32" and ico_file.exists():
            try:
                self.root.iconbitmap(str(ico_file))
            except Exception as e:
                print(f"[Icon] Erro ao carregar iconbitmap: {e}")

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

    def _load_saved_config(self):
        """Carrega e aplica as configurações salvas na aba 'Configuracoes' do Excel."""
        cfg = self.favorites.load_config()
        if not cfg:
            return

        if "delay_seconds" in cfg:
            try:
                self.delay_ms = max(200, int(float(cfg["delay_seconds"]) * 1000))
            except (ValueError, TypeError):
                pass

        if "framing_mode" in cfg:
            val = str(cfg["framing_mode"]).strip().lower()
            for m in FramingMode:
                if m.name.lower() == val or m.value.lower() == val:
                    self.framing_mode = m
                    break

        if "transition_mode" in cfg:
            val = str(cfg["transition_mode"]).strip().lower()
            for t in TransitionMode:
                if t.name.lower() == val or t.value.lower() == val:
                    self.transition_mode = t
                    break

        if "sort_order" in cfg:
            val = str(cfg["sort_order"]).strip().lower()
            for s in SortOrder:
                if s.name.lower() == val or s.value.lower() == val:
                    self.sort_order = s
                    break

        if "caption_mode" in cfg:
            val = str(cfg["caption_mode"]).strip().lower()
            for c in CaptionMode:
                if c.name.lower() == val or c.value.lower() == val:
                    self.caption_mode = c
                    break

        if "is_fullscreen" in cfg:
            self.is_fullscreen = str(cfg["is_fullscreen"]).strip().lower() in ("true", "1", "yes")

        if "is_always_on_top" in cfg:
            self.is_always_on_top = str(cfg["is_always_on_top"]).strip().lower() in ("true", "1", "yes")

        if "enhancement_enabled" in cfg:
            self.enhancement_enabled = str(cfg["enhancement_enabled"]).strip().lower() in ("true", "1", "yes")

        if "show_status_icons" in cfg:
            self.show_status_icons = str(cfg["show_status_icons"]).strip().lower() in ("true", "1", "yes")

    def _save_current_config(self):
        """Persiste as configurações atuais na aba 'Configuracoes' da planilha."""
        cfg = {
            "delay_seconds": round(self.delay_ms / 1000.0, 2),
            "framing_mode": self.framing_mode.name.lower(),
            "transition_mode": self.transition_mode.name.lower(),
            "sort_order": self.sort_order.name.lower(),
            "caption_mode": self.caption_mode.name.lower(),
            "is_fullscreen": self.is_fullscreen,
            "is_always_on_top": self.is_always_on_top,
            "enhancement_enabled": self.enhancement_enabled,
            "show_status_icons": self.show_status_icons,
        }
        self.favorites.save_config(cfg)

    def _apply_sort_order(self, reset_history: bool = True):
        """Reorganiza a lista ativa de exibição e reseta/ajusta o histórico de navegação."""
        base_paths = self.raw_image_paths

        if self.filter_mode == "FAVORITES":
            base_paths = [p for p in base_paths if self.favorites.is_favorite(p)]
            if not base_paths:
                self.show_toast("Nenhuma foto favoritada nesta pasta!", duration_ms=2500)
                self.filter_mode = "ALL"
                base_paths = self.raw_image_paths
        elif self.filter_mode == "UNLIKES":
            base_paths = [p for p in base_paths if self.favorites.is_unliked(p)]
            if not base_paths:
                self.show_toast("Nenhuma foto com unlike nesta pasta!", duration_ms=2500)
                self.filter_mode = "ALL"
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

        # Se for modo Panorâmico, pré-escala uma única vez na RAM
        if self.framing_mode == FramingMode.PANORAMIC:
            self.pan_scaled_img, self.pan_max_dx, self.pan_max_dy = pre_scale_panoramic(
                new_pil, win_w, win_h, enhance_lowres=self.enhancement_enabled
            )
            new_canvas_img = crop_panoramic_frame(
                self.pan_scaled_img, win_w, win_h, self.pan_max_dx, self.pan_max_dy, 0.0
            )
        else:
            self.pan_scaled_img = None
            new_canvas_img = prepare_canvas_image(
                new_pil, win_w, win_h, self.framing_mode, enhance_lowres=self.enhancement_enabled
            )

        self.current_pil_img = new_pil
        self.current_canvas_img = new_canvas_img

        # Decide o tipo de transição
        if first_run or self.transition_mode == TransitionMode.HARD or old_canvas_img is None:
            self._display_canvas_image(new_canvas_img)
            self._post_slide_render(path, transition_duration_ms=0)
        elif self.transition_mode == TransitionMode.CROSSFADE:
            self._animate_crossfade(old_canvas_img, new_canvas_img, path, step=0, total_steps=25)
        elif self.transition_mode == TransitionMode.FADE_BLACK:
            self._animate_fade_black(old_canvas_img, new_canvas_img, path, step=0, total_steps=25)

    def _display_canvas_image(self, pil_img: Image.Image):
        """Converte a imagem PIL para PhotoImage e atualiza o Canvas suavemente sem flicker."""
        self.current_photo_tk = ImageTk.PhotoImage(pil_img)
        if self.canvas_img_id is None:
            self.canvas_img_id = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.current_photo_tk)
        else:
            self.canvas.itemconfig(self.canvas_img_id, image=self.current_photo_tk)
        self.canvas.tag_lower(self.canvas_img_id)

    def _post_slide_render(self, path: str, transition_duration_ms: int = 0):
        """Finaliza renderização do slide: atualiza legendas e agenda início suave de pan e próximo slide."""
        self._update_caption_overlay(path)

        # Se estiver no modo Panorâmico, espera a pausa de assentamento (350ms) antes de iniciar a câmera
        if self.framing_mode == FramingMode.PANORAMIC and not self.is_paused:
            remaining_ms = self.delay_ms - transition_duration_ms - SETTLE_PAUSE_MS
            self.pan_duration_sec = max(1.0, remaining_ms / 1000.0)
            self.settle_job = self.root.after(SETTLE_PAUSE_MS, self._start_pan_after_settle)

        # Agenda o próximo slide
        if not self.is_paused:
            self.scheduled_next = self.root.after(self.delay_ms, self.next_slide)

    def _start_pan_after_settle(self):
        """Inicia a movimentação panorâmica estritamente a partir do repouso após o término da transição."""
        if self.framing_mode != FramingMode.PANORAMIC or self.is_paused or not self.pan_scaled_img:
            return
        self.pan_start_time = time.time()
        self._start_panoramic_tick()

    def _animate_crossfade(self, old_img: Image.Image, new_img: Image.Image, path: str, step: int, total_steps: int):
        """Executa interpolação gradual e suave entre duas imagens (Crossfade cinemático)."""
        alpha = step / total_steps
        blended = blend_two_images(old_img, new_img, alpha)
        self._display_canvas_image(blended)

        if step < total_steps:
            self.transition_job = self.root.after(
                18,
                self._animate_crossfade,
                old_img,
                new_img,
                path,
                step + 1,
                total_steps
            )
        else:
            self._display_canvas_image(new_img)
            # 25 passos * 18ms = ~450ms
            self._post_slide_render(path, transition_duration_ms=450)

    def _animate_fade_black(self, old_img: Image.Image, new_img: Image.Image, path: str, step: int, total_steps: int):
        """Executa esmaecimento suave para o preto e retorno gradual à nova imagem."""
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
                18,
                self._animate_fade_black,
                old_img,
                new_img,
                path,
                step + 1,
                total_steps
            )
        else:
            self._display_canvas_image(new_img)
            self._post_slide_render(path, transition_duration_ms=450)

    def _start_panoramic_tick(self):
        """Atualiza periodicamente o frame panorâmico (efeito Ken Burns) com custo computacional mínimo (<0.2ms)."""
        if self.framing_mode != FramingMode.PANORAMIC or self.is_paused:
            return
        if not self.pan_scaled_img:
            return

        elapsed = time.time() - self.pan_start_time
        progress = elapsed / self.pan_duration_sec

        if progress <= 1.0:
            win_w = self.canvas.winfo_width()
            win_h = self.canvas.winfo_height()
            panned = crop_panoramic_frame(
                self.pan_scaled_img, win_w, win_h, self.pan_max_dx, self.pan_max_dy, progress
            )
            # Mantém a referência do quadro atualizado para que a transição saia deste ponto exato
            self.current_canvas_img = panned
            self._display_canvas_image(panned)
            # 20ms = ~50 FPS de alta fluidez
            self.pan_job = self.root.after(20, self._start_panoramic_tick)
        else:
            # Fixa o quadro final absoluto (1.0) até o momento em que a próxima transição começar
            win_w = self.canvas.winfo_width()
            win_h = self.canvas.winfo_height()
            final_panned = crop_panoramic_frame(
                self.pan_scaled_img, win_w, win_h, self.pan_max_dx, self.pan_max_dy, 1.0
            )
            self.current_canvas_img = final_panned
            self._display_canvas_image(final_panned)

    def _cancel_scheduled_jobs(self):
        """Cancela timers ativos para evitar colisões durante transições."""
        if self.scheduled_next:
            self.root.after_cancel(self.scheduled_next)
            self.scheduled_next = None
        if self.settle_job:
            self.root.after_cancel(self.settle_job)
            self.settle_job = None
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
        """Atualiza a legenda no topo da tela e o ícone de status no canto superior direito."""
        self.canvas.delete("caption")
        self.canvas.delete("status_icon")

        win_w = self.canvas.winfo_width()
        is_fav = self.favorites.is_favorite(path)
        is_unl = self.favorites.is_unliked(path)

        # 1. Ícone de status no canto superior direito (Coração / X Vermelho)
        if self.show_status_icons and (is_fav or is_unl):
            icon_x = win_w - 35
            icon_y = 25
            icon_text = "❤️" if is_fav else "❌"
            icon_color = "#FF4B4B" if is_fav else "#FF2222"
            icon_bg = "#2A1010" if is_fav else "#2E0A0A"
            icon_id = self.canvas.create_text(
                icon_x, icon_y, text=icon_text, fill=icon_color, font=("Segoe UI Emoji", 14), tags="status_icon"
            )
            ibbox = self.canvas.bbox(icon_id)
            if ibbox:
                irect_id = self.canvas.create_rectangle(
                    ibbox[0] - 8, ibbox[1] - 4, ibbox[2] + 8, ibbox[3] + 4,
                    fill=icon_bg, outline="#552222", width=1, tags="status_icon"
                )
                self.canvas.tag_raise(icon_id, irect_id)

        # 2. Legenda informativa centralizada no topo
        if self.caption_mode == CaptionMode.NONE:
            return

        filename = os.path.basename(path)
        current_num = self.history_pos + 1
        total_num = len(self.playlist)

        tag_icon = " ❤️" if is_fav else (" ❌" if is_unl else "")

        filter_tag = ""
        if self.filter_mode == "FAVORITES":
            filter_tag = " [Filtro: Favoritas]"
        elif self.filter_mode == "UNLIKES":
            filter_tag = " [Filtro: Unlikes]"

        if self.caption_mode == CaptionMode.COMPACT:
            text = f"[{current_num}/{total_num}]{filter_tag} {filename}{tag_icon}"
        elif self.caption_mode == CaptionMode.DETAILED:
            res_str = f"{self.current_pil_img.size[0]}x{self.current_pil_img.size[1]}" if self.current_pil_img else ""
            parent_dir = os.path.basename(os.path.dirname(path))
            text = f"[{current_num}/{total_num}]{filter_tag} {parent_dir}/{filename} ({res_str}){tag_icon}"
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

    def add_like(self, event=None):
        """
        Lógica progressiva de Like:
        - Se possuir Unlike, o 1º aperto desfaz o unlike (volta a neutro).
        - Se estiver neutro, aplica Like (coração ❤️).
        - Se já for Like, informa que já está favoritado.
        """
        path = self.get_current_image_path()
        if not path:
            return

        if self.favorites.is_unliked(path):
            self.favorites.remove_unlike(path)
            self.show_toast("Unlike desfeito! (Foto neutra) ⚪", duration_ms=1800)
            self._update_caption_overlay(path)
            return

        if self.favorites.is_favorite(path):
            self.show_toast("Esta foto já está favoritada! ❤️", duration_ms=1500)
            return

        metadata = {}
        if self.current_pil_img:
            metadata["resolution"] = f"{self.current_pil_img.size[0]}x{self.current_pil_img.size[1]}"
        try:
            metadata["size_kb"] = round(os.path.getsize(path) / 1024, 2)
        except OSError:
            pass

        self.favorites.add_favorite(path, metadata)
        self.show_toast("Favoritada! ❤️ Salva no Excel.", duration_ms=1800)
        self._update_caption_overlay(path)

    def remove_like(self, event=None):
        """
        Lógica progressiva de Unlike / Dislike:
        - Se possuir Like, o 1º aperto remove dos favoritos (volta a neutro).
        - Se estiver neutro, aplica Unlike (X vermelho ❌).
        - Se já for Unlike, informa que já está com unlike.
        """
        path = self.get_current_image_path()
        if not path:
            return

        if self.favorites.is_favorite(path):
            self.favorites.remove_favorite(path)
            self.show_toast("Removida dos favoritos! 🤍", duration_ms=1800)
            self._update_caption_overlay(path)
            return

        if self.favorites.is_unliked(path):
            self.show_toast("Esta foto já está marcada com unlike! ❌", duration_ms=1500)
            return

        metadata = {}
        if self.current_pil_img:
            metadata["resolution"] = f"{self.current_pil_img.size[0]}x{self.current_pil_img.size[1]}"
        try:
            metadata["size_kb"] = round(os.path.getsize(path) / 1024, 2)
        except OSError:
            pass

        self.favorites.add_unlike(path, metadata)
        self.show_toast("Marcada com Unlike! ❌ Salva no Excel.", duration_ms=1800)
        self._update_caption_overlay(path)

    def toggle_filter(self, event=None):
        """Alterna ciclo de filtros: Todas as fotos -> Apenas Favoritas -> Apenas Unlikes."""
        modes = ["ALL", "FAVORITES", "UNLIKES"]
        curr_idx = modes.index(self.filter_mode) if self.filter_mode in modes else 0
        self.filter_mode = modes[(curr_idx + 1) % len(modes)]

        if self.filter_mode == "ALL":
            self.show_toast("Exibindo: Todas as Fotos", duration_ms=1800)
        elif self.filter_mode == "FAVORITES":
            self.show_toast("Filtrando: Apenas Favoritas ❤️", duration_ms=1800)
        elif self.filter_mode == "UNLIKES":
            self.show_toast("Filtrando: Apenas Unlikes ❌", duration_ms=1800)

        self._apply_sort_order(reset_history=True)
        self.next_slide()

    def toggle_filter_favorites(self, event=None):
        """Compatibilidade: alterna ciclo de filtros."""
        self.toggle_filter(event)

    def toggle_status_icons(self, event=None):
        """Alterna a visibilidade dos ícones de status (❤️ / ❌) no canto direito."""
        self.show_status_icons = not self.show_status_icons
        status = "Ativados" if self.show_status_icons else "Ocultos"
        self.show_toast(f"Ícones de Status: {status}", duration_ms=1500)
        self._save_current_config()
        path = self.get_current_image_path()
        if path:
            self._update_caption_overlay(path)

    def handle_delete_action(self, event=None):
        """Trata tecla Delete: se estiver no modo unlikes executa exclusão em lote; senão unlike da foto atual."""
        if self.filter_mode == "UNLIKES":
            self.delete_all_unlikes()
        else:
            self.remove_like(event)

    def delete_all_unlikes(self, event=None):
        """
        Quando (e somente quando) estiver filtrando os unlikes, lista as fotos marcadas,
        solicita confirmação explícita e, se confirmado, apaga os arquivos do disco e do Excel.
        """
        if self.filter_mode != "UNLIKES":
            self.show_toast("A exclusão em lote só é permitida no modo de filtro 'Apenas Unlikes'!", duration_ms=2500)
            return

        unliked_in_folder = [p for p in self.raw_image_paths if self.favorites.is_unliked(p)]
        if not unliked_in_folder:
            self.show_toast("Nenhuma foto com unlike nesta pasta para apagar.", duration_ms=2000)
            return

        # Pausa a apresentação durante o diálogo
        was_paused = self.is_paused
        self.is_paused = True
        self._cancel_scheduled_jobs()

        # Cria janela de confirmação detalhada com rolagem se necessário
        confirm_win = tk.Toplevel(self.root)
        confirm_win.title("Confirmar Exclusão de Fotos com Unlike")
        confirm_win.geometry("620x450")
        confirm_win.configure(bg="#222")
        confirm_win.attributes("-topmost", True)
        confirm_win.focus_force()

        header_lbl = tk.Label(
            confirm_win,
            text=f"Atenção: {len(unliked_in_folder)} foto(s) com Unlike serão apagadas do disco!",
            bg="#222",
            fg="#FF5252",
            font=("Helvetica", 11, "bold")
        )
        header_lbl.pack(pady=10)

        txt_frame = tk.Frame(confirm_win, bg="#333")
        txt_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        scrollbar = tk.Scrollbar(txt_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        txt_list = tk.Text(
            txt_frame,
            bg="#1E1E1E",
            fg="#E0E0E0",
            font=("Consolas", 9),
            yscrollcommand=scrollbar.set,
            wrap=tk.NONE
        )
        txt_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=txt_list.yview)

        for p in unliked_in_folder:
            txt_list.insert(tk.END, f"{os.path.basename(p)}  ({p})\n")
        txt_list.config(state=tk.DISABLED)

        btn_frame = tk.Frame(confirm_win, bg="#222")
        btn_frame.pack(pady=12)

        def do_delete():
            confirm_win.destroy()
            deleted_count = 0
            for p in unliked_in_folder:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                    self.favorites.remove_unlike(p)
                    if p in self.raw_image_paths:
                        self.raw_image_paths.remove(p)
                    deleted_count += 1
                except Exception as e:
                    print(f"[Delete] Erro ao excluir '{p}': {e}")

            self.show_toast(f"Concluído: {deleted_count} fotos excluídas do disco e desmarcadas!", duration_ms=3000)
            self.filter_mode = "ALL"
            self._apply_sort_order(reset_history=True)
            self.is_paused = was_paused
            self.next_slide()

        def do_cancel():
            confirm_win.destroy()
            self.is_paused = was_paused
            if not self.is_paused:
                self.scheduled_next = self.root.after(self.delay_ms, self.next_slide)

        btn_confirm = tk.Button(
            btn_frame,
            text="Sim, Apagar Definitivamente",
            command=do_delete,
            bg="#C62828",
            fg="white",
            font=("Helvetica", 10, "bold"),
            padx=15,
            pady=4
        )
        btn_confirm.pack(side=tk.LEFT, padx=10)

        btn_cancel = tk.Button(
            btn_frame,
            text="Cancelar",
            command=do_cancel,
            bg="#555",
            fg="white",
            font=("Helvetica", 10),
            padx=15,
            pady=4
        )
        btn_cancel.pack(side=tk.LEFT, padx=10)

        confirm_win.bind("<Escape>", lambda e: do_cancel())

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
            self._save_current_config()
            self.show_toast(f"Novo intervalo: {val:.2f} segundos", duration_ms=2000)

        self.is_paused = was_paused
        if not self.is_paused:
            self.scheduled_next = self.root.after(self.delay_ms, self.next_slide)

    def cycle_sort_order(self, event=None):
        """Alterna o modo de ordenação em tempo de execução."""
        orders = [SortOrder.RANDOM, SortOrder.DATE, SortOrder.NAME]
        curr_idx = orders.index(self.sort_order)
        self.sort_order = orders[(curr_idx + 1) % len(orders)]
        self._save_current_config()
        self._apply_sort_order(reset_history=True)
        self.show_toast(f"Ordem: {self.sort_order.value}", duration_ms=2000)
        self.next_slide()

    def cycle_framing_mode(self, event=None):
        """Alterna o modo de enquadramento (Fit, Fill, Panorâmico)."""
        modes = [FramingMode.FIT, FramingMode.FILL, FramingMode.PANORAMIC]
        curr_idx = modes.index(self.framing_mode)
        self.framing_mode = modes[(curr_idx + 1) % len(modes)]
        self._save_current_config()
        self.show_toast(f"Enquadramento: {self.framing_mode.value}", duration_ms=2000)
        self._cancel_scheduled_jobs()
        self._render_current_slide()

    def cycle_transition_mode(self, event=None):
        """Alterna o modo de transição (Crossfade, Dura, Fade Preto)."""
        transitions = [TransitionMode.CROSSFADE, TransitionMode.HARD, TransitionMode.FADE_BLACK]
        curr_idx = transitions.index(self.transition_mode)
        self.transition_mode = transitions[(curr_idx + 1) % len(transitions)]
        self._save_current_config()
        self.show_toast(f"Transição: {self.transition_mode.value}", duration_ms=2000)

    def cycle_caption(self, event=None):
        """Alterna a exibição da legenda na tela."""
        modes = [CaptionMode.NONE, CaptionMode.COMPACT, CaptionMode.DETAILED]
        curr_idx = modes.index(self.caption_mode)
        self.caption_mode = modes[(curr_idx + 1) % len(modes)]
        self._save_current_config()
        self.show_toast(f"Legenda: {self.caption_mode.value}", duration_ms=1500)
        path = self.get_current_image_path()
        if path:
            self._update_caption_overlay(path)

    def toggle_fullscreen(self, event=None):
        """Alterna o modo de tela cheia com F11."""
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes("-fullscreen", self.is_fullscreen)
        self._save_current_config()
        self.show_toast("Tela Cheia: Ativada" if self.is_fullscreen else "Tela Cheia: Desativada", duration_ms=1200)

    def toggle_enhancement(self, event=None):
        """Alterna a otimização inteligente de imagens em baixa resolução (Tecla E)."""
        self.enhancement_enabled = not self.enhancement_enabled
        status = "ATIVADA (Nitidez + Fundo Suave)" if self.enhancement_enabled else "DESATIVADA"
        self._save_current_config()
        self.show_toast(f"Melhoria Baixa Resolução: {status}", duration_ms=2200)
        self._cancel_scheduled_jobs()
        self._render_current_slide()

    def on_escape(self, event=None):
        """
        Escape prioritário:
        - Se a janela de ajuda F1 estiver aberta, fecha apenas ela.
        - Senão, se estiver em tela cheia sai dela; caso contrário fecha a aplicação.
        """
        if self.help_window and self.help_window.winfo_exists():
            self.help_window.destroy()
            self.help_window = None
            return

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
            self._save_current_config()
            self.show_toast(f"Velocidade: {self.delay_ms / 1000:.2f} s", duration_ms=1000)

    def speed_down(self, event=None):
        """Desacelera o intervalo do slide."""
        self.delay_ms = min(int(self.delay_ms * 1.35), 60000)
        self._save_current_config()
        self.show_toast(f"Velocidade: {self.delay_ms / 1000:.2f} s", duration_ms=1000)

    def toggle_topmost(self, event=None):
        """Alterna fixação da janela no topo."""
        self.is_always_on_top = not self.is_always_on_top
        self.root.attributes("-topmost", self.is_always_on_top)
        self._save_current_config()
        self.show_toast("Janela no Topo: Ativada" if self.is_always_on_top else "Janela no Topo: Desativada", duration_ms=1200)

    def on_window_resize(self, event):
        """Trata redimensionamento da janela recalculando o canvas."""
        if event.widget == self.root:
            if self.current_pil_img and not self.transition_job:
                self._cancel_scheduled_jobs()
                self._render_current_slide()

    def toggle_help_window(self, event=None):
        """Abre ou fecha a janela de ajuda (toggle). Se já estiver aberta, fecha."""
        if self.help_window and self.help_window.winfo_exists():
            self.help_window.destroy()
            self.help_window = None
            return

        help_win = tk.Toplevel(self.root)
        self.help_window = help_win
        help_win.title("Atalhos e Ajuda do Slideshow")
        help_win.geometry("570x610")
        help_win.configure(bg="#1E1E1E")
        help_win.resizable(False, False)
        help_win.attributes("-topmost", True)

        def close_help(e=None):
            if self.help_window and self.help_window.winfo_exists():
                self.help_window.destroy()
            self.help_window = None

        help_win.protocol("WM_DELETE_WINDOW", close_help)
        help_win.bind("<Escape>", close_help)
        help_win.bind("<F1>", close_help)

        title_lbl = tk.Label(
            help_win,
            text="Slideshow Pro - Atalhos de Teclado",
            bg="#1E1E1E",
            fg="#4FC3F7",
            font=("Helvetica", 14, "bold")
        )
        title_lbl.pack(pady=10)

        help_data = [
            ("F1", "Abrir / Fechar esta tela de ajuda (Toggle)"),
            ("F11", "Alternar Tela Cheia"),
            ("Espaço", "Pausar / Retomar apresentação"),
            ("Seta Esquerda", "Foto Anterior (Histórico Infinito)"),
            ("Seta Direita", "Próxima Foto"),
            ("Seta Cima / Baixo", "Acelerar / Desacelerar intervalo"),
            ("D", "Digitar intervalo de tempo personalizado"),
            ("O", "Alternar Ordem (Aleatória / Data / Alfabética)"),
            ("L", "Like ❤️ (Se houver Unlike, desfaz o unlike primeiro)"),
            ("U", "Unlike ❌ (Se houver Like, desfaz o like primeiro)"),
            ("F", "Alternar Filtro (Todas -> Apenas Favoritas -> Apenas Unlikes)"),
            ("I", "Alternar exibição dos Ícones de Status (❤️ / ❌)"),
            ("Shift+Delete", "Apagar do disco todas as fotos com Unlike (no filtro Unlikes)"),
            ("E", "Alternar Otimização Baixa Resolução"),
            ("C", "Alternar Legenda (Oculta / Compacta / Detalhada)"),
            ("M", "Modo Enquadramento (Ajustar / Zoom / Panorâmico)"),
            ("X", "Modo Transição (Suave Crossfade / Dura / Fade)"),
            ("T / P", "Alternar Janela sempre no Topo"),
            ("Esc", "Fechar Ajuda (se aberta) / Sair Tela Cheia / Sair"),
        ]

        frame_table = tk.Frame(help_win, bg="#2A2A2A", padx=10, pady=5)
        frame_table.pack(padx=15, pady=5, fill=tk.BOTH, expand=True)

        for row, (key, desc) in enumerate(help_data):
            lbl_key = tk.Label(
                frame_table,
                text=key,
                bg="#3A3A3A",
                fg="#FFD54F",
                font=("Helvetica", 8, "bold"),
                padx=6,
                pady=1,
                relief=tk.RIDGE
            )
            lbl_key.grid(row=row, column=0, padx=4, pady=2, sticky=tk.W)

            lbl_desc = tk.Label(
                frame_table,
                text=desc,
                bg="#2A2A2A",
                fg="#E0E0E0",
                font=("Helvetica", 8),
                padx=4
            )
            lbl_desc.grid(row=row, column=1, padx=4, pady=2, sticky=tk.W)

        btn_close = tk.Button(
            help_win,
            text="Fechar (Esc)",
            command=close_help,
            bg="#333",
            fg="white",
            relief=tk.FLAT,
            font=("Helvetica", 9, "bold"),
            padx=15,
            pady=3
        )
        btn_close.pack(pady=8)

    def quit_app(self, event=None):
        """Finaliza a aplicação persistindo as configurações e restaurando energia."""
        self._cancel_scheduled_jobs()
        self._save_current_config()
        OneDriveVaultManager.restore_system_sleep()
        self.root.destroy()
