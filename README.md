# Gerador de Tabelas para YouTube — Cabeça de Investidor

Gera imagens PNG profissionais (1920x1080) a partir de tabelas HTML, para uso como assets visuais em vídeos do YouTube.

## Funcionalidades

- **GUI com preview ao vivo** da imagem final (960x540)
- **Seletor de tabela** — processa todas as tabelas do `index.html`
- **Posição X/Y e escala por tabela** — cada tabela lembra suas próprias configurações
- **Largura de colunas por tabela** — sliders individuais por coluna
- **Temas prontos**: Dark Red, Dark Blue, Dark Green, Dark Purple
- **Cor de fundo e cor de destaque** customizáveis via color picker
- **Layouts**: Left, Center, Right, Fullscreen
- **Cantos arredondados** via máscara alpha (Pillow)
- **Sombra suave** (drop shadow com Gaussian blur)
- **Linha decorativa** acima do título de cada tabela
- **Numeração automática de linhas** (coluna #)
- **Destaque automático de linha total** (verde/vermelho conforme valor)
- **Batch export**: gera todas as tabelas × todos os temas em subpastas
- **Persistência de configurações** em `Outputs/settings.json`
- **Modo CLI** sem GUI

## Requisitos

```bash
conda activate Legendasv2
pip install pillow beautifulsoup4 html2image numpy
```

Requer Google Chrome instalado (usado pelo html2image para renderizar as tabelas).

## Como usar

### GUI (modo padrão)
```bash
python gerar_fundos_tabelas_v3.py
```

### CLI (sem GUI)
```bash
python gerar_fundos_tabelas_v3.py --no-gui
python gerar_fundos_tabelas_v3.py --no-gui --theme "Dark Blue" --layout Center
python gerar_fundos_tabelas_v3.py --no-gui --table 2          # só a tabela 2
python gerar_fundos_tabelas_v3.py --no-gui --table "Diagnóstico"  # por nome
python gerar_fundos_tabelas_v3.py --no-gui --output-dir Saida
```

### Flags CLI disponíveis
| Flag | Valores | Default |
|------|---------|---------|
| `--no-gui` | — | desligado |
| `--theme` | Dark Red, Dark Blue, Dark Green, Dark Purple | Dark Red |
| `--layout` | Left, Center, Right, Fullscreen | Left |
| `--output-dir` | qualquer caminho | Outputs |
| `--table` | índice numérico ou substring do nome | todas |

## Estrutura de arquivos

```
Cria Tabelas/
├── gerar_fundos_tabelas_v3.py   # script principal
├── index.html                   # tabelas e script do vídeo
├── README.md
└── Outputs/
    ├── settings.json            # configurações salvas por tabela
    ├── Dark_Red/
    │   ├── 01_Tabela.png
    │   └── ...
    ├── Dark_Blue/
    ├── Dark_Green/
    └── Dark_Purple/
```

## Como funciona internamente

1. **Leitura do HTML** — BeautifulSoup extrai as tabelas do `index.html`
2. **Renderização** — html2image (Chrome headless) converte cada tabela em PNG temporário via `file://` URL (necessário para evitar `ERR_FILE_NOT_FOUND` no Windows com espaços no caminho)
3. **Composição** — Pillow recorta o card, aplica máscara de cantos arredondados, sombra, e cola no fundo com gradiente radial
4. **Branding** — texto "CABEÇA DE INVESTIDOR" adicionado no topo e rodapé via Pillow

## Notas técnicas

- O html2image salva arquivos de forma assíncrona no Windows — o script aguarda até 10s com polling antes de abrir o PNG gerado
- Uma instância nova do `Html2Image` é criada por tabela para evitar estado inválido do Chrome entre renders
- Configurações por tabela (X, Y, escala, larguras de coluna) são salvas automaticamente em `Outputs/settings.json`
