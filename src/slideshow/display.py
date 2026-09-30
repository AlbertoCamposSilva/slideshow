"""Módulo de renderização gráfica, modos de enquadramento (Fit, Fill, Panorâmico) e transições visuais."""

from enum import Enum
from typing import Tuple, Optional
from PIL import Image


class FramingMode(Enum):
    FIT = "Ajustar (Fit)"
    FILL = "Zoom / Preencher (Fill)"
    PANORAMIC = "Panorâmico (Ken Burns)"


class TransitionMode(Enum):
    CROSSFADE = "Suave (Crossfade)"
    HARD = "Dura (Instantânea)"
    FADE_BLACK = "Esmaecer para Preto"


class SortOrder(Enum):
    RANDOM = "Aleatória"
    DATE = "Data"
    NAME = "Alfabética (Caminho)"


class CaptionMode(Enum):
    NONE = "Oculta"
    COMPACT = "Compacta"
    DETAILED = "Detalhada"


def prepare_canvas_image(
    image: Image.Image,
    win_w: int,
    win_h: int,
    mode: FramingMode,
    pan_progress: float = 0.0
) -> Image.Image:
    """
    Renderiza a imagem final no tamanho exato da janela (win_w, win_h),
    aplicando o enquadramento especificado (FIT com letterbox, FILL com crop central,
    ou PANORAMIC com pan dinâmico).
    """
    if win_w <= 10 or win_h <= 10:
        win_w, win_h = 800, 600

    img = image.convert("RGB")
    img_w, img_h = img.size

    if img_w <= 0 or img_h <= 0:
        return Image.new("RGB", (win_w, win_h), "black")

    if mode == FramingMode.FIT:
        # Ajusta para caber 100% da foto na janela, fundo preto
        ratio = min(win_w / img_w, win_h / img_h)
        new_w = max(1, int(img_w * ratio))
        new_h = max(1, int(img_h * ratio))
        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        canvas = Image.new("RGB", (win_w, win_h), "black")
        offset_x = (win_w - new_w) // 2
        offset_y = (win_h - new_h) // 2
        canvas.paste(resized, (offset_x, offset_y))
        return canvas

    elif mode == FramingMode.FILL:
        # Preenche 100% da janela sem barras pretas, centralizando o corte
        ratio = max(win_w / img_w, win_h / img_h)
        new_w = max(1, int(img_w * ratio))
        new_h = max(1, int(img_h * ratio))
        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        left = (new_w - win_w) // 2
        top = (new_h - win_h) // 2
        right = left + win_w
        bottom = top + win_h
        return resized.crop((left, top, right, bottom))

    elif mode == FramingMode.PANORAMIC:
        # Ken Burns Pan & Scan: Preenche toda a janela e move suavemente
        # Escala de modo que haja folga para deslocamento (no mínimo cobrindo a janela + 15% de margem)
        base_ratio = max(win_w / img_w, win_h / img_h)
        # Dá margem adicional para pan se a foto tiver aspecto similar à janela
        pan_factor = 1.15
        final_ratio = base_ratio * pan_factor

        scaled_w = int(img_w * final_ratio)
        scaled_h = int(img_h * final_ratio)
        resized = img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)

        max_dx = max(0, scaled_w - win_w)
        max_dy = max(0, scaled_h - win_h)

        # Interpolação suave (clamped entre 0.0 e 1.0)
        p = max(0.0, min(1.0, pan_progress))
        # Curva de aceleração suave (smoothstep)
        smooth_p = p * p * (3 - 2 * p)

        curr_x = int(max_dx * smooth_p)
        curr_y = int(max_dy * smooth_p)

        return resized.crop((curr_x, curr_y, curr_x + win_w, curr_y + win_h))

    return img


def blend_two_images(img1: Image.Image, img2: Image.Image, alpha: float) -> Image.Image:
    """Interpola duas imagens com mesmo tamanho para transição suave (Crossfade)."""
    alpha_clamped = max(0.0, min(1.0, alpha))
    if img1.size != img2.size:
        img2 = img2.resize(img1.size, Image.Resampling.BILINEAR)
    return Image.blend(img1, img2, alpha_clamped)


def fade_to_black_image(img: Image.Image, progress: float) -> Image.Image:
    """
    Transição com fade to black:
    - Se progress <= 0.5: escurece para preto (alpha 0.0 -> 1.0 de preto)
    - Se progress > 0.5: clareia a partir do preto
    """
    black = Image.new("RGB", img.size, "black")
    alpha = max(0.0, min(1.0, progress))
    return Image.blend(img, black, alpha)
