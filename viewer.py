"""
viewer.py
=========

Visualizador interactivo de las animaciones.

Abre una ventana (basada en Matplotlib, sin dependencias adicionales) donde se
reproducen continuamente las animaciones generadas por ``motions``. Permite:

* cambiar entre movimientos,
* pausar / reanudar,
* reiniciar la animación,
* generar nuevas variantes aleatorias del movimiento actual,
* activar/desactivar capas de depuración (esqueleto / articulaciones).

Muestra en pantalla el nombre del movimiento, el número de frame y los FPS
reales de reproducción.

Controles de teclado
--------------------
    →  / ↑        siguiente movimiento
    ←  / ↓        movimiento anterior
    1..9, 0       seleccionar movimiento por índice
    espacio       pausar / reanudar
    r             reiniciar la animación
    n             nueva variante aleatoria
    s             mostrar/ocultar esqueleto
    j             mostrar/ocultar articulaciones
    b             mostrar/ocultar piezas gráficas
    q             salir
"""

from __future__ import annotations

import time

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

import config
import motions
from renderer import Renderer


class Viewer:
    """Ventana de reproducción de animaciones."""

    def __init__(self, start_movement: str = "idle"):
        self.renderer = Renderer()
        self.generator = motions.MotionGenerator()
        self.movements = self.generator.available()

        self.current = start_movement if start_movement in self.movements else "idle"
        self.frames = self.generator.generate(self.current)
        self.index = 0
        self.paused = False

        # Capas de depuración.
        self.show_sprites = True
        self.show_skeleton = False
        self.show_joints = False

        # Medición de FPS reales.
        self._last_time = time.perf_counter()
        self._fps = 0.0

        self._setup_figure()

    # -- Construcción de la figura -----------------------------------------
    def _setup_figure(self) -> None:
        self.fig, self.ax = plt.subplots(figsize=(7, 7))
        self.fig.canvas.manager.set_window_title("Ninja 2D · Motor de animación")
        self.ax.set_xlim(0, config.WINDOW_WIDTH)
        self.ax.set_ylim(config.WINDOW_HEIGHT, 0)   # y hacia abajo (pantalla)
        self.ax.axis("off")
        self.fig.subplots_adjust(left=0, right=1, top=0.94, bottom=0.06)

        arr = self._render_current()
        self.im = self.ax.imshow(arr, extent=[0, config.WINDOW_WIDTH,
                                               config.WINDOW_HEIGHT, 0])
        # Suelo de referencia.
        self.ax.axhline(config.WINDOW_HEIGHT - 40, color="#3a4152", lw=2, zorder=0)

        self.title = self.ax.set_title("", fontsize=13, color="#222")
        self.help = self.fig.text(
            0.5, 0.01,
            "←/→ mover · 1-0 elegir · espacio pausa · r reinicio · "
            "n variante · s esqueleto · j joints · b piezas · q salir",
            ha="center", va="bottom", fontsize=8, color="#666",
        )

        self.fig.canvas.mpl_connect("key_press_event", self._on_key)

    # -- Render ------------------------------------------------------------
    def _render_current(self):
        state = self.frames[self.index]
        return self.renderer.render_array(
            state,
            show_sprites=self.show_sprites,
            show_skeleton=self.show_skeleton,
            show_joints=self.show_joints,
            background=(240, 242, 246, 255),
        )

    def _update_title(self) -> None:
        self.title.set_text(
            f"{self.current.upper():<12}  "
            f"frame {self.index + 1:>2}/{len(self.frames)}   "
            f"{self._fps:4.1f} FPS"
            + ("   [PAUSA]" if self.paused else "")
        )

    # -- Bucle de animación ------------------------------------------------
    def _tick(self, _frame_number):
        now = time.perf_counter()
        dt = now - self._last_time
        self._last_time = now
        if dt > 0:
            # Suavizado exponencial de los FPS reales.
            self._fps = 0.8 * self._fps + 0.2 * (1.0 / dt)

        if not self.paused:
            self.index = (self.index + 1) % len(self.frames)

        self.im.set_data(self._render_current())
        self._update_title()
        return (self.im, self.title)

    # -- Interacción -------------------------------------------------------
    def _regenerate(self, seed=None) -> None:
        self.frames = self.generator.generate(self.current, seed=seed)
        self.index = 0

    def _select(self, name: str) -> None:
        if name in self.movements:
            self.current = name
            self._regenerate()

    def _on_key(self, event) -> None:
        key = event.key
        if key in ("right", "up"):
            i = (self.movements.index(self.current) + 1) % len(self.movements)
            self._select(self.movements[i])
        elif key in ("left", "down"):
            i = (self.movements.index(self.current) - 1) % len(self.movements)
            self._select(self.movements[i])
        elif key in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
            idx = 9 if key == "0" else int(key) - 1
            if idx < len(self.movements):
                self._select(self.movements[idx])
        elif key == " ":
            self.paused = not self.paused
        elif key == "r":
            self.index = 0
        elif key == "n":
            self._regenerate()
        elif key == "s":
            self.show_skeleton = not self.show_skeleton
        elif key == "j":
            self.show_joints = not self.show_joints
        elif key == "b":
            self.show_sprites = not self.show_sprites
        elif key == "q":
            plt.close(self.fig)

    # -- Lanzamiento -------------------------------------------------------
    def run(self) -> None:
        """Inicia el bucle de reproducción (bloqueante)."""
        interval = 1000.0 / config.FPS
        # Guardamos la animación en un atributo para que no la recolecte el GC.
        self._anim = FuncAnimation(
            self.fig, self._tick, interval=interval,
            blit=False, cache_frame_data=False,
        )
        plt.show()


def launch(start_movement: str = "idle") -> None:
    """Crea y ejecuta el visualizador."""
    Viewer(start_movement).run()
