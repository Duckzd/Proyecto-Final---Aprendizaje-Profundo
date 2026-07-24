"""
character.py
============

Representación del ESTADO CINEMÁTICO del personaje.

El personaje NO se representa mediante coordenadas absolutas, sino mediante un
diccionario de estado con:

* ``root_x``, ``root_y``      : posición de la cadera (root).
* ``root_rotation``           : rotación global del personaje.
* ``velocity_x``, ``velocity_y`` : velocidad del root (derivada de la posición).
* ángulos articulares relativos: ``torso_angle``, ``neck_angle``,
  ``left_shoulder``, ``left_elbow``, ``right_shoulder``, ``right_elbow``,
  ``left_hip``, ``left_knee``, ``right_hip``, ``right_knee``, ``sword_angle``.
* ``movement``                : nombre del movimiento en curso (str).
* ``phase``                   : fase normalizada del movimiento en [0, 1).

Este módulo ofrece utilidades para crear estados por defecto, aplicar los
límites articulares y convertir el estado a/desde un VECTOR numérico. Ese
vector es la interfaz pensada para la LSTM/GRU de la segunda etapa: la red
generará exactamente estos números y la cinemática directa + el renderizador
harán el resto SIN cambios.
"""

from __future__ import annotations

import numpy as np

import config
import skeleton


def default_state() -> dict:
    """Devuelve el estado neutro (personaje de pie, en reposo).

    Todos los ángulos articulares a 0 producen una pose erguida con brazos y
    piernas rectos. La katana se inclina ligeramente hacia arriba.
    """
    root_x, root_y = config.default_root()
    state: dict = {
        "root_x": root_x,
        "root_y": root_y,
        "root_rotation": 0.0,
        "velocity_x": 0.0,
        "velocity_y": 0.0,
        "torso_angle": 0.0,
        "neck_angle": 0.0,
        "left_shoulder": 0.0,
        "left_elbow": 10.0,
        "right_shoulder": 0.0,
        "right_elbow": 10.0,
        "left_hip": 0.0,
        "left_knee": 5.0,
        "right_hip": 0.0,
        "right_knee": 5.0,
        "sword_angle": 20.0,
        "movement": "idle",
        "phase": 0.0,
    }
    return clamp_state(state)


def clamp_state(state: dict) -> dict:
    """Corrige *in place* todos los ángulos para respetar los límites.

    Devuelve el mismo diccionario (mutado) por comodidad.
    """
    for key in config.JOINT_LIMITS:
        if key in state:
            state[key] = skeleton.clamp_angle(key, float(state[key]))
    return state


def get_state_vector(state: dict) -> np.ndarray:
    """Convierte el estado a un vector numérico en el orden canónico.

    Ver :data:`config.STATE_ORDER`. Ésta es la representación que consumirá /
    producirá la red neuronal en la segunda etapa.
    """
    return np.array([float(state.get(k, 0.0)) for k in config.STATE_ORDER],
                    dtype=np.float32)


def state_from_vector(vector: np.ndarray, movement: str = "generated") -> dict:
    """Reconstruye un estado a partir de un vector en orden canónico.

    Es la operación inversa de :func:`get_state_vector`. Pensada para tomar la
    salida de la LSTM/GRU y convertirla en un estado renderizable.
    """
    state = {k: float(v) for k, v in zip(config.STATE_ORDER, vector)}
    state["movement"] = movement
    return clamp_state(state)


def sequence_to_matrix(frames: list[dict]) -> np.ndarray:
    """Convierte una secuencia de estados en una matriz ``(T, D)``.

    ``T`` = número de frames, ``D`` = ``len(config.STATE_ORDER)``. Es el
    formato natural de entrada/salida para entrenar una red recurrente.
    """
    return np.stack([get_state_vector(f) for f in frames], axis=0)


class Character:
    """Envoltorio de conveniencia sobre el estado del personaje.

    Mantiene un estado actual y, opcionalmente, una secuencia de frames de una
    animación. No calcula coordenadas: para eso se usa ``kinematics``.
    """

    def __init__(self, state: dict | None = None):
        self.state: dict = state if state is not None else default_state()
        self.frames: list[dict] = []
        self._frame_index: int = 0

    # -- Gestión de animaciones --------------------------------------------
    def load_animation(self, frames: list[dict]) -> None:
        """Carga una secuencia de frames y sitúa el estado en el primero."""
        if not frames:
            raise ValueError("La animación no contiene frames.")
        self.frames = frames
        self._frame_index = 0
        self.state = dict(frames[0])

    def set_frame(self, index: int) -> dict:
        """Sitúa el estado en el frame ``index`` (con envoltura circular)."""
        if not self.frames:
            return self.state
        self._frame_index = index % len(self.frames)
        self.state = dict(self.frames[self._frame_index])
        return self.state

    def advance(self, step: int = 1) -> dict:
        """Avanza ``step`` frames en la animación cargada."""
        return self.set_frame(self._frame_index + step)

    @property
    def frame_index(self) -> int:
        return self._frame_index

    def get_state(self, frame: int | None = None) -> dict:
        """Devuelve el estado completo de un frame.

        Si ``frame`` es ``None`` devuelve el estado actual. Esta función es la
        interfaz recomendada para la segunda etapa (entrada/salida de la red).
        """
        if frame is None:
            return dict(self.state)
        if not self.frames:
            return dict(self.state)
        return dict(self.frames[frame % len(self.frames)])
