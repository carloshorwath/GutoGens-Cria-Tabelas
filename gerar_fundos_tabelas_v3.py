import os
import sys
import re
import time
import numpy as np
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from bs4 import BeautifulSoup
from html2image import Html2Image


# -------------------------------
# CONFIGURAÇÕES
# -------------------------------

VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080

PIP_WIDTH = 500
CONTENT_WIDTH = VIDEO_WIDTH - PIP_WIDTH - 150

CARD_MARGIN_LEFT = 70


# -------------------------------
# FUNDO FINAL (Pillow puro)
# -------------------------------

def criar_fundo_final(width, height):
    """Degradê radial + floor glow, 100% numpy"""
    cx, cy = width * 0.3, height * 0.5
    y, x = np.ogrid[:height, :width]
    dist = np.sqrt((x - cx)**2 + (y - cy)**2)
    max_dist = np.sqrt(width**2 + height**2) * 0.8
    ratio = np.clip(dist / max_dist, 0, 1)

    r = (58 * (1 - ratio)).astype(np.uint8)   # #3a
    g = (14 * (1 - ratio)).astype(np.uint8)   # #0e
    b = (14 * (1 - ratio)).astype(np.uint8)   # #0e

    arr = np.stack([r, g, b], axis=2)

    # Floor glow
    glow_h = int(height * 0.15)
    for row in range(glow_h):
        t = 1 - row / glow_h
        y_pos = height - 1 - row
        blend = t * 0.15
        arr[y_pos, :, 0] = np.clip(arr[y_pos, :, 0].astype(float) + 255 * blend, 0, 255).astype(np.uint8)
        arr[y_pos, :, 1] = np.clip(arr[y_pos, :, 1].astype(float) + 68 * blend, 0, 255).astype(np.uint8)
        arr[y_pos, :, 2] = np.clip(arr[y_pos, :, 2].astype(float) + 68 * blend, 0, 255).astype(np.uint8)

    return Image.fromarray(arr, 'RGB')


def encontrar_bbox_conteudo(img, limiar=3):
    """Encontra bounding box de pixels não-pretos (brilho > limiar)"""
    arr = np.array(img)[:, :, :3].astype(int)
    brilho = arr.max(axis=2)
    mask = brilho > limiar

    coords = np.argwhere(mask)
    if len(coords) == 0:
        return None

    y_min, x_min = coords.min(axis=0)
    y_max, x_max = coords.max(axis=0)
    return (x_min, y_min, x_max + 1, y_max + 1)


def _carregar_fonte(size, bold=False):
    nome = "segoeuib.ttf" if bold else "segoeui.ttf"
    fallback = "arialbd.ttf" if bold else "arial.ttf"
    try:
        return ImageFont.truetype(f"C:/Windows/Fonts/{nome}", size)
    except:
        try:
            return ImageFont.truetype(f"C:/Windows/Fonts/{fallback}", size)
        except:
            return ImageFont.load_default()


def desenhar_marca(img):
    """Desenha marca no topo (grande) e rodapé (pequeno + linha vermelha)"""
    draw = ImageDraw.Draw(img)
    texto = "CABEÇA DE INVESTIDOR"

    # --- TOPO: grande, canto superior direito ---
    font_top = _carregar_fonte(50, bold=True)
    bbox_top = draw.textbbox((0, 0), texto, font=font_top)
    tw_top = bbox_top[2] - bbox_top[0]

    x_top = VIDEO_WIDTH - 60 - tw_top
    y_top = 35

    draw.text((x_top, y_top), texto, font=font_top, fill=(255, 255, 255, 140))

    # --- RODAPÉ: pequeno + linha vermelha, canto inferior direito ---
    font_bot = _carregar_fonte(18, bold=False)
    bbox_bot = draw.textbbox((0, 0), texto, font=font_bot)
    tw_bot = bbox_bot[2] - bbox_bot[0]
    th_bot = bbox_bot[3] - bbox_bot[1]

    line_w = 100
    gap = 20
    margin_right = 100
    margin_bottom = 40

    total_w = tw_bot + gap + line_w
    bx = VIDEO_WIDTH - margin_right - total_w
    by = VIDEO_HEIGHT - margin_bottom - max(th_bot, 6)

    draw.text((bx, by), texto, font=font_bot, fill=(128, 128, 128))

    lx = bx + tw_bot + gap
    ly = by + th_bot // 2 - 3
    draw.rounded_rectangle([lx, ly, lx + line_w, ly + 6], radius=3, fill=(255, 68, 68))

    return img


# -------------------------------
# GERADOR
# -------------------------------

