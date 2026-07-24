"""
assets.py
=========

Generación PROCEDURAL de las piezas gráficas (PNG con fondo transparente) que
componen al ninja. Así el proyecto es autocontenido: no requiere arte externo.

Estilo: **silueta negra tipo stick-figure** (inspirado en un ninja stickman):
extremidades finas y negras, manos como puños, botas puntiagudas, y una cabeza
redonda con ojos blancos rasgados y una cinta con dos colas ondeando hacia
atrás. La katana se dibuja en gris oscuro para distinguirse de la silueta.

Cada pieza se dibuja apuntando hacia +x (hacia la derecha), con el PIVOTE
(el punto por el que se une a su articulación padre) en el centro del borde
IZQUIERDO de la imagen: ``(MARGIN, alto/2)``. La pieza se extiende hacia la
derecha una longitud igual a la del hueso. El renderizador rota cada pieza
según el ángulo del hueso y coloca ese pivote sobre la articulación, de modo
que nunca aparezcan separaciones entre segmentos.

Mapeo de orientación al rotar (con el personaje de pie, ver kinematics.py):
    - local +x  -> "hacia el extremo del hueso".
    - para la cabeza (hueso hacia arriba):  local +y = FRENTE del personaje
      (donde van los ojos),  local -y = ESPALDA (donde ondean las colas).
"""

from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw

import config

# Margen (en píxeles) alrededor de cada pieza para que nada se recorte.
MARGIN = 6

# Piezas que existen (deben coincidir con skeleton.py).
_PARTS = ["torso", "neck", "head", "upper_arm", "forearm", "hand",
          "thigh", "calf", "foot", "sword"]


def _new_canvas(width_px: float, height_px: float):
    w = int(round(width_px)) + 2 * MARGIN
    h = int(round(height_px)) + 2 * MARGIN
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _taper_capsule(draw, x0, x1, cy, w0, w1, color):
    """Cápsula afilada: círculo (r=w0/2) en x0, círculo (r=w1/2) en x1, unidos.

    Es la forma básica de todas las extremidades del stick-figure.
    """
    r0, r1 = w0 / 2.0, w1 / 2.0
    draw.ellipse([x0 - r0, cy - r0, x0 + r0, cy + r0], fill=color)
    draw.ellipse([x1 - r1, cy - r1, x1 + r1, cy + r1], fill=color)
    draw.polygon([(x0, cy - r0), (x1, cy - r1), (x1, cy + r1), (x0, cy + r0)],
                 fill=color)


# ---------------------------------------------------------------------------
# Extremidades finas (brazos, piernas, cuello)
# ---------------------------------------------------------------------------

def _limb(length_key: str, width_key: str, taper: float = 0.7) -> Image.Image:
    """Extremidad negra fina y ligeramente afilada hacia el extremo distal."""
    L = config.LENGTHS[length_key]
    W = config.PART_WIDTHS[width_key]
    img, d = _new_canvas(L, W)
    cy = img.height / 2.0
    _taper_capsule(d, MARGIN, MARGIN + L, cy, W, W * taper, config.COLORS["body"])
    return img


def _make_torso() -> Image.Image:
    """Tronco: línea negra que se ensancha ligeramente hacia los hombros."""
    L = config.LENGTHS["spine"]
    W = config.PART_WIDTHS["torso"]
    img, d = _new_canvas(L, W + 8)
    cy = img.height / 2.0
    # Más ancho en el pecho (extremo distal) que en la cadera (pivote).
    _taper_capsule(d, MARGIN, MARGIN + L, cy, W * 0.8, W + 6, config.COLORS["body"])
    return img


def _make_hand() -> Image.Image:
    """Mano: puño redondeado negro."""
    L = config.LENGTHS["hand"]
    W = config.PART_WIDTHS["hand"]
    img, d = _new_canvas(L, W)
    cy = img.height / 2.0
    cx = MARGIN + L * 0.45
    r = W / 2.0
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=config.COLORS["body"])
    return img


def _make_foot() -> Image.Image:
    """Pie: bota ninja puntiaguda (talón redondeado, punta hacia +x)."""
    L = config.LENGTHS["foot"]
    W = config.PART_WIDTHS["foot"]
    img, d = _new_canvas(L + W * 0.6, W)
    cy = img.height / 2.0
    x0 = MARGIN
    heel_r = W * 0.5
    # Talón redondeado sobre el pivote.
    d.ellipse([x0 - heel_r * 0.4, cy - heel_r, x0 + heel_r, cy + heel_r],
              fill=config.COLORS["body"])
    # Cuerpo de la bota con la punta afilada hacia delante y ligeramente abajo.
    toe_x = MARGIN + L + W * 0.55
    d.polygon([
        (x0, cy - heel_r),
        (MARGIN + L * 0.5, cy - heel_r * 0.7),
        (toe_x, cy + heel_r * 0.15),          # punta
        (MARGIN + L * 0.5, cy + heel_r),
        (x0, cy + heel_r),
    ], fill=config.COLORS["body"])
    return img


# ---------------------------------------------------------------------------
# Cabeza (con ojos rasgados y colas de la cinta)
# ---------------------------------------------------------------------------

