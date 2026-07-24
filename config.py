"""
config.py
=========

Parámetros globales del proyecto de animación esquelética 2D.

Todo lo que sea susceptible de ajuste (tamaños de segmentos, límites
articulares, resolución de ventana, velocidad de reproducción, colores...)
vive aquí para poder modificarlo desde un único lugar, incluido el notebook
``development.ipynb``.

Los valores se exponen como diccionarios / variables de módulo *mutables*.
De esta forma, el notebook puede hacer por ejemplo::

    import config
    config.LENGTHS["thigh"] = 110
    config.SCALE = 1.2

y el resto de módulos (que leen ``config`` en tiempo de ejecución, sin
cachear) tomarán automáticamente los nuevos valores.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Ventana / render
# ---------------------------------------------------------------------------

WINDOW_WIDTH: int = 800          # ancho de la ventana / lienzo en píxeles
WINDOW_HEIGHT: int = 800         # alto de la ventana / lienzo en píxeles
FPS: int = 30                    # frames por segundo objetivo de reproducción

# Multiplicador global del tamaño del personaje. 1.0 = tamaño base.
SCALE: float = 1.0

# ---------------------------------------------------------------------------
# Longitudes de los segmentos corporales (en píxeles, ANTES de aplicar SCALE)
# ---------------------------------------------------------------------------
# Estas longitudes son CONSTANTES durante toda la animación: la cinemática
# directa nunca las modifica, sólo cambia los ángulos.

LENGTHS: dict[str, float] = {
    "spine": 110.0,       # pelvis  -> pecho
    "neck": 25.0,         # pecho   -> base del cuello
    "head": 55.0,         # cuello  -> parte superior de la cabeza
    "upper_arm": 70.0,    # hombro  -> codo
    "forearm": 65.0,      # codo    -> muñeca
    "hand": 22.0,         # muñeca  -> punta de la mano
    "thigh": 95.0,        # cadera  -> rodilla
    "calf": 90.0,         # rodilla -> tobillo
    "foot": 35.0,         # tobillo -> punta del pie
    "sword": 120.0,       # empuñadura -> punta de la katana
}

# ---------------------------------------------------------------------------
# Anchos de las piezas gráficas (en píxeles, ANTES de aplicar SCALE)
# ---------------------------------------------------------------------------
# Cada segmento se dibuja como una imagen PNG. Este es el "grosor" de la pieza.

PART_WIDTHS: dict[str, float] = {
    "torso": 20.0,        # tronco fino (estilo stick-figure)
    "neck": 12.0,
    "head": 60.0,         # diámetro de la cabeza
    "upper_arm": 14.0,
    "forearm": 11.0,
    "hand": 22.0,         # puño redondeado
    "thigh": 16.0,
    "calf": 12.0,
    "foot": 22.0,         # bota ninja puntiaguda
    "sword": 10.0,
}

# ---------------------------------------------------------------------------
# Límites articulares (grados). (mínimo, máximo)
# ---------------------------------------------------------------------------
# Cualquier ángulo que supere estos límites se corrige automáticamente
# (ver character.clamp_state / skeleton.clamp_angle).

JOINT_LIMITS: dict[str, tuple[float, float]] = {
    "root_rotation": (-360.0, 360.0),  # amplio: permite volteretas completas
    "torso_angle": (-30.0, 30.0),     # espalda
    "neck_angle": (-40.0, 40.0),      # cuello
    "left_shoulder": (-170.0, 170.0),
    "left_elbow": (0.0, 150.0),       # codo
    "right_shoulder": (-170.0, 170.0),
    "right_elbow": (0.0, 150.0),      # codo
    "left_hip": (-120.0, 120.0),
    "left_knee": (0.0, 140.0),        # rodilla
    "right_hip": (-120.0, 120.0),
    "right_knee": (0.0, 140.0),       # rodilla
    "sword_angle": (-180.0, 180.0),
}

# ---------------------------------------------------------------------------
# Estado cinemático del personaje
# ---------------------------------------------------------------------------
# Variables articulares (ángulos relativos respecto al padre) que definen la
# pose. Son las que una LSTM/GRU deberá generar en la segunda etapa.

ANGLE_KEYS: list[str] = [
    "root_rotation",
    "torso_angle",
    "neck_angle",
    "left_shoulder",
    "left_elbow",
    "right_shoulder",
    "right_elbow",
    "left_hip",
    "left_knee",
    "right_hip",
    "right_knee",
    "sword_angle",
]

# Orden canónico del VECTOR DE ESTADO completo (para Deep Learning).
# Incluye posición del root, velocidades, ángulos y metadatos de movimiento.
STATE_ORDER: list[str] = [
    "root_x",
    "root_y",
    "root_rotation",
    "velocity_x",
    "velocity_y",
    "torso_angle",
    "neck_angle",
    "left_shoulder",
    "left_elbow",
    "right_shoulder",
    "right_elbow",
    "left_hip",
    "left_knee",
    "right_hip",
    "right_knee",
    "sword_angle",
    "phase",
]

# ---------------------------------------------------------------------------
# Colores (paleta del ninja) usados para generar las piezas PNG
# ---------------------------------------------------------------------------
# RGBA (0-255). Estilo SILUETA: ninja negro (stick-figure), ojos blancos
# rasgados y una katana en gris oscuro para que se distinga de la silueta.

COLORS: dict[str, tuple[int, int, int, int]] = {
    "body": (20, 20, 24, 255),            # negro de la silueta (todo el cuerpo)
    "eye": (248, 248, 248, 255),          # ojos blancos
    "blade": (74, 78, 90, 255),           # hoja de la katana (gris oscuro)
    "blade_edge": (150, 154, 166, 255),   # filo/brillo de la hoja
    "hilt": (20, 20, 24, 255),            # empuñadura (negra)
}

# Colores de depuración (esqueleto / articulaciones / pivotes) en el render.
DEBUG_COLORS: dict[str, tuple[int, int, int, int]] = {
    "bone": (255, 255, 255, 200),
    "joint": (80, 200, 255, 255),
    "pivot": (255, 120, 40, 255),
    "root": (255, 60, 120, 255),
}

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------

BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR: str = os.path.join(BASE_DIR, "assets")


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def scaled_length(name: str) -> float:
    """Devuelve la longitud de un segmento aplicando ``SCALE``."""
    return LENGTHS[name] * SCALE


def scaled_width(name: str) -> float:
    """Devuelve el ancho de una pieza aplicando ``SCALE``."""
    return PART_WIDTHS[name] * SCALE


def default_root() -> tuple[float, float]:
    """Posición por defecto de la cadera (root) en coordenadas matemáticas.

    Se coloca centrada horizontalmente y a una altura tal que los pies
    queden cerca del suelo (parte inferior de la ventana).
    """
    return (WINDOW_WIDTH / 2.0, 240.0 * SCALE)
