# Slideshow Pro

Um apresentador de slides moderno, resiliente, modular e extensível para Windows e Linux, com suporte aprofundado ao **Cofre Pessoal (Personal Vault) do OneDrive**, transições audiovisuais cinematográficas e sistema de favoritos em Excel.

---

## 🌟 Principais Recursos

- **Módulo Python Reutilizável**: Instale via `pip`/`uv` ou importe diretamente em outros programas (`from slideshow import run_slideshow`).
- **Resiliência ao Cofre Pessoal do OneDrive**:
  - Detecção inteligente do estado do cofre (montado vs. bloqueado/desmontado).
  - Identificação de arquivos em nuvem (*Files On-Demand* desidratados).
  - **Buffer em RAM condicional com teto de 1 GB**: lê fotos para a memória na inicialização se estiverem no cofre, evitando que o fechamento por inatividade (20 min) do BitLocker interrompa a reprodução.
  - Se for uma pasta comum, lê sob demanda do disco com consumo mínimo de memória.
- **Transições Suaves**:
  - **Crossfade**: Dissolvência suave entre imagens via interpolação de canais.
  - **Dura**: Corte seco tradicional.
  - **Fade to Black**: Esmaecimento para o preto.
- **Modos de Enquadramento**:
  - **Ajustar (Fit)**: Imagem inteira visível sem distorção.
  - **Zoom / Preencher (Fill)**: Cobre 100% da janela centralizada.
  - **Panorâmico (Ken Burns Pan & Scan)**: A foto preenche a janela e se move suavemente de uma borda a outra durante o slide.
- **Histórico Infinito no Modo Aleatório**:
  - O botão de voltar (Seta Esquerda) funciona retroativamente por toda a trilha de fotos exibidas, sem limite.
- **Sistema de Likes / Favoritos em Excel (.xlsx)**:
  - Pressione **`L`** para curtir/descurtir fotos.
  - Gravado automaticamente na planilha centralizada: `~/slideshow_favoritos.xlsx`.
  - Pressione **`F`** para filtrar e exibir apenas fotos favoritas.
- **Legenda Configurável**:
  - Pressione **`C`** para alternar entre: Oculta, Compacta (`[1/150] foto.jpg ❤️`) ou Detalhada (pasta, resolução, data).
- **Controle de Tempo Interativo**:
  - Pressione **`D`** para digitar diretamente o intervalo em segundos (ex: `2.5`, `5`, `10`).
- **Tela Cheia com F11**: Alterna instantaneamente com a tecla **F11**.
- **Janela de Ajuda com F1**: Tela flutuante com todos os atalhos disponíveis.
- **Compilável com Nuitka e PyInstaller**: Scripts prontos para gerar executável standalone para Windows.

---

## 🚀 Instalação e Execução

### Usando o `uv` (Recomendado)
```bash
# Executar diretamente do repositório
uv run slideshow

# Ou com opções específicas
uv run slideshow -p "C:\Fotos" -d 4.5 --fullscreen -m panoramic
```

### Como Módulo em Outros Projetos
```python
from slideshow import run_slideshow

# Chamada simples
run_slideshow(folder=r"C:\MinhasFotos", delay=4.0, fullscreen=True)

# Chamada com opções avançadas
run_slideshow(
    folder=r"C:\Users\silva\OneDrive\Cofre Pessoal\Outras Imagens",
    delay=5.0,
    framing="panoramic",
    transition="crossfade",
    order="random",
    ram_limit_mb=1024
)
```

---

## ⌨️ Atalhos de Teclado

| Tecla | Ação |
| :--- | :--- |
| **`F1`** | Abre / fecha a janela de ajuda flutuante |
| **`F11`** | Alterna o modo de Tela Cheia |
| **`Espaço`** | Pausar / Retomar apresentação |
| **`Seta Esquerda`** | Foto anterior (**Histórico Infinito**) |
| **`Seta Direita`** | Próxima foto |
| **`Seta Cima / Baixo`** | Acelerar / desacelerar intervalo |
| **`D`** | Digitar intervalo de tempo personalizado em segundos |
| **`O`** | Alternar ordem (Aleatória / Data / Alfabética) |
| **`L`** | Dar Like / Descurtir (salva em `slideshow_favoritos.xlsx`) |
| **`F`** | Filtrar: exibir apenas fotos favoritas |
| **`C`** | Alternar legenda (Oculta / Compacta / Detalhada) |
| **`M`** | Alternar modo de enquadramento (Ajustar / Zoom / Panorâmico) |
| **`X`** | Alternar estilo de transição (Suave Crossfade / Dura / Fade) |
| **`T` / `P`** | Alternar janela sempre no topo (Sempre Visível) |
| **`Esc`** | Sair da tela cheia ou fechar o programa |

---

## 🔍 Ferramenta de Diagnóstico do Cofre OneDrive

Para testar e inspecionar o status de acesso e atributos dos arquivos de qualquer diretório:

```bash
uv run slideshow --check-vault -p "C:\Users\silva\OneDrive\Cofre Pessoal\Outras Imagens"
```

---

## 📦 Construção de Executáveis (.exe)

Consulte o arquivo [`COMO_COMPILAR.md`](COMO_COMPILAR.md) para instruções completas sobre compilação com **Nuitka** (preferencial) e **PyInstaller**.

---

## 📄 Licença
Distribuído sob a licença MIT. Veja `LICENSE` para mais detalhes.
