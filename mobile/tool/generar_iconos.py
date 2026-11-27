"""Generar iconos Android desde el logo original. Requiere Pillow."""
from pathlib import Path
from PIL import Image, ImageOps

mobile = Path(__file__).resolve().parents[1]
logo = Image.open(mobile / 'assets/el-cumbe-marca.png').convert('RGBA')
# El icono usa únicamente el símbolo superior; el nombre lo muestra Android.
# La franja inferior del original contiene la razón social y «EL CUMBE».
logo = logo.crop((0, 0, logo.width, int(logo.height * .75)))
logo = logo.crop(logo.getbbox())
res = mobile / 'android/app/src/main/res'


def icono(size, fraction):
    canvas = Image.new('RGBA', (size, size), '#ffffff')
    fitted = ImageOps.contain(logo, (int(size * fraction), int(size * fraction)),
                             Image.Resampling.LANCZOS)
    canvas.alpha_composite(fitted, ((size - fitted.width) // 2, (size - fitted.height) // 2))
    return canvas


for density, size in [('mdpi', 48), ('hdpi', 72), ('xhdpi', 96),
                      ('xxhdpi', 144), ('xxxhdpi', 192)]:
    folder = res / f'mipmap-{density}'
    folder.mkdir(exist_ok=True)
    icono(size, .76).save(folder / 'ic_launcher.png')

# Zona segura para máscaras circulares/redondeadas de Android 8 o superior.
folder = res / 'drawable'
folder.mkdir(exist_ok=True)
icono(432, .58).save(folder / 'el_cumbe_launcher.png')
print('Iconos El Cumbe generados.')
