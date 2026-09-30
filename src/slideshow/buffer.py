"""Módulo de gerenciamento de buffer de memória RAM com limite configurável para fotos do Cofre Pessoal."""

import io
import os
from typing import Dict, List, Optional, Callable
from PIL import Image

DEFAULT_RAM_LIMIT_MB = 1024  # 1 GB


class RAMImageBuffer:
    """Gerenciador de cache em RAM para evitar que o auto-bloqueio do Cofre Pessoal interrompa o slideshow."""

    def __init__(self, ram_limit_mb: int = DEFAULT_RAM_LIMIT_MB, is_vault: bool = False):
        self.ram_limit_bytes = ram_limit_mb * 1024 * 1024
        self.is_vault = is_vault
        self.current_usage_bytes = 0
        self.buffer: Dict[str, bytes] = {}
        self.failed_paths: set = set()

    def should_preload(self) -> bool:
        """Determina se o pré-carregamento deve ocorrer (apenas se for detectado que está no Vault)."""
        return self.is_vault

    def preload_images(
        self,
        image_paths: List[str],
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> int:
        """
        Pré-carrega o conteúdo dos arquivos de imagem para a memória RAM.
        Retorna o total de imagens carregadas no buffer.
        """
        if not self.should_preload():
            return 0

        loaded_count = 0
        total_files = len(image_paths)

        for idx, path in enumerate(image_paths):
            if progress_callback:
                progress_callback(idx + 1, total_files, os.path.basename(path))

            try:
                file_size = os.path.getsize(path)
            except OSError:
                continue

            # Verifica se o arquivo cabe no limite estipulado de RAM
            if self.current_usage_bytes + file_size > self.ram_limit_bytes:
                # Limite de RAM atingido
                break

            try:
                with open(path, "rb") as f:
                    data = f.read()
                self.buffer[path] = data
                self.current_usage_bytes += len(data)
                loaded_count += 1
            except (OSError, PermissionError):
                self.failed_paths.add(path)

        return loaded_count

    def get_image(self, path: str) -> Optional[Image.Image]:
        """
        Obtém a imagem do buffer de memória (se disponível) ou diretamente do disco.
        Retorna uma instância de PIL.Image ou None se houver erro irrecuperável.
        """
        # 1. Tenta recuperar da memória
        if path in self.buffer:
            try:
                bio = io.BytesIO(self.buffer[path])
                img = Image.open(bio)
                img.load()  # Garante decodificação completa na memória
                return img
            except Exception as e:
                print(f"[Buffer] Erro ao ler imagem do buffer de memória para '{path}': {e}")

        # 2. Se não estiver em buffer, lê do disco
        try:
            img = Image.open(path)
            img.load()
            return img
        except (FileNotFoundError, PermissionError, OSError) as e:
            print(f"[Disk] Falha de acesso ao ler do disco '{path}': {e}")
            return None
        except Exception as e:
            print(f"[Disk] Erro ao abrir arquivo de imagem '{path}': {e}")
            return None

    def clear(self):
        """Limpa o buffer de memória."""
        self.buffer.clear()
        self.current_usage_bytes = 0
        self.failed_paths.clear()

    @property
    def usage_mb(self) -> float:
        """Uso atual de memória do buffer em Megabytes."""
        return self.current_usage_bytes / (1024 * 1024)
