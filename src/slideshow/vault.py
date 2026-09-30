"""Módulo de diagnóstico e gerenciamento de caminhos, atributos de arquivo e Cofre Pessoal (Personal Vault) do OneDrive."""

import os
import sys
import ctypes
from pathlib import Path
from typing import Dict, Any, List, Optional

# Atributos de arquivo do Windows (Win32 API)
FILE_ATTRIBUTE_READONLY = 0x00000001
FILE_ATTRIBUTE_HIDDEN = 0x00000002
FILE_ATTRIBUTE_SYSTEM = 0x00000004
FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_ATTRIBUTE_ARCHIVE = 0x00000020
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
FILE_ATTRIBUTE_OFFLINE = 0x00001000
FILE_ATTRIBUTE_PINNED = 0x00080000
FILE_ATTRIBUTE_UNPINNED = 0x00100000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x00040000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x00400000

# Execução de energia no Windows (manter tela e sistema ligados durante o slideshow)
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}


def get_file_attributes_win32(path: str) -> Optional[int]:
    """Retorna a máscara de atributos do arquivo no Windows ou None se indisponível."""
    if sys.platform != 'win32':
        return None
    try:
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        if attrs == 0xFFFFFFFF:  # INVALID_FILE_ATTRIBUTES
            return None
        return attrs
    except Exception:
        return None


def is_dehydrated_cloud_file(path: str) -> bool:
    """Verifica se o arquivo é um ponteiro em nuvem (Files On-Demand desidratado)."""
    attrs = get_file_attributes_win32(path)
    if attrs is None:
        return False
    # Arquivo desidratado tem bits de recall ou offline
    is_recall = bool(attrs & (FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS | FILE_ATTRIBUTE_RECALL_ON_OPEN))
    is_offline = bool(attrs & FILE_ATTRIBUTE_OFFLINE)
    return is_recall or is_offline


class OneDriveVaultManager:
    """Gerenciador de detecção e interação com o Cofre Pessoal do OneDrive."""

    VAULT_DIR_NAMES = {"cofre pessoal", "personal vault"}
    VAULT_LNK_NAMES = {"cofre pessoal.lnk", "personal vault.lnk"}

    @classmethod
    def find_onedrive_root(cls, path: Path) -> Optional[Path]:
        """Tenta localizar a raiz da pasta do OneDrive subindo a árvore de diretórios."""
        curr = path.resolve() if path.exists() else path
        for parent in [curr] + list(curr.parents):
            # Procura marcas típicas do OneDrive
            name_lower = parent.name.lower()
            if "onedrive" in name_lower:
                return parent
            # Ou verifica se há arquivo .lnk do cofre ou marcador desktop.ini
            for lnk in cls.VAULT_LNK_NAMES:
                if (parent / lnk).exists():
                    return parent
        return None

    @classmethod
    def is_vault_path(cls, path_str: str) -> bool:
        """Verifica se o caminho informado é ou está dentro de um Cofre Pessoal."""
        p = Path(path_str)
        # Checa se algum segmento do caminho contém "Cofre Pessoal" ou "Personal Vault"
        for part in p.parts:
            if part.lower() in cls.VAULT_DIR_NAMES:
                return True
        return False

    @classmethod
    def find_vault_lnk(cls, path_str: str) -> Optional[Path]:
        """Procura o atalho .lnk do Cofre Pessoal no OneDrive."""
        p = Path(path_str)
        onedrive_root = cls.find_onedrive_root(p)
        if onedrive_root:
            for lnk in cls.VAULT_LNK_NAMES:
                candidate = onedrive_root / lnk
                if candidate.exists():
                    return candidate
        # Checa no diretório pai direto também
        parent = p.parent
        for lnk in cls.VAULT_LNK_NAMES:
            candidate = parent / lnk
            if candidate.exists():
                return candidate
        return None

    @classmethod
    def is_vault_locked(cls, path_str: str) -> bool:
        """Determina se o Cofre Pessoal está bloqueado (volume BitLocker desmontado)."""
        if not cls.is_vault_path(path_str):
            return False
        # Se for um caminho de cofre, mas o diretório não existe ou não pode ser listado
        if not os.path.exists(path_str):
            return True
        try:
            os.listdir(path_str)
            return False
        except (PermissionError, FileNotFoundError, OSError):
            return True

    @classmethod
    def request_unlock(cls, path_str: str) -> bool:
        """Dispara a janela do Windows para desbloqueio do Cofre Pessoal via .lnk."""
        lnk = cls.find_vault_lnk(path_str)
        if lnk and lnk.exists():
            try:
                os.startfile(str(lnk))
                return True
            except Exception as e:
                print(f"Erro ao tentar abrir atalho do cofre: {e}")
        return False

    @staticmethod
    def prevent_system_sleep():
        """Mantém a tela e o computador despertos durante o slideshow."""
        if sys.platform == 'win32':
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(
                    ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
                )
            except Exception:
                pass

    @staticmethod
    def restore_system_sleep():
        """Restaura as configurações de suspensão normais do sistema."""
        if sys.platform == 'win32':
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            except Exception:
                pass


