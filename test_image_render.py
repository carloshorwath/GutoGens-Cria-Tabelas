import os
import sys
import re
import time
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from bs4 import BeautifulSoup
from html2image import Html2Image

def create_rounded_mask(width, height, radius):
    """Creates a rounded rectangle mask"""
    mask = Image.new('L', (width, height), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, width, height], radius, fill=255)
    return mask

def main():
    width, height = 400, 300
    card_img = Image.new('RGB', (width, height), color=(30, 30, 30))
    # Test mask
    mask = create_rounded_mask(width, height, 40)
    card_rgba = Image.new('RGBA', card_img.size)
    card_rgba.paste(card_img, (0, 0))
    card_rgba.putalpha(mask)

    # Test drop shadow
    shadow_offset = (0, 20)
    shadow_blur = 30
    shadow = Image.new('RGBA', (width, height), color=(0, 0, 0, 150))
    shadow.putalpha(mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(shadow_blur))

    # Test composite
    bg = Image.new('RGB', (800, 600), color=(100, 100, 100))

    paste_x = 200
    paste_y = 150

    # composite shadow
    bg.paste(shadow, (paste_x + shadow_offset[0], paste_y + shadow_offset[1]), shadow)
    # composite card
    bg.paste(card_rgba, (paste_x, paste_y), card_rgba)

    bg.save("temp_test_render/test_composite.png")

if __name__ == '__main__':
    main()
