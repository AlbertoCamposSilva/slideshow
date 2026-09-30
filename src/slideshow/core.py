"""Módulo central para invocação programática e orquestração do Slideshow."""

import os
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import List, Optional
from pathlib import Path

from slideshow.app import SlideshowApp
from slideshow.vault import OneDriveVaultManager, IMAGE_EXTENSIONS
from slideshow.display import FramingMode, TransitionMode, SortOrder


def find_image_files(directory: str) -> List[str]:
    """Varre recursivamente o diretório em busca de imagens suportadas."""
    found = []
    try:
        for root, _, files in os.walk(directory):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in IMAGE_EXTENSIONS:
                    found.append(os.path.join(root, file))
    except (PermissionError, OSError) as e:
        print(f"[Erro] Falha ao varrer diretório '{directory}': {e}")
    return found


def resolve_target_directory(initial_path: Optional[str] = None) -> Optional[str]:
    """Resolve a pasta de imagens: caminho fornecido ou diálogo gráfico."""
    if initial_path:
        p = Path(initial_path)
        if p.exists() and p.is_dir():
            return str(p.resolve())

        # Se um caminho específico foi passado via CLI e for de cofre (mesmo que bloqueado)
        if OneDriveVaultManager.is_vault_path(initial_path):
            return initial_path

    # Abre seletor de pastas nativo do Tkinter trazendo obrigatoriamente para o primeiro plano
    temp_root = tk.Tk()
    temp_root.withdraw()
    temp_root.attributes("-topmost", True)
    temp_root.lift()
    temp_root.focus_force()
    chosen = filedialog.askdirectory(
        parent=temp_root,
        title="Selecione a pasta com as fotos para o Slideshow"
    )
    temp_root.destroy()
    return chosen if chosen else None


def check_vault_and_prompt(target_dir: str) -> bool:
    """Verifica se o cofre está bloqueado e oferece opção interativa de desbloqueio."""
    # Só atua se a pasta selecionada for comprovadamente de um Cofre Pessoal
    if not OneDriveVaultManager.is_vault_path(target_dir):
        return True

    if OneDriveVaultManager.is_vault_locked(target_dir):
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.lift()
        root.focus_force()

        ans = messagebox.askyesno(
            "Cofre Pessoal Bloqueado",
            f"A pasta selecionada faz parte do Cofre Pessoal do OneDrive, que está atualmente BLOQUEADO.\n\n"
            f"Deseja abrir o assistente do OneDrive para desbloquear o cofre agora?",
            icon="warning",
            parent=root
        )
        if ans:
            OneDriveVaultManager.request_unlock(target_dir)
            messagebox.showinfo(
                "Aguardando Desbloqueio",
                "Após autenticar-se e desbloquear o Cofre Pessoal no Windows, clique em OK para continuar.",
                parent=root
            )
            # Reavalia se foi desbloqueado
            if OneDriveVaultManager.is_vault_locked(target_dir):
                messagebox.showerror(
                    "Cofre Ainda Bloqueado",
                    "O cofre ainda não está acessível. Por favor, desbloqueie-o manualmente antes de iniciar.",
                    parent=root
                )
                root.destroy()
                return False
        else:
            root.destroy()
            return False

        root.destroy()
    return True


def run_slideshow(
    folder: Optional[str] = None,
    delay: float = 3.0,
    fullscreen: bool = False,
    framing: str = "fit",
    transition: str = "crossfade",
    order: str = "random",
    ram_limit_mb: int = 1024
):
    """
    Função principal exportada para iniciar o slideshow a partir de qualquer script ou CLI.
    """
    target_dir = resolve_target_directory(folder)
    if not target_dir:
        # Usuário cancelou ou fechou a seleção de pasta
        return

    # Trata verificação do cofre apenas se a pasta selecionada for um cofre
    if not check_vault_and_prompt(target_dir):
        return

    is_vault = OneDriveVaultManager.is_vault_path(target_dir)
    images = find_image_files(target_dir)

    if not images:
        root_temp = tk.Tk()
        root_temp.withdraw()
        root_temp.attributes("-topmost", True)
        root_temp.lift()
        root_temp.focus_force()
        messagebox.showwarning(
            "Nenhuma Imagem Encontrada",
            f"Nenhuma foto suportada foi encontrada na pasta:\n{target_dir}",
            parent=root_temp
        )
        root_temp.destroy()
        return

    # Mapeamento de enums a partir de strings
    framing_map = {
        "fit": FramingMode.FIT,
        "fill": FramingMode.FILL,
        "panoramic": FramingMode.PANORAMIC,
    }
    transition_map = {
        "crossfade": TransitionMode.CROSSFADE,
        "hard": TransitionMode.HARD,
        "fade_black": TransitionMode.FADE_BLACK,
    }
    order_map = {
        "random": SortOrder.RANDOM,
        "date": SortOrder.DATE,
        "name": SortOrder.NAME,
    }

    selected_framing = framing_map.get(framing.lower(), FramingMode.FIT)
    selected_transition = transition_map.get(transition.lower(), TransitionMode.CROSSFADE)
    selected_order = order_map.get(order.lower(), SortOrder.RANDOM)

    root = tk.Tk()
    root.geometry("1200x800")
    if fullscreen:
        root.attributes("-fullscreen", True)

    app = SlideshowApp(
        root=root,
        all_image_paths=images,
        delay_seconds=delay,
        framing_mode=selected_framing,
        transition_mode=selected_transition,
        sort_order=selected_order,
        ram_limit_mb=ram_limit_mb,
        is_vault=is_vault
    )
    if fullscreen:
        app.is_fullscreen = True

    root.mainloop()
