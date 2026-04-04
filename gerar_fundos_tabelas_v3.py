import os
import sys
import re
import time
import argparse
import threading
import json
import numpy as np
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageTk
from bs4 import BeautifulSoup
from html2image import Html2Image

import tkinter as tk
from tkinter import ttk, colorchooser, messagebox

# -------------------------------
# CONFIGURAÇÕES BASE
# -------------------------------

VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080

THEMES = {
    "Dark Red": {"bg_center": (58, 14, 14), "accent": "#ff4444"},
    "Dark Blue": {"bg_center": (14, 24, 58), "accent": "#4488ff"},
    "Dark Green": {"bg_center": (14, 58, 24), "accent": "#44ff44"},
    "Dark Purple": {"bg_center": (48, 14, 58), "accent": "#b844ff"},
}

LAYOUTS = {
    "Left": {"x_ratio": 0.036, "y_ratio": 0.5},
    "Center": {"x_ratio": 0.5, "y_ratio": 0.5},
    "Right": {"x_ratio": 0.964, "y_ratio": 0.5},
    "Fullscreen": {"x_ratio": 0.5, "y_ratio": 0.5}
}

class TableImageGenerator:
    def __init__(self, output_dir="Outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.render_w = 2200
        self.render_h = 1400

    def criar_fundo_final(self, width, height, center_color):
        """Degradê radial + floor glow, 100% numpy"""
        cx, cy = width * 0.3, height * 0.5
        y, x = np.ogrid[:height, :width]
        dist = np.sqrt((x - cx)**2 + (y - cy)**2)
        max_dist = np.sqrt(width**2 + height**2) * 0.8
        ratio = np.clip(dist / max_dist, 0, 1)

        cr, cg, cb = center_color

        r = (cr * (1 - ratio)).astype(np.uint8)
        g = (cg * (1 - ratio)).astype(np.uint8)
        b = (cb * (1 - ratio)).astype(np.uint8)

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

    def encontrar_bbox_conteudo(self, img, limiar=3):
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

    def _carregar_fonte(self, size, bold=False):
        nome = "segoeuib.ttf" if bold else "segoeui.ttf"
        fallback = "arialbd.ttf" if bold else "arial.ttf"
        try:
            return ImageFont.truetype(f"C:/Windows/Fonts/{nome}", size)
        except:
            try:
                return ImageFont.truetype(f"C:/Windows/Fonts/{fallback}", size)
            except:
                return ImageFont.load_default()

    def desenhar_marca(self, img, accent_color):
        """Desenha marca no topo (grande) e rodapé (pequeno + linha)"""
        draw = ImageDraw.Draw(img)
        texto = "CABEÇA DE INVESTIDOR"

        # --- TOPO: grande, canto superior direito ---
        font_top = self._carregar_fonte(50, bold=True)
        bbox_top = draw.textbbox((0, 0), texto, font=font_top)
        tw_top = bbox_top[2] - bbox_top[0]

        x_top = VIDEO_WIDTH - 60 - tw_top
        y_top = 35

        draw.text((x_top, y_top), texto, font=font_top, fill=(255, 255, 255, 140))

        # --- RODAPÉ: pequeno + linha, canto inferior direito ---
        font_bot = self._carregar_fonte(18, bold=False)
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

        # Convert accent_color from hex to rgb
        accent_rgb = tuple(int(accent_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))

        draw.rounded_rectangle([lx, ly, lx + line_w, ly + 6], radius=3, fill=accent_rgb)

        return img

    def create_rounded_mask(self, width, height, radius):
        mask = Image.new('L', (width, height), 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([0, 0, width, height], radius, fill=255)
        return mask

    def process_table_html(self, html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")

        style_tag = soup.find("style")
        original_css = style_tag.string if style_tag else ""

        tables = soup.find_all("table")
        processed_tables = []

        for i, table in enumerate(tables):
            # 4. Automatic visual improvements: row numbers and highlighting
            # Clone the table so we don't modify the original soup structure globally
            import copy
            table_copy = copy.copy(table)

            # highlight total row
            for row in table_copy.find_all("tr"):
                text = row.get_text().lower()
                if any(word in text for word in ['total', 'sobra', 'resultado', 'saldo']):
                    # simple check: if any cell has '-', make it red, else green.
                    # Usually applies to the last column, but let's check all
                    cells = row.find_all(["td", "th"])
                    is_negative = any("-" in c.get_text() for c in cells)
                    highlight_color = "#ff4444" if is_negative else "#44ff44"
                    for cell in cells:
                        cell['style'] = f"color: {highlight_color} !important;"

            # row numbers
            thead = table_copy.find("thead")
            if thead:
                for tr in thead.find_all("tr"):
                    new_th = soup.new_tag("th")
                    new_th.string = "#"
                    tr.insert(0, new_th)

            tbody = table_copy.find("tbody") or table_copy
            idx = 1
            for tr in tbody.find_all("tr"):
                if tr.parent.name == "thead": continue
                if not tr.find("td") and tr.find("th"): continue # inner header
                new_td = soup.new_tag("td")
                new_td.string = str(idx)
                # Keep odd/even background style alignment by not adding inline styles unless necessary,
                # but center the number
                new_td['style'] = "text-align: center; color: #888; font-weight: bold;"
                tr.insert(0, new_td)
                idx += 1

            title_p = table.find_previous_sibling("p", class_="table-title")
            title = title_p.get_text() if title_p else f"Tabela_{i+1}"

            clean_title = title.replace("(Salário Bruto)", "").replace("(Salário Líquido)", "").strip()
            safe_title = re.sub(r"[^\w\s-]", "", clean_title).strip().replace(" ", "_")

            processed_tables.append({
                "index": i,
                "title": clean_title,
                "safe_title": safe_title,
                "html": str(table_copy)
            })

        return original_css, processed_tables

    def generate_single_image(self, table_data, original_css, settings, save_path=None):
        """
        Generates a single image with given settings.
        Returns the PIL Image. If save_path is provided, saves it.
        settings: dict containing theme, layout, pos_x, pos_y, scale, accent_color, bg_center
        """
        accent_color = settings['accent_color']
        bg_center = settings['bg_center']

        # accent adjusted colors for css
        # lighten accent for titles
        # This is a bit hacky, but works for our simple hex colors
        r, g, b = tuple(int(accent_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        accent_light = f"rgba({min(r+34,255)}, {min(g+34,255)}, {min(b+34,255)}, 1.0)"
        accent_shadow = f"rgba({r}, {g}, {b}, 0.3)"

        # Decorative line
        decorative_line_css = f"""
        .title-container {{
            position: relative;
            margin-bottom: 15px;
        }}
        .decorative-line {{
            width: 100px;
            height: 5px;
            background-color: {accent_color};
            border-radius: 3px;
            margin-bottom: 10px;
        }}
        """

        card_css = f"""
        * {{
            box-sizing: border-box;
            margin:0;
            padding:0;
            font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }}

        html, body {{
            width:{self.render_w}px;
            height:{self.render_h}px;
            overflow:hidden;
            background: #000000;
            color: white;
        }}

        .table-content {{
            display: inline-block;
            background: rgb(15, 15, 15);
            padding: 40px 40px 30px 40px;
            /* We handle border-radius in Pillow for proper antialiasing and alpha */
            border-radius: 40px;
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
            border-bottom: 5px solid {accent_color};
            color: {accent_light};
            text-shadow: 0 0 15px {accent_shadow};
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
            color: {accent_light};
            text-transform: uppercase;
            letter-spacing: 4px;
            text-shadow: 0 0 30px {accent_shadow};
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
        {decorative_line_css}
        """

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
            <div class="title-container">
                <div class="decorative-line"></div>
                <p class="table-title">{table_data['title']}</p>
            </div>
            {table_data['html']}
        </div>
        </body>
        </html>
        """

        temp_filename = f"_temp_{table_data['index']}.png"
        html_temp_path = os.path.join(self.output_dir, f"_render_{table_data['index']}.html")
        with open(html_temp_path, "w", encoding="utf-8") as f:
            f.write(html_render)

        hti = Html2Image(
            size=(self.render_w, self.render_h),
            output_path=self.output_dir,
            custom_flags=['--force-device-scale-factor=1']
        )

        file_url = Path(html_temp_path).resolve().as_uri()
        hti.screenshot(url=file_url, save_as=temp_filename)

        temp_path = os.path.join(self.output_dir, temp_filename)
        for _ in range(100):
            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 5000:
                break
            time.sleep(0.1)
        else:
            print(f"  AVISO: arquivo não gerado ou vazio: {temp_filename}")
            if os.path.exists(html_temp_path):
                os.remove(html_temp_path)
            return None

        raw_img = Image.open(temp_path).convert('RGB')

        bbox = self.encontrar_bbox_conteudo(raw_img)
        if bbox is None:
            os.remove(temp_path)
            os.remove(html_temp_path)
            return None

        # Fix bbox to avoid cropping shadows or borders (add small padding)
        pad = 5
        x_min = max(0, bbox[0] - pad)
        y_min = max(0, bbox[1] - pad)
        x_max = min(raw_img.width, bbox[2] + pad)
        y_max = min(raw_img.height, bbox[3] + pad)

        card_img = raw_img.crop((x_min, y_min, x_max, y_max))

        # cleanup
        raw_img.close()
        os.remove(temp_path)
        os.remove(html_temp_path)

        # Scale card
        layout = settings.get('layout', 'Left')
        scale = settings.get('scale', 1.0)

        if layout == 'Fullscreen':
            # override scale to make width fit the screen with 80px margin (40px each side)
            target_width = VIDEO_WIDTH - 80
            scale = target_width / card_img.width

        if scale != 1.0:
            new_size = (int(card_img.width * scale), int(card_img.height * scale))
            # Use LANCZOS for resizing
            resample_filter = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
            card_img = card_img.resize(new_size, resample_filter)

        card_w, card_h = card_img.size

        # Apply rounded corners via mask
        radius = int(40 * scale)
        mask = self.create_rounded_mask(card_w, card_h, radius)
        card_rgba = Image.new('RGBA', card_img.size)
        card_rgba.paste(card_img, (0, 0))
        card_rgba.putalpha(mask)

        # Create Drop shadow
        shadow_offset = (0, int(20 * scale))
        shadow_blur = int(30 * scale)
        # Extend bounds for shadow
        pad_shadow = shadow_blur * 2
        shadow_canvas_w = card_w + pad_shadow * 2
        shadow_canvas_h = card_h + pad_shadow * 2

        shadow = Image.new('RGBA', (shadow_canvas_w, shadow_canvas_h), (0, 0, 0, 0))
        shadow_mask_img = Image.new('RGBA', (card_w, card_h), (0, 0, 0, 180)) # darker shadow
        shadow_mask_img.putalpha(mask)
        shadow.paste(shadow_mask_img, (pad_shadow, pad_shadow), shadow_mask_img)
        shadow = shadow.filter(ImageFilter.GaussianBlur(shadow_blur))

        # Background
        fundo = self.criar_fundo_final(VIDEO_WIDTH, VIDEO_HEIGHT, bg_center)

        # Positioning
        x_ratio = LAYOUTS[layout]['x_ratio']
        y_ratio = LAYOUTS[layout]['y_ratio']

        # Adjust for manual offsets
        offset_x = settings.get('offset_x', 0)
        offset_y = settings.get('offset_y', 0)

        # Default positions (centered on anchor)
        if layout == 'Left':
            paste_x = 70 # fixed margin as before
        elif layout == 'Right':
            paste_x = VIDEO_WIDTH - card_w - 70
        else:
            paste_x = (VIDEO_WIDTH - card_w) // 2

        paste_y = (VIDEO_HEIGHT - card_h) // 2

        paste_x += offset_x
        paste_y += offset_y

        # Paste Shadow
        shadow_x = paste_x - pad_shadow + shadow_offset[0]
        shadow_y = paste_y - pad_shadow + shadow_offset[1]

        shadow_x = max(0, shadow_x)
        shadow_y = max(0, shadow_y)

        # Composite alpha requires base to be RGBA
        fundo_rgba = fundo.convert("RGBA")
        fundo_rgba.paste(shadow, (shadow_x, shadow_y), shadow)
        fundo_rgba.paste(card_rgba, (paste_x, paste_y), card_rgba)

        final = fundo_rgba.convert("RGB")

        # Footer
        final = self.desenhar_marca(final, accent_color)

        if save_path:
            final.save(save_path)

        return final

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-gui', action='store_true')
    parser.add_argument('--html', default='index.html')
    args = parser.parse_args()
    print("Testing functionality...")
    generator = TableImageGenerator()
    original_css, tables = generator.process_table_html(args.html)
    print(f"Loaded {len(tables)} tables")

# -------------------------------
# GUI
# -------------------------------

class AppGUI:
    def __init__(self, root, generator, original_css, tables):
        self.root = root
        self.generator = generator
        self.original_css = original_css
        self.tables = tables

        self.root.title("Gerador de Tabelas para YouTube")

        # State
        self.current_table_idx = 0
        self.theme_name = tk.StringVar(value="Dark Red")
        self.layout_var = tk.StringVar(value="Left")

        self.offset_x = tk.IntVar(value=0)
        self.offset_y = tk.IntVar(value=0)
        self.scale_var = tk.DoubleVar(value=1.0)

        self.table_settings = {}
        for t in self.tables:
            self.table_settings[str(t["index"])] = {
                'offset_x': 0,
                'offset_y': 0,
                'scale': 1.0
            }

        self.bg_color_center = list(THEMES["Dark Red"]["bg_center"])
        self.accent_color = THEMES["Dark Red"]["accent"]

        self._load_settings()

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._update_preview_delayed()

    def _load_settings(self):
        settings_file = self.generator.output_dir / "settings.json"
        if settings_file.exists():
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "theme" in data and data["theme"] in THEMES:
                        self.theme_name.set(data["theme"])
                        self.bg_color_center = list(THEMES[data["theme"]]["bg_center"])
                        self.accent_color = THEMES[data["theme"]]["accent"]
                    if "layout" in data and data["layout"] in LAYOUTS:
                        self.layout_var.set(data["layout"])
                    if "table_settings" in data:
                        for k, v in data["table_settings"].items():
                            if k in self.table_settings:
                                self.table_settings[k].update(v)
                        # Apply to currently selected table (index 0 by default)
                        first_idx = str(self.tables[self.current_table_idx]["index"])
                        self.offset_x.set(self.table_settings[first_idx]['offset_x'])
                        self.offset_y.set(self.table_settings[first_idx]['offset_y'])
                        self.scale_var.set(self.table_settings[first_idx]['scale'])
            except Exception as e:
                print(f"Erro ao carregar configurações: {e}")

    def _on_closing(self):
        # Save current table settings
        active_idx = str(self.tables[self.current_table_idx]["index"])
        self.table_settings[active_idx]['offset_x'] = self.offset_x.get()
        self.table_settings[active_idx]['offset_y'] = self.offset_y.get()
        self.table_settings[active_idx]['scale'] = self.scale_var.get()

        data = {
            "theme": self.theme_name.get(),
            "layout": self.layout_var.get(),
            "table_settings": self.table_settings
        }
        settings_file = self.generator.output_dir / "settings.json"
        try:
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Erro ao salvar configurações: {e}")
        self.root.destroy()

    def _build_ui(self):
        # Main frames
        left_frame = ttk.Frame(self.root, padding=10)
        left_frame.pack(side=tk.LEFT, fill=tk.Y)

        right_frame = ttk.Frame(self.root, padding=10)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # --- LEFT FRAME (Controls) ---

        # Table Selector
        ttk.Label(left_frame, text="Tabela:").pack(anchor=tk.W)
        self.table_listbox = tk.Listbox(left_frame, height=8, exportselection=False)
        for t in self.tables:
            self.table_listbox.insert(tk.END, t["title"])
        self.table_listbox.select_set(0)
        self.table_listbox.pack(fill=tk.X, pady=(0, 10))
        self.table_listbox.bind('<<ListboxSelect>>', self._on_table_select)

        # Themes
        ttk.Label(left_frame, text="Tema (Presets):").pack(anchor=tk.W)
        theme_frame = ttk.Frame(left_frame)
        theme_frame.pack(fill=tk.X, pady=(0, 10))
        for t_name in THEMES.keys():
            ttk.Radiobutton(theme_frame, text=t_name, variable=self.theme_name, value=t_name, command=self._on_theme_change).pack(anchor=tk.W)

        # Custom Colors
        color_frame = ttk.Frame(left_frame)
        color_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(color_frame, text="Cor Fundo (Centro)", command=self._pick_bg_color).pack(fill=tk.X, pady=2)
        ttk.Button(color_frame, text="Cor Destaque (Acento)", command=self._pick_accent_color).pack(fill=tk.X, pady=2)

        # Layout
        ttk.Label(left_frame, text="Layout:").pack(anchor=tk.W)
        layout_frame = ttk.Frame(left_frame)
        layout_frame.pack(fill=tk.X, pady=(0, 10))
        for l_name in LAYOUTS.keys():
            ttk.Radiobutton(layout_frame, text=l_name, variable=self.layout_var, value=l_name, command=self._on_setting_change).pack(side=tk.LEFT, padx=2)

        # Sliders
        self.lbl_offset_x = ttk.Label(left_frame, text=f"Offset X: {self.offset_x.get()}")
        self.lbl_offset_x.pack(anchor=tk.W)
        ttk.Scale(left_frame, from_=-1000, to=1000, variable=self.offset_x, command=self._on_slider_change).pack(fill=tk.X)

        self.lbl_offset_y = ttk.Label(left_frame, text=f"Offset Y: {self.offset_y.get()}")
        self.lbl_offset_y.pack(anchor=tk.W)
        ttk.Scale(left_frame, from_=-500, to=500, variable=self.offset_y, command=self._on_slider_change).pack(fill=tk.X)

        self.lbl_scale = ttk.Label(left_frame, text=f"Escala: {self.scale_var.get():.2f}x")
        self.lbl_scale.pack(anchor=tk.W)
        ttk.Scale(left_frame, from_=0.5, to=2.0, variable=self.scale_var, command=self._on_slider_change).pack(fill=tk.X, pady=(0, 20))

        # Buttons
        self.btn_save = ttk.Button(left_frame, text="Salvar Esta (Save This)", command=self._save_current_threaded)
        self.btn_save.pack(fill=tk.X, pady=5)
        self.btn_batch = ttk.Button(left_frame, text="Gerar Todas (Batch Export)", command=self._batch_export_threaded)
        self.btn_batch.pack(fill=tk.X, pady=5)

        # Status Label
        self.status_label = ttk.Label(left_frame, text="Status: Pronto")
        self.status_label.pack(anchor=tk.W, pady=10)

        # Controls list for state toggling
        self.controls = [
            self.table_listbox,
            self.btn_save,
            self.btn_batch,
        ]

        # --- RIGHT FRAME (Preview) ---
        self.canvas_w = 960
        self.canvas_h = 540
        self.preview_canvas = tk.Canvas(right_frame, width=self.canvas_w, height=self.canvas_h, bg="black")
        self.preview_canvas.pack(anchor=tk.CENTER)
        self.preview_image_id = self.preview_canvas.create_image(0, 0, anchor=tk.NW)

        self._pending_update = None
        self._is_rendering = False

    def _set_ui_state(self, state, status_text):
        self.status_label.config(text=f"Status: {status_text}")
        tk_state = tk.NORMAL if state == 'normal' else tk.DISABLED
        for control in self.controls:
            try:
                control.config(state=tk_state)
            except tk.TclError:
                pass # Listbox might need different state handling or be ok

    def _on_table_select(self, event):
        sel = self.table_listbox.curselection()
        if sel:
            # Salva configurações atuais para a tabela antiga
            old_idx = str(self.tables[self.current_table_idx]["index"])
            self.table_settings[old_idx]['offset_x'] = self.offset_x.get()
            self.table_settings[old_idx]['offset_y'] = self.offset_y.get()
            self.table_settings[old_idx]['scale'] = self.scale_var.get()

            self.current_table_idx = sel[0]
            new_idx = str(self.tables[self.current_table_idx]["index"])

            # Carrega configurações salvas para a nova tabela
            self.offset_x.set(self.table_settings[new_idx]['offset_x'])
            self.offset_y.set(self.table_settings[new_idx]['offset_y'])
            self.scale_var.set(self.table_settings[new_idx]['scale'])

            self.lbl_offset_x.config(text=f"Offset X: {self.offset_x.get()}")
            self.lbl_offset_y.config(text=f"Offset Y: {self.offset_y.get()}")
            self.lbl_scale.config(text=f"Escala: {self.scale_var.get():.2f}x")

            self._update_preview_delayed()

    def _on_theme_change(self):
        t = self.theme_name.get()
        self.bg_color_center = list(THEMES[t]["bg_center"])
        self.accent_color = THEMES[t]["accent"]
        self._update_preview_delayed()

    def _pick_bg_color(self):
        color = colorchooser.askcolor(title="Escolha a Cor do Fundo", color=tuple(self.bg_color_center))
        if color[0]:
            self.bg_color_center = [int(c) for c in color[0]]
            self._update_preview_delayed()

    def _pick_accent_color(self):
        color = colorchooser.askcolor(title="Escolha a Cor de Destaque", color=self.accent_color)
        if color[1]:
            self.accent_color = color[1]
            self._update_preview_delayed()

    def _on_slider_change(self, event):
        self.lbl_offset_x.config(text=f"Offset X: {self.offset_x.get()}")
        self.lbl_offset_y.config(text=f"Offset Y: {self.offset_y.get()}")
        self.lbl_scale.config(text=f"Escala: {self.scale_var.get():.2f}x")
        self._update_preview_delayed()

    def _on_setting_change(self):
        self._update_preview_delayed()

    def _update_preview_delayed(self):
        if self._pending_update is not None:
            self.root.after_cancel(self._pending_update)
        # Wait 500ms before rendering to avoid lag while dragging sliders
        self._pending_update = self.root.after(500, self._render_preview_threaded)

    def _get_current_settings(self):
        return {
            "layout": self.layout_var.get(),
            "offset_x": self.offset_x.get(),
            "offset_y": self.offset_y.get(),
            "scale": self.scale_var.get(),
            "bg_center": self.bg_color_center,
            "accent_color": self.accent_color
        }

    def _render_preview_threaded(self):
        if self._is_rendering:
            return
        self._pending_update = None
        threading.Thread(target=self._render_preview, daemon=True).start()

    def _render_preview(self):
        self._is_rendering = True
        self.root.after(0, lambda: self._set_ui_state('disabled', 'Renderizando Preview...'))

        settings = self._get_current_settings()
        table_data = self.tables[self.current_table_idx]

        print(f"Gerando preview para: {table_data['title']}...")
        img = self.generator.generate_single_image(table_data, self.original_css, settings)
        if img:
            # Scale down for preview
            preview_img = img.resize((self.canvas_w, self.canvas_h), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)

            def update_canvas():
                self.tk_img = ImageTk.PhotoImage(preview_img)
                self.preview_canvas.itemconfig(self.preview_image_id, image=self.tk_img)
            self.root.after(0, update_canvas)
        else:
            print("Falha ao gerar preview.")

        self._is_rendering = False
        self.root.after(0, lambda: self._set_ui_state('normal', 'Pronto'))

    def _save_current_threaded(self):
        if self._is_rendering:
            return
        threading.Thread(target=self._save_current, daemon=True).start()

    def _save_current(self):
        # Garante que os valores atuais estão salvos para a tabela ativa
        active_idx = str(self.tables[self.current_table_idx]["index"])
        self.table_settings[active_idx]['offset_x'] = self.offset_x.get()
        self.table_settings[active_idx]['offset_y'] = self.offset_y.get()
        self.table_settings[active_idx]['scale'] = self.scale_var.get()

        settings = self._get_current_settings()
        table_data = self.tables[self.current_table_idx]
        theme_folder = self.theme_name.get().replace(" ", "_")
        out_dir = self.generator.output_dir / theme_folder
        out_dir.mkdir(exist_ok=True)

        filename = f"{table_data['index']+1:02d}_{table_data['safe_title']}.png"
        save_path = out_dir / filename

        print(f"Salvando {save_path}...")
        self._is_rendering = True
        self.root.after(0, lambda: self._set_ui_state('disabled', 'Salvando Imagem...'))

        self.generator.generate_single_image(table_data, self.original_css, settings, save_path=str(save_path))

        self._is_rendering = False
        self.root.after(0, lambda: self._set_ui_state('normal', 'Pronto'))
        self.root.after(0, lambda: messagebox.showinfo("Sucesso", f"Imagem salva em:\n{save_path}"))

    def _batch_export_threaded(self):
        if self._is_rendering:
            return
        threading.Thread(target=self._batch_export, daemon=True).start()

    def _batch_export(self):
        print("Iniciando batch export...")
        self._is_rendering = True
        self.root.after(0, lambda: self._set_ui_state('disabled', 'Exportando em Lote...'))
        # Garante que os valores atuais estão salvos para a tabela ativa
        active_idx = str(self.tables[self.current_table_idx]["index"])
        self.table_settings[active_idx]['offset_x'] = self.offset_x.get()
        self.table_settings[active_idx]['offset_y'] = self.offset_y.get()
        self.table_settings[active_idx]['scale'] = self.scale_var.get()

        # Usa layout base, mas vai substituir offset/scale por tabela
        base_settings = self._get_current_settings()

        total = len(self.tables) * len(THEMES)
        count = 0

        for t_name, t_data in THEMES.items():
            theme_folder = t_name.replace(" ", "_")
            out_dir = self.generator.output_dir / theme_folder
            out_dir.mkdir(exist_ok=True)

            # Define tema
            batch_settings = base_settings.copy()
            batch_settings['bg_center'] = t_data['bg_center']
            batch_settings['accent_color'] = t_data['accent']

            for table_data in self.tables:
                t_idx = str(table_data["index"])

                # Aplica as configurações específicas desta tabela
                table_batch_settings = batch_settings.copy()
                table_batch_settings['offset_x'] = self.table_settings[t_idx]['offset_x']
                table_batch_settings['offset_y'] = self.table_settings[t_idx]['offset_y']
                table_batch_settings['scale'] = self.table_settings[t_idx]['scale']

                filename = f"{table_data['index']+1:02d}_{table_data['safe_title']}.png"
                save_path = out_dir / filename
                print(f"[{count+1}/{total}] Salvando {save_path}...")
                self.generator.generate_single_image(table_data, self.original_css, table_batch_settings, save_path=str(save_path))
                count += 1

                # Update status label
                self.root.after(0, lambda c=count: self.status_label.config(text=f"Status: Exportando... {c}/{total}"))

        self._is_rendering = False
        self.root.after(0, lambda: self._set_ui_state('normal', 'Pronto'))
        self.root.after(0, lambda: messagebox.showinfo("Sucesso", f"Batch export concluído!\n{count} imagens geradas."))


def main():
    parser = argparse.ArgumentParser(description="Gerador de Tabelas para YouTube")
    parser.add_argument('--no-gui', action='store_true', help='Executar sem GUI (CLI mode)')
    parser.add_argument('--theme', type=str, default='Dark Red', help='Nome do tema para o modo CLI')
    parser.add_argument('--layout', type=str, default='Left', choices=['Left', 'Center', 'Right', 'Fullscreen'], help='Layout para o modo CLI')
    parser.add_argument('--output-dir', type=str, default='Outputs', help='Diretório de saída')
    parser.add_argument('--table', type=str, help='Índice ou substring do nome da tabela para renderizar no modo CLI (opcional, por padrão renderiza todas)')
    args = parser.parse_args()

    BASE_DIR = Path(__file__).parent
    HTML_FILE = BASE_DIR / "index.html"

    if not HTML_FILE.exists():
        print("Erro: index.html não encontrado no diretório atual.")
        sys.exit(1)

    generator = TableImageGenerator(output_dir=args.output_dir)
    original_css, tables = generator.process_table_html(str(HTML_FILE))

    if args.no_gui:
        print("Modo CLI ativado.")
        theme_name = args.theme if args.theme in THEMES else "Dark Red"
        bg_center = THEMES[theme_name]["bg_center"]
        accent_color = THEMES[theme_name]["accent"]

        settings = {
            "layout": args.layout,
            "offset_x": 0,
            "offset_y": 0,
            "scale": 1.0,
            "bg_center": bg_center,
            "accent_color": accent_color
        }

        tables_to_render = tables
        if args.table:
            # Filter tables by index or substring
            filtered = []
            if args.table.isdigit():
                idx = int(args.table) - 1
                if 0 <= idx < len(tables):
                    filtered.append(tables[idx])
            else:
                filtered = [t for t in tables if args.table.lower() in t['title'].lower()]
            tables_to_render = filtered

        if not tables_to_render:
            print("Nenhuma tabela encontrada com o filtro especificado.")
            sys.exit(1)

        out_dir = Path(args.output_dir) / theme_name.replace(" ", "_")
        out_dir.mkdir(parents=True, exist_ok=True)

        for t in tables_to_render:
            filename = f"{t['index']+1:02d}_{t['safe_title']}.png"
            save_path = out_dir / filename
            print(f"Gerando {filename}...")
            generator.generate_single_image(t, original_css, settings, save_path=str(save_path))

        print("Concluído!")
    else:
        root = tk.Tk()
        app = AppGUI(root, generator, original_css, tables)
        root.mainloop()

if __name__ == '__main__':
    main()
