"""Testes unitários para o módulo slideshow."""

import os
import tempfile
from pathlib import Path
from PIL import Image

from slideshow.display import (
    FramingMode,
    TransitionMode,
    SortOrder,
    prepare_canvas_image,
    blend_two_images,
    fade_to_black_image,
)
from slideshow.buffer import RAMImageBuffer
from slideshow.favorites import FavoritesManager
from slideshow.vault import OneDriveVaultManager, diagnose_path


def test_display_canvas_fit():
    img = Image.new("RGB", (200, 100), color="red")
    canvas = prepare_canvas_image(img, 400, 300, FramingMode.FIT)
    assert canvas.size == (400, 300)


def test_display_canvas_fill():
    img = Image.new("RGB", (200, 100), color="blue")
    canvas = prepare_canvas_image(img, 400, 300, FramingMode.FILL)
    assert canvas.size == (400, 300)


def test_display_canvas_panoramic():
    img = Image.new("RGB", (600, 300), color="green")
    canvas_start = prepare_canvas_image(img, 400, 300, FramingMode.PANORAMIC, pan_progress=0.0)
    canvas_end = prepare_canvas_image(img, 400, 300, FramingMode.PANORAMIC, pan_progress=1.0)
    assert canvas_start.size == (400, 300)
    assert canvas_end.size == (400, 300)


def test_panoramic_fast_crop():
    from slideshow.display import pre_scale_panoramic, crop_panoramic_frame
    img = Image.new("RGB", (1000, 500), color="purple")
    scaled_img, max_dx, max_dy = pre_scale_panoramic(img, 400, 300)
    assert scaled_img.width >= 400
    assert scaled_img.height >= 300

    frame_0 = crop_panoramic_frame(scaled_img, 400, 300, max_dx, max_dy, 0.0)
    frame_mid = crop_panoramic_frame(scaled_img, 400, 300, max_dx, max_dy, 0.5)
    frame_1 = crop_panoramic_frame(scaled_img, 400, 300, max_dx, max_dy, 1.0)
    assert frame_0.size == (400, 300)
    assert frame_mid.size == (400, 300)
    assert frame_1.size == (400, 300)


def test_blend_images():
    img1 = Image.new("RGB", (100, 100), color="white")
    img2 = Image.new("RGB", (100, 100), color="black")
    blended = blend_two_images(img1, img2, 0.5)
    assert blended.size == (100, 100)


def test_favorites_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        excel_path = Path(tmpdir) / "test_favoritos.xlsx"
        fav = FavoritesManager(excel_path=excel_path)
        assert fav.favorites_count == 0

        fake_photo = os.path.join(tmpdir, "foto1.jpg")
        with open(fake_photo, "wb") as f:
            f.write(b"fake data")

        # Adiciona like explícito
        added = fav.add_favorite(fake_photo, {"resolution": "1920x1080", "size_kb": 12.5})
        assert added is True
        assert fav.is_favorite(fake_photo) is True
        assert fav.favorites_count == 1
        assert excel_path.exists()

        # Tentar adicionar novamente não deve duplicar nem remover
        added_again = fav.add_favorite(fake_photo)
        assert added_again is False
        assert fav.is_favorite(fake_photo) is True
        assert fav.favorites_count == 1

        # Remove like com método dedicado
        removed = fav.remove_favorite(fake_photo)
        assert removed is True
        assert fav.is_favorite(fake_photo) is False
        assert fav.favorites_count == 0

        # Tentar remover novamente retorna False
        removed_again = fav.remove_favorite(fake_photo)
        assert removed_again is False


def test_buffer_vault_only():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Buffer não-vault: não deve pré-carregar
        buf_normal = RAMImageBuffer(ram_limit_mb=10, is_vault=False)
        img_path = os.path.join(tmpdir, "test.png")
        img = Image.new("RGB", (50, 50), color="red")
        img.save(img_path)

        loaded = buf_normal.preload_images([img_path])
        assert loaded == 0  # Não carrega se não for vault
        assert buf_normal.usage_mb == 0.0

        # Buffer vault: deve carregar em RAM
        buf_vault = RAMImageBuffer(ram_limit_mb=10, is_vault=True)
        loaded_vault = buf_vault.preload_images([img_path])
        assert loaded_vault == 1
        assert buf_vault.usage_mb > 0.0

        retrieved = buf_vault.get_image(img_path)
        assert retrieved is not None
        assert retrieved.size == (50, 50)


def test_diagnose_nonexistent_path():
    diag = diagnose_path(r"C:\Caminho\Inexistente\Fotos_123456")
    assert diag["exists"] is False
    assert diag["accessible"] is False
    assert len(diag["advice"]) > 0


def test_lowres_enhancement_applied():
    from slideshow.display import enhance_lowres_image, prepare_canvas_image
    small_img = Image.new("RGB", (200, 150), color="blue")
    enhanced = enhance_lowres_image(small_img, 1920, 1440)
    assert enhanced.size == (1920, 1440)

    # Com enhance_lowres ativado, cria fundo ambiente desfocado
    canvas_enhanced = prepare_canvas_image(small_img, 800, 600, FramingMode.FIT, enhance_lowres=True)
    assert canvas_enhanced.size == (800, 600)

    # Com enhance_lowres desativado, gera com fundo preto padrão
    canvas_normal = prepare_canvas_image(small_img, 800, 600, FramingMode.FIT, enhance_lowres=False)
    assert canvas_normal.size == (800, 600)


def test_highres_image_not_modified_by_enhancement():
    from slideshow.display import prepare_canvas_image
    # Imagem de alta resolução (maior que a tela 400x300)
    large_img = Image.new("RGB", (1200, 900), color="red")
    canvas = prepare_canvas_image(large_img, 400, 300, FramingMode.FIT, enhance_lowres=True)
    assert canvas.size == (400, 300)
