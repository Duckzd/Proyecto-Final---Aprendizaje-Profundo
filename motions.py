"""
motions.py
==========

Generador PROCEDURAL de movimientos.

En lugar de keyframes dibujados a mano, cada movimiento se construye con
funciones matemáticas (senos, cosenos, interpolaciones y curvas suaves) que
modulan los ángulos articulares a lo largo del tiempo.

Cada llamada a :meth:`MotionGenerator.generate`:

* produce entre 30 y 60 frames,
* introduce pequeñas variaciones aleatorias (velocidad, amplitud, altura de
  salto, inclinación del torso, longitud del paso, velocidad de ataque...),
  de modo que dos ejecuciones nunca son idénticas,
* devuelve una lista de ESTADOS (diccionarios), no coordenadas.

Este generador es exactamente la pieza que una LSTM/GRU sustituirá en la
segunda etapa: la red producirá la misma secuencia de estados y el resto del
pipeline (cinemática directa + render) no cambiará.

Convención de ángulos (ver skeleton.py):
    - torso_angle negativo  -> inclinación del tronco hacia delante (+x).
    - right_shoulder ~ +100 -> brazo derecho hacia delante/horizontal.
    - right_hip ~ +90       -> pierna derecha hacia delante/horizontal.
    - rodillas y codos: siempre >= 0 (sólo flexionan en un sentido).
"""

from __future__ import annotations

import math

import numpy as np

import character
import config


# ---------------------------------------------------------------------------
# Utilidades matemáticas
# ---------------------------------------------------------------------------

def _lerp(a: float, b: float, t: float) -> float:
    """Interpolación lineal."""
    return a + (b - a) * t