def _paste_eye(img, cx, cy, w, h, angle_deg, color):
    """Dibuja un ojo (almendra) rotado y lo pega centrado en (cx, cy)."""
    e = Image.new("RGBA", (int(w) + 4, int(h) + 4), (0, 0, 0, 0))
    ImageDraw.Draw(e).ellipse([2, 2, w + 2, h + 2], fill=color)
    e = e.rotate(angle_deg, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(e, (int(round(cx - e.width / 2)),
                            int(round(cy - e.height / 2))))


def _make_head() -> Image.Image:
    """Cabeza redonda negra con ojos blancos rasgados y cinta con dos colas.

    Recordatorio de orientación (cabeza apuntando hacia arriba estando de pie):
        local +x  -> arriba (coronilla)      local -x -> abajo (cuello)
        local +y  -> FRENTE (cara/ojos)      local -y -> ESPALDA (colas)
    """
    L = config.LENGTHS["head"]          # cuello -> coronilla
    D = config.PART_WIDTHS["head"]      # diámetro de la cabeza
    tail = 62.0                         # alcance de las colas de la cinta

    # Lienzo con holgura vertical para que las colas (local -y) quepan arriba.
    W_img = int(round(MARGIN + L + MARGIN))
    H_img = int(round(D + 2 * tail))
    img = Image.new("RGBA", (W_img, H_img), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cy = H_img / 2.0                    # eje del hueso (= pivote y)
    r = D / 2.0
    ccx = MARGIN + L * 0.52             # centro de la cabeza sobre el hueso
    body = config.COLORS["body"]

    # --- Colas de la cinta (dos tiras onduladas hacia la espalda: local -y) ---
    # Nacen de la parte alta-trasera de la cabeza y ondean hacia arriba/atrás.
    for spread, lift, wob in [(0.62, 1.0, 12.0), (0.20, 0.78, 8.0)]:
        base = (ccx + r * 0.15, cy - r * spread)
        pts_top, pts_bot = [], []
        n = 14
        for i in range(n + 1):
            u = i / n
            px = base[0] + tail * 0.42 * u
            py = base[1] - tail * lift * u - wob * math.sin(u * math.pi * 1.6)
            wdt = 5.0 * (1.0 - u) ** 0.8 + 0.8      # se afila hacia la punta
            # normal aproximada perpendicular al avance para dar grosor
            pts_top.append((px - wdt, py - wdt))
            pts_bot.append((px + wdt, py + wdt))
        d.polygon(pts_top + pts_bot[::-1], fill=body)

    # --- Cabeza ---
    d.ellipse([ccx - r, cy - r, ccx + r, cy + r], fill=body)

    # --- Ojos blancos rasgados (enojados), en el FRENTE = local +y ---
    # Dos almendras al MISMO nivel (mismo dx) y separadas frente-atrás (dy),
    # de modo que en el render de pie queden lado a lado y a la misma altura.
    # La inclinación (-45°) deja la esquina frontal más baja -> mirada furiosa.
    eye = config.COLORS["eye"]
    _paste_eye(img, ccx + r * 0.33, cy + r * 0.10, r * 0.55, r * 0.26, -45, eye)
    _paste_eye(img, ccx + r * 0.33, cy + r * 0.52, r * 0.52, r * 0.24, -45, eye)
    return img


# ---------------------------------------------------------------------------
# Katana
# ---------------------------------------------------------------------------

def _make_sword() -> Image.Image:
    L = config.LENGTHS["sword"]
    W = config.PART_WIDTHS["sword"]
    img, d = _new_canvas(L, W + 6)
    cy = img.height / 2.0
    x0 = MARGIN
    hilt = L * 0.18
    guard = x0 + hilt
    # Empuñadura (tsuka) negra.
    d.rounded_rectangle([x0, cy - W * 0.32, guard, cy + W * 0.32], radius=W * 0.3,
                        fill=config.COLORS["hilt"])
    # Guarda (tsuba).
    d.ellipse([guard - 2, cy - W * 0.75, guard + 5, cy + W * 0.75],
              fill=config.COLORS["hilt"])
    # Hoja afilada hacia la punta.
    d.polygon([
        (guard, cy - W * 0.30), (MARGIN + L - 3, cy - W * 0.08),
        (MARGIN + L, cy), (MARGIN + L - 3, cy + W * 0.12),
        (guard, cy + W * 0.30),
    ], fill=config.COLORS["blade"])
    # Filo brillante.
    d.line([(guard, cy - W * 0.16), (MARGIN + L - 4, cy - 1)],
           fill=config.COLORS["blade_edge"], width=1)
    return img


_BUILDERS = {
    "torso": _make_torso,
    "head": _make_head,
    "hand": _make_hand,
    "foot": _make_foot,
    "sword": _make_sword,
    "neck": lambda: _limb("neck", "neck", taper=1.0),
    "upper_arm": lambda: _limb("upper_arm", "upper_arm"),
    "forearm": lambda: _limb("forearm", "forearm"),
    "thigh": lambda: _limb("thigh", "thigh"),
    "calf": lambda: _limb("calf", "calf"),
}


def asset_path(part: str) -> str:
    """Ruta en disco del PNG de una pieza."""
    return os.path.join(config.ASSET_DIR, f"{part}.png")


def build_part(part: str) -> Image.Image:
    """Construye (en memoria) la imagen de una pieza."""
    if part not in _BUILDERS:
        raise KeyError(f"Pieza desconocida: {part!r}")
    return _BUILDERS[part]()


def ensure_assets(force: bool = False) -> dict[str, str]:
    """Genera en disco todas las piezas que falten (o todas si ``force``).

    Devuelve ``{parte: ruta_png}``.
    """
    os.makedirs(config.ASSET_DIR, exist_ok=True)
    paths = {}
    for part in _BUILDERS:
        path = asset_path(part)
        if force or not os.path.exists(path):
            build_part(part).save(path)
        paths[part] = path
    return paths


if __name__ == "__main__":
    generated = ensure_assets(force=True)
    print("Piezas generadas en:", config.ASSET_DIR)
    for name, path in generated.items():
        print(f"  - {name:10s} -> {os.path.basename(path)}")
