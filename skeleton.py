"""
skeleton.py
===========

Definición del esqueleto articulado del personaje como un ÁRBOL JERÁRQUICO
de articulaciones (joints).

Cada nodo del árbol representa el extremo *distal* de un hueso (el punto donde
ese hueso termina y del que pueden colgar sus hijos). El hueso que llega a un
nodo tiene:

* ``parent``      : nombre del nodo padre (de dónde sale el hueso).
* ``length_key``  : clave de :data:`config.LENGTHS` con la longitud del hueso.
* ``base_angle``  : orientación de reposo del hueso RELATIVA al padre (grados).
* ``state_key``   : nombre de la variable de estado (ángulo articular) que se
                    suma a ``base_angle``. ``None`` si el hueso es rígido.
* ``part``        : clave de la pieza gráfica (:data:`config.PART_WIDTHS`) o
                    ``None`` si no se dibuja.
* ``limit``       : límites articulares (min, max) tomados de config.

La raíz del árbol es la CADERA (``pelvis``). Desde ella nacen el tronco (y de
él cuello, cabeza y brazos) y las dos piernas. La katana cuelga de la mano
derecha mediante una articulación adicional (``sword_angle``).

IMPORTANTE: aquí NO hay coordenadas. El esqueleto sólo describe la estructura
y las longitudes constantes. Las posiciones (x, y) las calcula
``kinematics.forward_kinematics`` a partir del estado.
"""

from __future__ import annotations

from dataclasses import dataclass

import config


@dataclass(frozen=True)
class Joint:
    """Un hueso del esqueleto (nodo del árbol jerárquico)."""

    name: str                 # nombre del nodo (extremo distal del hueso)
    parent: str | None        # nombre del nodo padre (None para la raíz)
    length_key: str | None    # clave en config.LENGTHS (None para la raíz)
    base_angle: float         # ángulo de reposo relativo al padre (grados)
    state_key: str | None     # variable de estado que modula el ángulo
    part: str | None          # pieza gráfica asociada (None = no se dibuja)
    sign: float = 1.0         # sentido de flexión (+1 codo/hacia delante,
                              # -1 rodilla/hacia atrás, como en la anatomía)

    @property
    def length(self) -> float:
        """Longitud actual del hueso (con SCALE aplicado)."""
        if self.length_key is None:
            return 0.0
        return config.scaled_length(self.length_key)

    @property
    def limit(self) -> tuple[float, float] | None:
        """Límites articulares de la variable de estado, si existe."""
        if self.state_key is None:
            return None
        return config.JOINT_LIMITS.get(self.state_key)


# ---------------------------------------------------------------------------
# Definición del árbol.  El ORDEN garantiza que todo padre aparece antes que
# sus hijos, de modo que la cinemática directa se puede resolver en una sola
# pasada.
# ---------------------------------------------------------------------------
#
# Convención de ángulos (coordenadas matemáticas, y hacia arriba, CCW +):
#   - El "eje hacia arriba" de la cadera es root_rotation + 90°.
#   - El tronco continúa hacia arriba (base 0).
#   - Los brazos cuelgan hacia abajo desde el pecho  -> base ~180°.
#   - Las piernas cuelgan hacia abajo desde la cadera -> base ~180°.
#   - Los pies apuntan hacia delante                  -> base ~ +80°.
#
# Las pequeñas asimetrías (±12°, ±8°) separan lados izquierdo/derecho para que
# las extremidades no queden perfectamente superpuestas en la pose de reposo.

_JOINT_TABLE: list[Joint] = [
    # nombre        padre        long_key      base    state_key        parte
    Joint("pelvis",   None,       None,          0.0,   None,            None),

    # --- Columna, cuello y cabeza ---
    Joint("chest",    "pelvis",   "spine",       0.0,   "torso_angle",   "torso"),
    Joint("neck",     "chest",    "neck",        0.0,   "neck_angle",    "neck"),
    Joint("head",     "neck",     "head",        0.0,   None,            "head"),

    # --- Brazo izquierdo (nace del pecho) ---
    Joint("l_elbow",  "chest",    "upper_arm",   192.0, "left_shoulder", "upper_arm"),
    Joint("l_wrist",  "l_elbow",  "forearm",     0.0,   "left_elbow",    "forearm"),
    Joint("l_hand",   "l_wrist",  "hand",        0.0,   None,            "hand"),

    # --- Brazo derecho (nace del pecho) ---
    Joint("r_elbow",  "chest",    "upper_arm",   168.0, "right_shoulder","upper_arm"),
    Joint("r_wrist",  "r_elbow",  "forearm",     0.0,   "right_elbow",   "forearm"),
    Joint("r_hand",   "r_wrist",  "hand",        0.0,   None,            "hand"),

    # --- Pierna izquierda (nace de la cadera) ---
    Joint("l_knee",   "pelvis",   "thigh",       188.0, "left_hip",      "thigh"),
    Joint("l_ankle",  "l_knee",   "calf",        0.0,   "left_knee",     "calf",  sign=-1.0),
    Joint("l_foot",   "l_ankle",  "foot",        80.0,  None,            "foot"),

    # --- Pierna derecha (nace de la cadera) ---
    Joint("r_knee",   "pelvis",   "thigh",       172.0, "right_hip",     "thigh"),
    Joint("r_ankle",  "r_knee",   "calf",        0.0,   "right_knee",    "calf",  sign=-1.0),
    Joint("r_foot",   "r_ankle",  "foot",        80.0,  None,            "foot"),

    # --- Katana (nace de la mano derecha) ---
    Joint("sword",    "r_hand",   "sword",       -95.0, "sword_angle",   "sword"),
]

# Etiquetas legibles para la visualización del esqueleto en el notebook.
JOINT_LABELS: dict[str, str] = {
    "pelvis": "Hip (root)",
    "chest": "Chest",
    "neck": "Neck",
    "head": "Head",
    "l_elbow": "L Elbow",
    "l_wrist": "L Wrist",
    "l_hand": "L Hand",
    "r_elbow": "R Elbow",
    "r_wrist": "R Wrist",
    "r_hand": "R Hand",
    "l_knee": "L Knee",
    "l_ankle": "L Ankle",
    "l_foot": "L Foot",
    "r_knee": "R Knee",
    "r_ankle": "R Ankle",
    "r_foot": "R Foot",
    "sword": "Sword",
}


def build_skeleton() -> list[Joint]:
    """Devuelve la lista de articulaciones del esqueleto.

    Se reconstruye a partir de la tabla (que a su vez lee ``config`` de forma
    perezosa mediante las propiedades ``length``/``limit``), de modo que
    cualquier cambio en ``config.LENGTHS`` o ``config.SCALE`` se refleja de
    inmediato sin reiniciar el programa.
    """
    return list(_JOINT_TABLE)


def joint_map() -> dict[str, Joint]:
    """Devuelve un diccionario ``nombre -> Joint`` para acceso directo."""
    return {j.name: j for j in _JOINT_TABLE}


def root_joint() -> Joint:
    """Devuelve la articulación raíz (la cadera)."""
    return _JOINT_TABLE[0]


def clamp_angle(state_key: str, value: float) -> float:
    """Corrige ``value`` para que respete los límites articulares.

    Si ``state_key`` no tiene límites definidos, devuelve el valor sin tocar.
    """
    limit = config.JOINT_LIMITS.get(state_key)
    if limit is None:
        return value
    low, high = limit
    return max(low, min(high, value))
