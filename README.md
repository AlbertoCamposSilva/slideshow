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
- **Sistema de Likes, Unlikes e Favoritos em Excel (.xlsx)**:
  - Registrado automaticamente na planilha centralizada: `~/slideshow_favoritos.xlsx`.
  - **Like (`L`)**: adiciona aos favoritos. Se a foto possuir Unlike, o primeiro toque cancela o unlike.
  - **Unlike (`U`)**: marca como unlike. Se a foto possuir Like, o primeiro toque desfaz o like.
  - **Ícones de Status Visuais**: exibe ❤️ (Like) ou ❌ (Unlike) no canto superior direito (alternável via tecla **`I`**).
  - **Filtro Trilateral (`F`)**: alterna entre *Todas as Fotos*, *Apenas Favoritas* e *Apenas Unlikes*.
  - **Exclusão em Lote (`Shift+Delete`)**: quando no modo de filtro *Apenas Unlikes*, permite listar e apagar permanentemente todas as fotos com unlike do disco após confirmação segura.
- **Persistência Automática de Preferências**:
  - Salva automaticamente as últimas configurações (velocidade, enquadramento, transição, ordem, legenda, tela cheia, fixação no topo e melhoria de baixa resolução) na aba `Configuracoes` da planilha do usuário.
  - Ao abrir o Slideshow novamente, suas preferências são restauradas instantaneamente.
- **Otimização Inteligente de Fotos em Baixa Resolução (`E`)**:
  - Reescalonamento Lanczos de alta precisão, filtro Unsharp Mask adaptativo, granulação analógica suave (Film Grain) e desfoque de fundo ambiente.
- **Janela de Ajuda Interativa (`F1`) e Controle com `Esc`**:
  - A tecla **`F1`** abre e fecha a documentação de atalhos (*Toggle*).
  - A tecla **`Esc`** fecha prioritariamente a janela de ajuda sem sair da tela cheia ou encerrar o slideshow.
- **Compilável com Nuitka e PyInstaller**: Scripts prontos para gerar executável standalone para Windows.

---

## 🚀 Instalação e Execução

### Usando o `uv` (Recomendado)
```bash
# Execução direta informando a pasta de imagens
uv run python -m slideshow -p "C:\Fotos"

# A partir de qualquer diretório no sistema
uv run --project "C:\caminho\para\slideshow" python -m slideshow -p "C:\Fotos"

# Com opções de enquadramento panorâmico, transição suave e tela cheia
uv run python -m slideshow -p "C:\Fotos" -d 4.0 --fullscreen -m panoramic -t crossfade

# Ao executar sem argumentos, o seletor gráfico de pastas abrirá automaticamente
uv run python -m slideshow
```

### Como Módulo em Outros Projetos
```python
from slideshow import run_slideshow

# Chamada simples
run_slideshow(folder=r"C:\MinhasFotos", delay=4.0, fullscreen=True)

# Chamada com opções avançadas e suporte a Cofre Pessoal
run_slideshow(
    folder=r"C:\MinhasFotos",
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
| **`F1`** | Abre / fecha a janela de ajuda flutuante (**Toggle**) |
| **`F11`** | Alterna o modo de Tela Cheia |
| **`Espaço`** | Pausar / Retomar apresentação |
| **`Seta Esquerda`** | Foto anterior (**Histórico Infinito**) |
| **`Seta Direita`** | Próxima foto |
| **`Seta Cima / Baixo`** | Acelerar / desacelerar intervalo |
| **`D`** | Digitar intervalo de tempo personalizado em segundos |
| **`O`** | Alternar ordem (Aleatória / Data / Alfabética) |
| **`L`** | Like ❤️ (Se possuir Unlike, o 1º aperto desfaz o unlike) |
| **`U`** | Unlike ❌ (Se possuir Like, o 1º aperto desfaz o like) |
| **`F`** | Alternar filtro: **Todas as Fotos** ➔ **Apenas Favoritas** ➔ **Apenas Unlikes** |
| **`I`** | Alternar exibição dos Ícones de Status (**❤️** / **❌**) no canto superior direito |
| **`Shift+Delete`** | Apagar permanentemente do disco todas as fotos com Unlike (ativo no filtro Unlikes) |
| **`E`** | Alternar Otimização de Baixa Resolução (Nitidez, Grão e Fundo Suave) |
| **`C`** | Alternar legenda (Oculta / Compacta / Detalhada) |
| **`M`** | Alternar modo de enquadramento (Ajustar / Zoom / Panorâmico) |
| **`X`** | Alternar estilo de transição (Suave Crossfade / Dura / Fade) |
| **`T` / `P`** | Alternar janela sempre no topo (Sempre Visível) |
| **`Esc`** | Fecha janela de ajuda (se aberta) / sai da tela cheia / encerra |

---

## 🔍 Ferramenta de Diagnóstico do Cofre OneDrive

Para testar e inspecionar o status de acesso e atributos dos arquivos de qualquer diretório:

```bash
uv run slideshow --check-vault -p "C:\caminho\para\pasta"
```

---

## 📦 Construção de Executáveis (.exe)

Consulte o arquivo [`COMO_COMPILAR.md`](COMO_COMPILAR.md) para instruções completas sobre compilação com **Nuitka** (preferencial) e **PyInstaller**.

---

## 📄 Licença
Distribuído sob a licença MIT. Veja `LICENSE` para mais detalhes.