def _smoothstep(t: float) -> float:
    """Curva suave (aceleración/desaceleración) en [0, 1]."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _bell(t: float, center: float = 0.5, width: float = 0.25) -> float:
    """Curva tipo campana en [0, 1], con pico en ``center``.

    Útil para golpes: cero al inicio/fin, máximo en el instante del impacto.
    """
    return math.exp(-((t - center) ** 2) / (2.0 * width * width))


class MotionGenerator:
    """Genera secuencias de estados para cada movimiento del personaje."""

    #: Movimientos disponibles (nombre público -> método interno).
    MOVEMENTS = [
        "idle", "walk", "run", "jump", "dash",
        "roll", "punch", "kick", "sword_slash", "sword_combo",
    ]

    def __init__(self, seed: int | None = None):
        self._master_seed = seed

    # -- API pública -------------------------------------------------------
    def available(self) -> list[str]:
        """Lista de movimientos que se pueden generar."""
        return list(self.MOVEMENTS)

    def generate(self, name: str, seed: int | None = None,
                 n_frames: int | None = None) -> list[dict]:
        """Genera una secuencia de estados para el movimiento ``name``.

        Parameters
        ----------
        name:
            Nombre del movimiento (ver :attr:`MOVEMENTS`).
        seed:
            Semilla aleatoria. Con ``None`` se obtiene una variante distinta
            en cada llamada; con un entero fijo, el resultado es reproducible.
        n_frames:
            Nº de frames. Si es ``None`` se elige aleatoriamente en [30, 60].
        """
        if name not in self.MOVEMENTS:
            raise ValueError(f"Movimiento desconocido: {name!r}. "
                             f"Disponibles: {self.MOVEMENTS}")
        rng = np.random.default_rng(seed if seed is not None else self._master_seed)
        if n_frames is None:
            n_frames = int(rng.integers(30, 61))
        builder = getattr(self, f"_{name}")
        frames = builder(rng, n_frames)
        return self._finalize(frames, name)

    # -- Post-proceso común ------------------------------------------------
    def _finalize(self, frames: list[dict], name: str) -> list[dict]:
        """Fija movimiento/fase, calcula velocidades y aplica límites."""
        n = len(frames)
        for i, st in enumerate(frames):
            st["movement"] = name
            st["phase"] = i / n  # fase normalizada en [0, 1)

        # Velocidades del root por diferencias finitas.
        for i in range(n):
            if i == 0:
                vx = frames[1]["root_x"] - frames[0]["root_x"] if n > 1 else 0.0
                vy = frames[1]["root_y"] - frames[0]["root_y"] if n > 1 else 0.0
            else:
                vx = frames[i]["root_x"] - frames[i - 1]["root_x"]
                vy = frames[i]["root_y"] - frames[i - 1]["root_y"]
            frames[i]["velocity_x"] = vx
            frames[i]["velocity_y"] = vy

        # Corrección de límites articulares.
        for st in frames:
            character.clamp_state(st)
        return frames

    def _base_frames(self, n: int) -> list[dict]:
        """Crea ``n`` copias del estado neutro para modular encima."""
        return [character.default_state() for _ in range(n)]

    # ------------------------------------------------------------------
    # Encadenado de movimientos (varias acciones en una secuencia)
    # ------------------------------------------------------------------
    def compose(self, sequence: list[str], seed: int | None = None,
                blend: int = 8, per_frames: int | None = None) -> list[dict]:
        """Encadena varios movimientos en UNA sola secuencia continua.

        Ejemplo: ``compose(["run", "jump", "sword_slash"])`` produce al ninja
        corriendo, saltando y atacando sin cortes. Entre cada par de acciones se
        insertan ``blend`` frames de transición interpolada (curva suave) y se
        desplaza el root para que la posición sea continua (la traslación se
        acumula). Al final se recalculan velocidades y fase global.

        Parameters
        ----------
        sequence:
            Lista de nombres de movimiento a encadenar.
        seed:
            Semilla (cada sub-movimiento recibe una semilla derivada distinta).
        blend:
            Nº de frames de transición entre movimientos (0 = corte seco).
        per_frames:
            Frames por sub-movimiento (``None`` = aleatorio 30-60 en cada uno).
        """
        if not sequence:
            raise ValueError("La secuencia de movimientos está vacía.")
        rng = np.random.default_rng(seed)
        frames: list[dict] = []
        labels: list[str] = []
        cursor: dict | None = None      # último frame ya colocado
        prev: str | None = None

        for name in sequence:
            seg = self.generate(name, seed=int(rng.integers(0, 1_000_000)),
                                n_frames=per_frames)
            if cursor is not None:
                # Continuidad de posición: desplaza el root del segmento para
                # que empiece donde terminó el anterior.
                dx = cursor["root_x"] - seg[0]["root_x"]
                dy = cursor["root_y"] - seg[0]["root_y"]
                dr = cursor["root_rotation"] - seg[0]["root_rotation"]
                for f in seg:
                    f["root_x"] += dx
                    f["root_y"] += dy
                    f["root_rotation"] += dr
                # Transición suave de la pose entre acciones.
                for t in self._blend_frames(cursor, seg[0], blend):
                    frames.append(t)
                    labels.append(f"{prev}→{name}")
            for f in seg:
                frames.append(f)
                labels.append(name)
            cursor = dict(frames[-1])
            prev = name

        return self._finalize_composite(frames, labels)

    def _blend_frames(self, a: dict, b: dict, n: int) -> list[dict]:
        """Genera ``n`` frames que interpolan suavemente la pose de ``a`` a ``b``."""
        keys = ["root_x", "root_y"] + config.ANGLE_KEYS
        out = []
        for i in range(1, n + 1):
            w = _smoothstep(i / (n + 1))
            st = character.default_state()
            for k in keys:
                st[k] = _lerp(a[k], b[k], w)
            out.append(st)
        return out

    def _finalize_composite(self, frames: list[dict],
                            labels: list[str]) -> list[dict]:
        """Fija etiqueta/fase por frame, recalcula velocidades y aplica límites."""
        n = len(frames)
        for i, (st, lab) in enumerate(zip(frames, labels)):
            st["movement"] = lab
            st["phase"] = i / n
        for i in range(n):
            if i == 0:
                vx = frames[1]["root_x"] - frames[0]["root_x"] if n > 1 else 0.0
                vy = frames[1]["root_y"] - frames[0]["root_y"] if n > 1 else 0.0
            else:
                vx = frames[i]["root_x"] - frames[i - 1]["root_x"]
                vy = frames[i]["root_y"] - frames[i - 1]["root_y"]
            frames[i]["velocity_x"] = vx
            frames[i]["velocity_y"] = vy
        for st in frames:
            character.clamp_state(st)
        return frames

    # ------------------------------------------------------------------
    # Movimientos
    # ------------------------------------------------------------------
    def _idle(self, rng, n: int) -> list[dict]:
        """Reposo: respiración sutil y ligero balanceo."""
        frames = self._base_frames(n)
        breath_amp = rng.uniform(2.0, 4.0)
        sway = rng.uniform(1.5, 3.5)
        speed = rng.uniform(0.8, 1.3)
        phase0 = rng.uniform(0, 2 * math.pi)
        for i, st in enumerate(frames):
            w = 2 * math.pi * speed * i / n + phase0
            st["torso_angle"] = breath_amp * math.sin(w)
            st["neck_angle"] = 0.5 * breath_amp * math.sin(w + 0.4)
            st["left_shoulder"] = sway * math.sin(w)
            st["right_shoulder"] = -sway * math.sin(w)
            st["left_elbow"] = 12 + 3 * math.sin(w)
            st["right_elbow"] = 12 + 3 * math.sin(w)
            st["left_knee"] = 6 + 1.5 * math.sin(w)
            st["right_knee"] = 6 + 1.5 * math.sin(w)
            st["root_y"] += 1.5 * math.sin(w)  # respiración vertical
            st["sword_angle"] = 20 + 3 * math.sin(w + 1.0)
        return frames

    def _walk(self, rng, n: int) -> list[dict]:
        """Caminar: piernas y brazos alternos, con balanceo del root."""
        frames = self._base_frames(n)
        cycles = rng.uniform(1.5, 2.5)
        hip_amp = rng.uniform(22, 30)      # longitud del paso
        knee_amp = rng.uniform(25, 38)
        arm_amp = rng.uniform(18, 26)
        lean = rng.uniform(4, 10)          # inclinación del torso
        step_len = rng.uniform(30, 45)     # avance por ciclo
        bob = rng.uniform(3, 6)
        for i, st in enumerate(frames):
            t = i / n
            w = 2 * math.pi * cycles * t
            st["left_hip"] = hip_amp * math.sin(w)
            st["right_hip"] = hip_amp * math.sin(w + math.pi)
            st["left_knee"] = 12 + knee_amp * max(0.0, math.sin(w + 0.7))
            st["right_knee"] = 12 + knee_amp * max(0.0, math.sin(w + math.pi + 0.7))
            st["left_shoulder"] = -arm_amp * math.sin(w)
            st["right_shoulder"] = arm_amp * math.sin(w)
            st["left_elbow"] = 25 + 8 * math.sin(w)
            st["right_elbow"] = 25 - 8 * math.sin(w)
            st["torso_angle"] = -lean + 2 * math.sin(2 * w)
            st["neck_angle"] = 0.4 * lean
            st["root_x"] += step_len * cycles * t
            st["root_y"] += bob * abs(math.sin(w))  # sube al apoyar
        return frames

    def _run(self, rng, n: int) -> list[dict]:
        """Correr: como caminar pero más rápido, amplio e inclinado."""
        frames = self._base_frames(n)
        cycles = rng.uniform(2.5, 3.5)
        hip_amp = rng.uniform(38, 52)
        knee_amp = rng.uniform(55, 75)
        arm_amp = rng.uniform(35, 50)
        lean = rng.uniform(16, 26)
        step_len = rng.uniform(60, 90)
        bob = rng.uniform(8, 14)
        for i, st in enumerate(frames):
            t = i / n
            w = 2 * math.pi * cycles * t
            st["left_hip"] = hip_amp * math.sin(w)
            st["right_hip"] = hip_amp * math.sin(w + math.pi)
            st["left_knee"] = 20 + knee_amp * max(0.0, math.sin(w + 0.9))
            st["right_knee"] = 20 + knee_amp * max(0.0, math.sin(w + math.pi + 0.9))
            st["left_shoulder"] = -arm_amp * math.sin(w)
            st["right_shoulder"] = arm_amp * math.sin(w)
            st["left_elbow"] = 75 + 15 * math.sin(w)
            st["right_elbow"] = 75 - 15 * math.sin(w)
            st["torso_angle"] = -lean
            st["neck_angle"] = 0.5 * lean
            st["root_x"] += step_len * cycles * t
            st["root_y"] += bob * abs(math.sin(w))
        return frames

    def _jump(self, rng, n: int) -> list[dict]:
        """Salto: parábola vertical con flexión al despegar/aterrizar y
        recogida de piernas en el punto más alto (estilo acrobático)."""
        frames = self._base_frames(n)
        height = rng.uniform(90, 150)      # altura del salto
        crouch = rng.uniform(35, 55)
        tuck = rng.uniform(35, 60)
        forward = rng.uniform(0, 40)       # avance horizontal
        arm_raise = rng.uniform(60, 100)
        for i, st in enumerate(frames):
            t = i / n
            air = math.sin(math.pi * t)              # 0 -> 1 -> 0
            ground = 1.0 - air                        # 1 en despegue/aterrizaje
            st["root_y"] += height * air
            st["root_x"] += forward * t
            st["left_knee"] = 10 + crouch * ground + tuck * air
            st["right_knee"] = 10 + crouch * ground + tuck * air
            st["left_hip"] = 30 * air
            st["right_hip"] = 30 * air
            st["left_shoulder"] = -arm_raise * air
            st["right_shoulder"] = arm_raise * air
            st["left_elbow"] = 30 + 20 * air
            st["right_elbow"] = 30 + 20 * air
            st["torso_angle"] = -8 * air
        return frames

    def _dash(self, rng, n: int) -> list[dict]:
        """Dash: impulso rápido hacia delante con recuperación (ease-out)."""
        frames = self._base_frames(n)
        distance = rng.uniform(120, 190)
        lean = rng.uniform(20, 30)
        split = rng.uniform(45, 65)        # apertura de piernas (zancada)
        for i, st in enumerate(frames):
            t = i / n
            e = _smoothstep(min(1.0, t * 1.6))       # avance rápido y frena
            burst = _bell(t, center=0.25, width=0.2)
            st["root_x"] += distance * e
            st["root_y"] += 12 * burst
            st["torso_angle"] = -lean * (0.4 + 0.6 * burst)
            # Pierna adelantada / atrasada
            st["right_hip"] = split * (0.5 + 0.5 * burst)
            st["left_hip"] = -split * (0.4 + 0.4 * burst)
            st["right_knee"] = 15 + 30 * burst
            st["left_knee"] = 25 + 50 * burst
            # Brazos hacia atrás
            st["left_shoulder"] = -35 * burst
            st["right_shoulder"] = -35 * burst
            st["left_elbow"] = 60 + 30 * burst
            st["right_elbow"] = 60 + 30 * burst
        return frames

    def _roll(self, rng, n: int) -> list[dict]:
        """Voltereta: rotación completa del root con cuerpo recogido."""
        frames = self._base_frames(n)
        distance = rng.uniform(110, 170)
        direction = -1.0 if rng.random() < 0.5 else 1.0  # adelante/atrás
        tuck_hip = rng.uniform(55, 75)
        tuck_knee = rng.uniform(95, 125)
        for i, st in enumerate(frames):
            t = i / n
            st["root_rotation"] = direction * 360.0 * t
            st["root_x"] += -direction * distance * t
            st["root_y"] += 20 * math.sin(math.pi * t)   # rebote de "bola"
            # Cuerpo recogido durante casi toda la voltereta.
            curl = 0.6 + 0.4 * math.sin(math.pi * t)
            st["left_hip"] = tuck_hip * curl
            st["right_hip"] = tuck_hip * curl
            st["left_knee"] = tuck_knee * curl
            st["right_knee"] = tuck_knee * curl
            st["left_shoulder"] = 40 * curl
            st["right_shoulder"] = 40 * curl
            st["left_elbow"] = 110 * curl
            st["right_elbow"] = 110 * curl
            st["torso_angle"] = -25 * curl
            st["neck_angle"] = -20 * curl
        return frames

    def _punch(self, rng, n: int) -> list[dict]:
        """Puñetazo: brazo derecho se retrae y golpea al frente."""
        frames = self._base_frames(n)
        strike = rng.uniform(0.40, 0.55)   # instante del impacto
        speed = rng.uniform(0.9, 1.3)      # velocidad del ataque
        reach = rng.uniform(95, 115)
        for i, st in enumerate(frames):
            t = i / n
            # Fase de golpe: retracción -> extensión -> recuperación.
            ext = _bell(t, center=strike, width=0.12 / speed)
            st["right_shoulder"] = _lerp(10, reach, ext)
            st["right_elbow"] = _lerp(130, 8, ext)   # se estira al golpear
            # Guardia con el brazo izquierdo.
            st["left_shoulder"] = 70
            st["left_elbow"] = 120
            # Rotación de tronco y micro-avance.
            st["torso_angle"] = -6 - 10 * ext
            st["neck_angle"] = 6 * ext
            st["root_x"] += 12 * _smoothstep(t)
            st["right_knee"] = 20
            st["left_knee"] = 15
        return frames

    def _kick(self, rng, n: int) -> list[dict]:
        """Patada: pierna derecha se eleva al frente y regresa."""
        frames = self._base_frames(n)
        strike = rng.uniform(0.45, 0.6)
        speed = rng.uniform(0.9, 1.3)
        reach = rng.uniform(85, 105)
        for i, st in enumerate(frames):
            t = i / n
            ext = _bell(t, center=strike, width=0.14 / speed)
            st["right_hip"] = _lerp(-10, reach, ext)
            st["right_knee"] = _lerp(70, 8, ext)     # extiende al impactar
            # Pierna de apoyo (izquierda) ligeramente flexionada.
            st["left_hip"] = -12 * ext
            st["left_knee"] = 18 + 15 * ext
            # Equilibrio con torso y brazos.
            st["torso_angle"] = 10 * ext
            st["left_shoulder"] = -30 - 20 * ext
            st["right_shoulder"] = 30 + 20 * ext
            st["left_elbow"] = 50
            st["right_elbow"] = 50
            st["root_y"] += 8 * ext                  # leve salto
        return frames

    def _sword_slash(self, rng, n: int) -> list[dict]:
        """Corte de katana: arco descendente diagonal."""
        frames = self._base_frames(n)
        speed = rng.uniform(0.9, 1.3)
        wind = rng.uniform(0.15, 0.3)      # duración del amago
        for i, st in enumerate(frames):
            t = i / n
            self._apply_slash(st, t, speed, wind, torso_dir=-1.0)
        return frames

    def _sword_combo(self, rng, n: int) -> list[dict]:
        """Combo de katana: varios cortes encadenados con un paso."""
        frames = self._base_frames(n)
        n_strikes = int(rng.integers(2, 4))
        speed = rng.uniform(1.0, 1.4)
        step = rng.uniform(20, 45)
        for i, st in enumerate(frames):
            t = i / n
            local = (t * n_strikes) % 1.0           # fase dentro del corte
            strike_idx = int(t * n_strikes)
            torso_dir = -1.0 if strike_idx % 2 == 0 else 1.0
            self._apply_slash(st, local, speed, wind=0.2, torso_dir=torso_dir)
            st["root_x"] += step * _smoothstep(t)
        return frames

    def _apply_slash(self, st: dict, t: float, speed: float,
                     wind: float, torso_dir: float) -> None:
        """Aplica un corte de katana a un estado (usado por slash y combo)."""
        # Amago (t<wind): sube la espada; luego corta hacia abajo/adelante.
        if t < wind:
            u = t / wind
            shoulder = _lerp(10, -70, _smoothstep(u))   # arma arriba/atrás
            elbow = _lerp(60, 100, _smoothstep(u))
            sword = _lerp(20, -80, _smoothstep(u))
            torso = _lerp(0, 12, _smoothstep(u)) * torso_dir
        else:
            u = (t - wind) / (1.0 - wind)
            cut = _smoothstep(min(1.0, u * (1.0 + 0.3 * speed)))
            shoulder = _lerp(-70, 120, cut)             # baja al frente
            elbow = _lerp(100, 20, cut)
            sword = _lerp(-80, 70, cut)
            torso = _lerp(12, -18, cut) * torso_dir
        st["right_shoulder"] = shoulder
        st["right_elbow"] = elbow
        st["sword_angle"] = sword
        st["torso_angle"] = torso
        # La mano izquierda acompaña (empuñadura a dos manos, aproximada).
        st["left_shoulder"] = 60
        st["left_elbow"] = 100
        st["neck_angle"] = 8 * torso_dir