def gerar_fundos(html_path, output_dir):

    os.makedirs(output_dir, exist_ok=True)

    # Renderiza bem maior para nunca perder conteúdo
    render_w = 2200
    render_h = 1400

    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    style_tag = soup.find("style")
    original_css = style_tag.string if style_tag else ""

    # CSS: fundo PRETO + card solto no canto superior esquerdo
    card_css = f"""
    * {{
        box-sizing: border-box;
        margin:0;
        padding:0;
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }}

    html, body {{
        width:{render_w}px;
        height:{render_h}px;
        overflow:hidden;
        background: #000000;
        color: white;
    }}

    .table-content {{
        display: inline-block;
        background: rgb(15, 15, 15);
        padding: 40px 40px 30px 40px;
        border-radius: 40px;
        box-shadow: 0 40px 80px rgba(0,0,0,0.8);
        border: 1px solid rgba(255,255,255,0.12);
        border-top: 1px solid rgba(255,255,255,0.25);
        border-left: 1px solid rgba(255,255,255,0.18);
        margin: 10px;
    }}

    table {{
        width:100%;
        margin-top:20px;
        border-collapse: collapse;
        font-size: 30px;
        color: #eee;
    }}

    th {{
        font-size: 34px;
        text-align: left;
        padding: 25px 20px;
        border-bottom: 5px solid #ff4444;
        color: #ff6666;
        text-shadow: 0 0 15px rgba(255, 68, 68, 0.3);
    }}

    td {{
        padding: 22px 20px;
        border-bottom: 1px solid rgba(255,255,255,0.08);
    }}

    tr:nth-child(even) td {{
        background: rgba(255,255,255,0.02);
    }}

    h1 {{
        display:none;
    }}

    .table-title {{
        font-size: 50px;
        font-weight: 800;
        color: #ff6666;
        margin-bottom: 15px;
        text-transform: uppercase;
        letter-spacing: 4px;
        text-shadow: 0 0 30px rgba(255, 68, 68, 0.4);
    }}

    table.corte-gastos {{
        font-size: 22px !important;
    }}

    table.corte-gastos th {{
        font-size: 24px !important;
        padding: 15px 10px !important;
    }}

    table.corte-gastos td {{
        padding: 15px 10px !important;
    }}
    """

    tables = soup.find_all("table")
    print(f"\nTabelas encontradas: {len(tables)}")

    # Cria o fundo uma vez
    fundo = criar_fundo_final(VIDEO_WIDTH, VIDEO_HEIGHT)

    for i, table in enumerate(tables):

        title_p = table.find_previous_sibling("p", class_="table-title")
        title = title_p.get_text() if title_p else f"Tabela_{i+1}"

        clean_title = title.replace("(Salário Bruto)", "").replace("(Salário Líquido)", "").strip()
        safe_title = re.sub(r"[^\w\s-]", "", clean_title).strip().replace(" ", "_")
        filename = f"{i+1:02d}_{safe_title}.png"
        temp_filename = f"_temp_{filename}"

        html_render = f"""
        <html>
        <head>
        <style>
        {original_css}
        {card_css}
        </style>
        </head>
        <body>
        <div class="table-content">
            <p class="table-title">{clean_title}</p>
            {str(table)}
        </div>
        </body>
        </html>
        """

        # Recria instância por tabela (evita estado inválido do Chrome entre renders)
        hti = Html2Image(
            size=(render_w, render_h),
            output_path=output_dir,
            custom_flags=['--force-device-scale-factor=1']
        )

        # Passo 1: Renderiza card sobre fundo preto
        # Usa arquivo HTML temporário próprio para evitar problema de caminho com espaços
        html_temp_path = os.path.join(output_dir, f"_render_{i+1:02d}.html")
        with open(html_temp_path, "w", encoding="utf-8") as f:
            f.write(html_render)
        file_url = Path(html_temp_path).as_uri()
        hti.screenshot(url=file_url, save_as=temp_filename)

        # Aguarda até 10s para o arquivo ser gravado pelo Chrome (operação assíncrona)
        temp_path = os.path.join(output_dir, temp_filename)
        for _ in range(100):
            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 5000:
                break
            time.sleep(0.1)
        else:
            print(f"  AVISO: arquivo não gerado ou vazio: {temp_filename}")
            if os.path.exists(html_temp_path):
                os.remove(html_temp_path)
            continue

        raw_img = Image.open(temp_path).convert('RGB')

        # Passo 2: Encontra e recorta o conteúdo
        bbox = encontrar_bbox_conteudo(raw_img)
        if bbox is None:
            print(f"  AVISO: sem conteúdo em {filename}")
            os.remove(temp_path)
            if os.path.exists(html_temp_path):
                os.remove(html_temp_path)
            continue

        card_img = raw_img.crop(bbox)
        card_w, card_h = card_img.size

        # Passo 3: Cola o card centralizado verticalmente no fundo
        final = fundo.copy()

        paste_x = CARD_MARGIN_LEFT
        paste_y = (VIDEO_HEIGHT - card_h) // 2  # CENTRALIZADO

        # Segurança: não sair da imagem
        paste_y = max(20, min(paste_y, VIDEO_HEIGHT - card_h - 20))

        final.paste(card_img, (paste_x, paste_y))

        # Passo 4: Footer direto com Pillow
        desenhar_marca(final)

        # Passo 5: Salva
        final.save(os.path.join(output_dir, filename))
        os.remove(temp_path)
        os.remove(html_temp_path)

        print(f"  OK: {filename} (card {card_w}x{card_h}, y={paste_y})")

    print("\nConcluído!")
    print("Imagens em:", output_dir)


# -------------------------------
# MAIN
# -------------------------------

if __name__ == "__main__":

    BASE_DIR = Path(__file__).parent

    HTML_FILE = BASE_DIR / "index.html"
    OUTPUT = BASE_DIR / "Outputs_Tabelas_v3"

    if not HTML_FILE.exists():
        print("HTML não encontrado")
        sys.exit()

    gerar_fundos(HTML_FILE, OUTPUT)
