# 🥷 Motor de animación 2D de un ninja con redes recurrentes

Generación de **animaciones 2D** de un personaje (un ninja con katana) mediante un
**esqueleto articulado** + **Forward Kinematics**, y una **red neuronal recurrente**
(RNN/LSTM/GRU) que aprende a generar el movimiento.

El proyecto tiene **dos etapas**:

- **Etapa 1 — motor de animación** (sin Deep Learning): esqueleto, cinemática
  directa, generador procedural de movimientos y renderizado. Módulos `.py`.
- **Etapa 2 — Deep Learning** (con PyTorch): una red recurrente sustituye al
  generador matemático prediciendo el estado cinemático. Todo en
  [`development.ipynb`](development.ipynb), Secciones 9–11.

La clave del diseño: el personaje se representa por **ángulos** (no coordenadas), de
modo que la red predice el estado y el **mismo** motor de cinemática + render lo
dibuja, sin cambiar entre etapas.

---

## Estructura del proyecto

```
ProyectoFinal/
├── config.py        skeleton.py   kinematics.py   character.py
├── motions.py       assets.py     renderer.py     viewer.py     main.py
├── development.ipynb        # notebook: depuración (Etapa 1) + entrenamiento (Etapa 2)
├── requirements.txt
├── informe/                 # artículo científico (LaTeX + figuras)
└── ppt/                     # presentación (.pptx) + script generador
```

> **Artefactos generados (no versionados).** `assets/` (piezas PNG), `*.pt`
> (modelos entrenados) y `normalizer.npz` **se crean solos** al ejecutar
> `main.py` o el notebook, por eso están en `.gitignore`. Un clon limpio funciona
> sin ellos: se regeneran en la primera ejecución.

---

## Arquitectura (módulos independientes)

| Módulo | Responsabilidad |
|---|---|
| [`config.py`](config.py) | Parámetros globales: longitudes, límites articulares, tamaño, resolución, colores. |
| [`skeleton.py`](skeleton.py) | Árbol jerárquico de articulaciones (raíz = cadera). |
| [`kinematics.py`](kinematics.py) | **Forward Kinematics**: estado → coordenadas (x, y). Nunca se modificará en la 2.ª etapa. |
| [`character.py`](character.py) | Estado cinemático, límites, y conversión estado ↔ vector (interfaz para la RNN). |
| [`motions.py`](motions.py) | Generador **procedural** de movimientos (senos/cosenos/interpolaciones). |
| [`assets.py`](assets.py) | Generación procedural de las piezas PNG (fondo transparente). |
| [`renderer.py`](renderer.py) | Renderizado 2D: compone las piezas PNG rotadas por sus pivotes. No se modificará en la 2.ª etapa. |
| [`viewer.py`](viewer.py) | Visualizador interactivo (ventana Matplotlib). |
| [`main.py`](main.py) | Punto de entrada / CLI. |
| [`development.ipynb`](development.ipynb) | Notebook completo: depuración de la Etapa 1 y entrenamiento/comparación de modelos (Etapa 2). |

## Representación del personaje

El personaje **no** se representa con coordenadas absolutas, sino con un **estado
cinemático** de ángulos relativos por articulación (más root, velocidades, fase):

```
root_x, root_y, root_rotation, velocity_x, velocity_y,
torso_angle, neck_angle,
left_shoulder, left_elbow, right_shoulder, right_elbow,
left_hip, left_knee, right_hip, right_knee,
sword_angle, movement, phase
```

Las coordenadas se **calculan dinámicamente** con Forward Kinematics; las longitudes
de los segmentos son constantes. Cada articulación tiene **límites físicos** que se
corrigen automáticamente (codo 0–150°, rodilla 0–140°, cuello ±40°, espalda ±30°…).

## Esqueleto

```
Hip (root)
├── Chest ── Neck ── Head
│   ├── L Shoulder ── L Elbow ── L Hand
│   └── R Shoulder ── R Elbow ── R Hand ── Sword
├── L Hip ── L Knee ── L Foot
└── R Hip ── R Knee ── R Foot
```

