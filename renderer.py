"""
renderer.py
===========

Renderizador 2D.

Recibe ÚNICAMENTE las coordenadas calculadas por la cinemática directa
(``kinematics.forward_kinematics``) y compone al personaje colocando cada
pieza PNG (con fondo transparente) rotada según el ángulo de su hueso, de modo
que las piezas queden perfectamente unidas por sus pivotes (sin separaciones).

Produce una imagen ``PIL.Image`` RGBA del tamaño de la ventana. Esa imagen la
puede mostrar cualquier front-end (el visualizador de matplotlib, un notebook,
o guardarse a disco). El renderizador NO deberá modificarse en la segunda
etapa con Deep Learning.

Cámara: por defecto sigue al personaje en horizontal (el root se ancla al
centro de la ventana) para que las traslaciones (caminar, correr, dash...) no
lo saquen del encuadre. En vertical no sigue, para que los saltos se vean.

Opciones de depuración: se puede superponer el esqueleto, las articulaciones y
los pivotes, y activar/desactivar las piezas gráficas.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

import assets
import config
import kinematics
import skeleton

# Orden de dibujo (de atrás hacia delante) para una superposición correcta.
_DRAW_ORDER = [
    "l_knee", "l_ankle", "l_foot",       # pierna trasera
    "r_knee", "r_ankle", "r_foot",       # pierna delantera
    "chest",                             # torso
    "neck", "head",                      # cuello y cabeza
    "l_elbow", "l_wrist", "l_hand",      # brazo trasero
    "r_elbow", "r_wrist", "r_hand",      # brazo delantero
    "sword",                             # katana (al frente)
]


class Renderer:
    """Compone al personaje a partir de un estado cinemático."""

    def __init__(self):
        assets.ensure_assets()
        self._base_sprites: dict[str, Image.Image] = {}
        self._scaled_cache: dict[tuple[str, float], Image.Image] = {}
        self._joint_map = skeleton.joint_map()
        self.reload_assets()

    # -- Gestión de piezas -------------------------------------------------
    def reload_assets(self, force: bool = False) -> None:
        """(Re)genera y recarga las piezas PNG desde disco."""
        assets.ensure_assets(force=force)
        self._base_sprites = {
            part: Image.open(assets.asset_path(part)).convert("RGBA")
            for part in assets._BUILDERS
        }
        self._scaled_cache.clear()

    def _sprite(self, part: str) -> tuple[Image.Image, tuple[float, float]]:
        """Devuelve ``(imagen_escalada, pivote)`` de una pieza para SCALE."""
        key = (part, round(config.SCALE, 4))
        if key not in self._scaled_cache:
            base = self._base_sprites[part]
            if abs(config.SCALE - 1.0) < 1e-6:
                img = base
            else:
                w = max(1, int(round(base.width * config.SCALE)))
                h = max(1, int(round(base.height * config.SCALE)))
                img = base.resize((w, h), Image.LANCZOS)
            self._scaled_cache[key] = img
        img = self._scaled_cache[key]
        pivot = (assets.MARGIN * config.SCALE, img.height / 2.0)
        return img, pivot

    # -- Transformación de coordenadas -------------------------------------
    def _world_to_screen(self, x: float, y: float, offset_x: float) -> tuple[float, float]:
        """Coordenadas matemáticas (y arriba) -> píxeles de pantalla (y abajo)."""
        sx = x + offset_x
        sy = config.WINDOW_HEIGHT - y
        return sx, sy

    # -- Render principal --------------------------------------------------
    def render(self, state: dict, *,
               show_sprites: bool = True,
               show_skeleton: bool = False,
               show_joints: bool = False,
               show_pivots: bool = False,
               follow: bool = True,
               background: tuple[int, int, int, int] | None = None) -> Image.Image:
        """Renderiza un estado y devuelve una imagen RGBA de la ventana.

        Parameters
        ----------
        state:
            Estado cinemático del personaje.
        show_sprites, show_skeleton, show_joints, show_pivots:
            Capas a dibujar (permiten depurar).
        follow:
            Si ``True`` la cámara sigue al root en horizontal.
        background:
            Color de fondo RGBA. ``None`` = transparente.
        """
        canvas = Image.new(
            "RGBA", (config.WINDOW_WIDTH, config.WINDOW_HEIGHT),
            background if background is not None else (0, 0, 0, 0),
        )

        pose = kinematics.forward_kinematics(state)
        root_x = float(state.get("root_x", 0.0))
        offset_x = (config.WINDOW_WIDTH / 2.0 - root_x) if follow else 0.0

        if show_sprites:
            self._draw_sprites(canvas, pose, offset_x)
        if show_skeleton or show_joints or show_pivots:
            self._draw_debug(canvas, pose, offset_x,
                             show_skeleton, show_joints, show_pivots)
        return canvas

    def _draw_sprites(self, canvas: Image.Image, pose: kinematics.Pose,
                      offset_x: float) -> None:
        for name in _DRAW_ORDER:
            joint = self._joint_map.get(name)
            if joint is None or joint.part is None or joint.parent is None:
                continue
            sprite, pivot = self._sprite(joint.part)
            angle = pose.angles[name]                 # ángulo absoluto del hueso
            px, py = pose.positions[joint.parent]     # el pivote va en el padre
            sx, sy = self._world_to_screen(px, py, offset_x)
            self._paste_rotated(canvas, sprite, pivot, angle, sx, sy)

    @staticmethod
    def _paste_rotated(canvas: Image.Image, sprite: Image.Image,
                       pivot: tuple[float, float], angle_deg: float,
                       screen_x: float, screen_y: float) -> None:
        """Rota ``sprite`` alrededor de su pivote y lo pega en pantalla.

        Método: se coloca el sprite en un lienzo cuadrado con el pivote en el
        centro, se rota alrededor del centro (PIL rota en sentido antihorario,
        que con nuestra convención equivale al ángulo matemático del hueso), y
        se pega centrado en la posición de la articulación. Así el pivote queda
        exactamente sobre la articulación padre.
        """
        pw, ph = pivot
        # Distancia máxima del pivote a las esquinas -> lado del lienzo cuadrado.
        corners = [(0, 0), (sprite.width, 0), (0, sprite.height),
                   (sprite.width, sprite.height)]
        maxd = max(math.hypot(cx - pw, cy - ph) for cx, cy in corners)
        S = int(math.ceil(2 * maxd)) + 2
        square = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        # Pegar el sprite de modo que su pivote caiga en el centro del cuadrado.
        square.alpha_composite(sprite,
                               (int(round(S / 2 - pw)), int(round(S / 2 - ph))))
        rotated = square.rotate(angle_deg, resample=Image.BICUBIC, expand=False)
        top_left = (int(round(screen_x - S / 2)), int(round(screen_y - S / 2)))
        canvas.alpha_composite(rotated, top_left)

    def _draw_debug(self, canvas: Image.Image, pose: kinematics.Pose,
                    offset_x: float, skel: bool, joints: bool,
                    pivots: bool) -> None:
        draw = ImageDraw.Draw(canvas)

        # Huesos (líneas).
        if skel:
            for _name, p_parent, p_node in pose.bones():
                x0, y0 = self._world_to_screen(*p_parent, offset_x)
                x1, y1 = self._world_to_screen(*p_node, offset_x)
                draw.line([(x0, y0), (x1, y1)],
                          fill=config.DEBUG_COLORS["bone"], width=2)

        # Articulaciones (puntos en cada nodo).
        if joints:
            for name, (x, y) in pose.positions.items():
                sx, sy = self._world_to_screen(x, y, offset_x)
                color = (config.DEBUG_COLORS["root"] if name == "pelvis"
                         else config.DEBUG_COLORS["joint"])
                r = 5 if name == "pelvis" else 3
                draw.ellipse([sx - r, sy - r, sx + r, sy + r], fill=color)

        # Pivotes (mismos puntos, resaltados en otro color) para verificar
        # visualmente que las piezas se unen exactamente en las articulaciones.
        if pivots:
            for joint in skeleton.build_skeleton():
                if joint.parent is None:
                    continue
                x, y = pose.positions[joint.parent]
                sx, sy = self._world_to_screen(x, y, offset_x)
                draw.ellipse([sx - 2, sy - 2, sx + 2, sy + 2],
                             outline=config.DEBUG_COLORS["pivot"], width=1)
        return None

    # -- Utilidades --------------------------------------------------------
    @staticmethod
    def to_array(image: Image.Image) -> np.ndarray:
        """Convierte la imagen a un array numpy RGBA (para matplotlib)."""
        return np.asarray(image)

    def render_array(self, state: dict, **kwargs) -> np.ndarray:
        """Atajo: renderiza y devuelve directamente un array numpy."""
        return self.to_array(self.render(state, **kwargs))
