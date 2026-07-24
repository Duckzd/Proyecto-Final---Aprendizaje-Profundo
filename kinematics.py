"""
kinematics.py
=============

Cinemática Directa (Forward Kinematics).

Recibe el ESTADO cinemático del personaje (posición del root + ángulos
articulares relativos) y calcula, mediante trigonometría, las coordenadas
(x, y) de TODAS las articulaciones, así como el ángulo absoluto (world angle)
de cada hueso.

Reglas de diseño (importantes para la segunda etapa con Deep Learning):

* Las coordenadas NUNCA se almacenan como estado principal: se calculan de
  forma dinámica a partir del estado cada vez que hacen falta.
* Las longitudes de los segmentos son constantes (vienen del esqueleto).
* Este módulo NO deberá modificarse cuando una LSTM/GRU sustituya al
  generador matemático de movimientos: seguirá recibiendo el mismo estado.

Fórmula recursiva (coordenadas matemáticas, y hacia arriba, ángulos CCW+):

    world_angle(hueso) = world_angle(padre) + base_angle + angulo_articular
    pos(nodo)          = pos(padre) + longitud * (cos, sin)(world_angle)

El eje "hacia arriba" del root (la cadera) es ``root_rotation + 90°``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import config
import skeleton


@dataclass
class Pose:
    """Resultado de la cinemática directa para un estado dado.

    Attributes
    ----------
    positions:
        ``nombre_nodo -> (x, y)`` en coordenadas matemáticas (y hacia arriba).
    angles:
        ``nombre_nodo -> ángulo absoluto del hueso`` en grados.
    """

    positions: dict[str, tuple[float, float]]
    angles: dict[str, float]

    def bones(self) -> list[tuple[str, tuple[float, float], tuple[float, float]]]:
        """Lista de huesos como ``(nombre, punto_padre, punto_nodo)``.

        Útil para dibujar el esqueleto (una línea por hueso).
        """
        result = []
        for joint in skeleton.build_skeleton():
            if joint.parent is None:
                continue
            result.append(
                (joint.name, self.positions[joint.parent], self.positions[joint.name])
            )
        return result


def forward_kinematics(state: dict) -> Pose:
    """Calcula la pose (posiciones + ángulos) a partir del estado.

    Parameters
    ----------
    state:
        Diccionario con al menos ``root_x``, ``root_y``, ``root_rotation`` y
        las variables articulares (ver :data:`config.ANGLE_KEYS`). Las claves
        articulares que falten se asumen 0.

    Returns
    -------
    Pose
        Posiciones y ángulos absolutos de todas las articulaciones.
    """
    joints = skeleton.build_skeleton()

    root_x = float(state.get("root_x", 0.0))
    root_y = float(state.get("root_y", 0.0))
    root_rotation = float(state.get("root_rotation", 0.0))

    positions: dict[str, tuple[float, float]] = {}
    angles: dict[str, float] = {}

    # --- Raíz (cadera) ---
    root = joints[0]
    positions[root.name] = (root_x, root_y)
    # El eje de referencia de la cadera apunta "hacia arriba".
    angles[root.name] = root_rotation + 90.0

    # --- Resto del árbol (padres antes que hijos, garantizado por la tabla) ---
    for joint in joints[1:]:
        parent_angle = angles[joint.parent]
        parent_pos = positions[joint.parent]

        # Ángulo articular (con corrección de límites) sumado a la base.
        joint_value = 0.0
        if joint.state_key is not None:
            joint_value = skeleton.clamp_angle(
                joint.state_key, float(state.get(joint.state_key, 0.0))
            )

        # ``sign`` invierte el sentido de flexión donde la anatomía lo exige
        # (la rodilla flexiona hacia atrás, al revés que el codo).
        world_angle = parent_angle + joint.base_angle + joint.sign * joint_value
        rad = math.radians(world_angle)

        end_x = parent_pos[0] + joint.length * math.cos(rad)
        end_y = parent_pos[1] + joint.length * math.sin(rad)

        positions[joint.name] = (end_x, end_y)
        angles[joint.name] = world_angle

    return Pose(positions=positions, angles=angles)


def joint_coordinates(state: dict) -> dict[str, tuple[float, float]]:
    """Atajo: devuelve sólo el diccionario de coordenadas (x, y)."""
    return forward_kinematics(state).positions


def bounding_box(pose: Pose) -> tuple[float, float, float, float]:
    """Devuelve ``(min_x, min_y, max_x, max_y)`` de una pose.

    Útil para encuadrar la visualización automáticamente.
    """
    xs = [p[0] for p in pose.positions.values()]
    ys = [p[1] for p in pose.positions.values()]
    return (min(xs), min(ys), max(xs), max(ys))