## Movimientos disponibles

`idle`, `walk`, `run`, `jump`, `dash`, `roll`, `punch`, `kick`, `sword_slash`,
`sword_combo`. Cada uno genera 30–60 frames y añade pequeñas variaciones aleatorias
(velocidad, amplitud, altura de salto, inclinación del torso, longitud del paso,
velocidad del ataque), de modo que **nunca se generan dos secuencias idénticas**.

### Encadenado de acciones

`MotionGenerator.compose([...])` concatena varios movimientos en **una sola
secuencia continua** (más larga), con transiciones suaves y traslación acumulada:

```python
gen = motions.MotionGenerator()
chained = gen.compose(["run", "jump", "sword_slash"])   # corre, salta y ataca
```

En el notebook, la **Sección 10** muestra el encadenado procedural y además un
modelo recurrente **condicionado por la acción**, capaz de generar coreografías
(p. ej. `run → kick → sword_slash`) **a demanda**.

---

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

```bash
python main.py                       # visualizador interactivo (idle)
python main.py walk                  # visualizador en un movimiento concreto
python main.py --list                # lista de movimientos
python main.py --assets              # (re)genera las piezas PNG
python main.py --export walk out.gif # exporta una animación a GIF
```

### Controles del visualizador

| Tecla | Acción |
|---|---|
| ← / → (o ↑ / ↓) | cambiar de movimiento |
| 1 … 0 | seleccionar movimiento por índice |
| espacio | pausar / reanudar |
| `r` | reiniciar la animación |
| `n` | nueva variante aleatoria |
| `s` / `j` / `b` | mostrar/ocultar esqueleto / articulaciones / piezas |
| `q` | salir |

### Notebook de desarrollo

```bash
jupyter notebook development.ipynb
```

9 secciones: configuración, esqueleto, Forward Kinematics manual, renderizado con
capas de depuración, prueba de movimientos, variabilidad, tablas de depuración,
preparación para Deep Learning (`get_state(frame)`) y **entrenamiento del modelo
(Etapa 2)**.

### Sección 9 — Entrenamiento (Etapa 2, requiere PyTorch)

Implementa el reemplazo del generador matemático por una red recurrente:

- **Dataset** `(N, T, D)` generado con cientos de variantes de cada movimiento.
- **Ventanas deslizantes** (frames `[i:i+W]` → frame `[i+W]`) y split train/val.
- **Normalización** z-score (guardada en `normalizer.npz`).
- **Modelo** `RNN/LSTM/GRU → Dense → 17`, intercambiable con un parámetro.
- **Entrenamiento** con curvas de pérdida y guardado del mejor modelo (`best_model.pt`).
- **Generación autoregresiva** y comparación original vs. red, lado a lado.
- **Errores** por variable (MAE/RMSE) y **comparación** RNN vs LSTM vs GRU.

Los estados que produce la red se renderizan con el **mismo** `kinematics` +
`renderer` de la Etapa 1 (el motor gráfico no se modifica).

### Sección 10 — Encadenado de acciones

- **Procedural**: `gen.compose([...])` para secuencias multi-acción controladas.
- **Red condicionada**: un GRU que recibe la acción deseada por frame y genera
  coreografías a demanda (`cond_model.pt`).

---

## Preparación para la 2.ª etapa (Deep Learning)

Una LSTM/GRU generará únicamente el **estado cinemático** (`config.STATE_ORDER`).
El resto del pipeline no cambia:

```
estado (root, velocidades, ángulos, fase)
        │
        ▼
kinematics.forward_kinematics  ──►  renderer      (idénticos en ambas etapas)
```

Utilidades clave ya disponibles:

- `character.get_state_vector(state)` → vector numérico en orden canónico.
- `character.state_from_vector(vec)` → estado renderizable (salida de la red).
- `character.sequence_to_matrix(frames)` → matriz `(T, D)` para entrenar la RNN.