def diagnose_path(path_str: str) -> Dict[str, Any]:
    """Executa diagnóstico completo sobre o caminho especificado e o estado do Cofre."""
    report: Dict[str, Any] = {
        "path": path_str,
        "exists": False,
        "is_dir": False,
        "is_vault": OneDriveVaultManager.is_vault_path(path_str),
        "vault_locked": False,
        "vault_lnk_found": None,
        "error": None,
        "images_count": 0,
        "dehydrated_count": 0,
        "hydrated_count": 0,
        "total_size_bytes": 0,
        "accessible": False,
        "advice": []
    }

    p = Path(path_str)
    lnk = OneDriveVaultManager.find_vault_lnk(path_str)
    if lnk:
        report["vault_lnk_found"] = str(lnk)

    try:
        report["exists"] = p.exists()
        if report["exists"]:
            report["is_dir"] = p.is_dir()
    except (PermissionError, FileNotFoundError, OSError) as e:
        report["error"] = str(e)

    if report["is_vault"]:
        report["vault_locked"] = OneDriveVaultManager.is_vault_locked(path_str)
        if report["vault_locked"]:
            report["advice"].append(
                "O Cofre Pessoal do OneDrive está BLOQUEADO. Abra o atalho do Cofre Pessoal ou autentique-se no OneDrive."
            )
            return report

    if not report["exists"]:
        report["advice"].append("O caminho especificado não existe.")
        return report

    if not report["is_dir"]:
        report["advice"].append("O caminho especificado não é um diretório.")
        return report

    # Testa listagem de arquivos
    try:
        found_images = []
        dehydrated = 0
        total_size = 0

        for root, _, files in os.walk(path_str):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in IMAGE_EXTENSIONS:
                    full_p = os.path.join(root, file)
                    found_images.append(full_p)
                    try:
                        total_size += os.path.getsize(full_p)
                    except OSError:
                        pass
                    if is_dehydrated_cloud_file(full_p):
                        dehydrated += 1

        report["accessible"] = True
        report["images_count"] = len(found_images)
        report["dehydrated_count"] = dehydrated
        report["hydrated_count"] = len(found_images) - dehydrated
        report["total_size_bytes"] = total_size

        if dehydrated > 0:
            report["advice"].append(
                f"Detectados {dehydrated} arquivos apenas em nuvem (Files On-Demand). "
                f"Eles serão baixados sob demanda ao serem abertos."
            )

        if report["images_count"] == 0:
            report["advice"].append("Nenhuma imagem suportada foi encontrada neste diretório.")

    except (PermissionError, OSError) as e:
        report["error"] = str(e)
        report["advice"].append(f"Erro de acesso ao inspecionar o diretório: {e}")

    return report


def main_diag():
    """CLI de diagnóstico rápido."""
    target = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\silva\OneDrive\Cofre Pessoal\Outras Imagens"
    print(f"\n=== DIAGNÓSTICO DO CAMINHO: {target} ===")
    diag = diagnose_path(target)
    for k, v in diag.items():
        if k != "advice":
            print(f" - {k}: {v}")
    if diag["advice"]:
        print("\nRecomendações / Orientações:")
        for adv in diag["advice"]:
            print(f" * {adv}")
    print("==========================================\n")


if __name__ == "__main__":
    main_diag()
