"""
main.py
=======

Punto de entrada del motor de animación 2D del ninja.

Genera las piezas gráficas (si faltan) y abre el visualizador interactivo.

Uso
---
    python main.py                 # abre el visualizador en 'idle'
    python main.py walk            # abre el visualizador en un movimiento
    python main.py --list          # lista los movimientos disponibles
    python main.py --assets        # (re)genera las piezas PNG y sale
    python main.py --export walk out.gif   # exporta una animación a GIF

Este archivo sólo orquesta los módulos; toda la lógica vive en:
config, skeleton, kinematics, character, motions, assets, renderer, viewer.
"""

from __future__ import annotations

import argparse
import sys

import assets
import motions


def _export(movement: str, path: str, seed: int | None = None) -> None:
    """Exporta una animación a un GIF (útil para informes / documentación)."""
    from renderer import Renderer

    renderer = Renderer()
    frames = motions.MotionGenerator().generate(movement, seed=seed)
    images = [renderer.render(f, background=(240, 242, 246, 255)).convert("P")
              for f in frames]
    images[0].save(path, save_all=True, append_images=images[1:],
                   duration=1000 // 30, loop=0, disposal=2)
    print(f"Animación '{movement}' exportada a {path} ({len(images)} frames).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Motor de animación 2D del ninja.")
    parser.add_argument("movement", nargs="?", default="idle",
                        help="movimiento inicial del visualizador")
    parser.add_argument("--list", action="store_true",
                        help="lista los movimientos disponibles y sale")
    parser.add_argument("--assets", action="store_true",
                        help="(re)genera las piezas PNG y sale")
    parser.add_argument("--export", nargs=2, metavar=("MOV", "PATH"),
                        help="exporta un movimiento a un GIF y sale")
    parser.add_argument("--seed", type=int, default=None,
                        help="semilla aleatoria (reproducibilidad)")
    args = parser.parse_args(argv)

    if args.list:
        print("Movimientos disponibles:")
        for i, m in enumerate(motions.MotionGenerator().available(), 1):
            print(f"  {i:>2}. {m}")
        return 0

    if args.assets:
        paths = assets.ensure_assets(force=True)
        print(f"Piezas generadas en {assets.config.ASSET_DIR}:")
        for name in paths:
            print(f"  - {name}")
        return 0

    if args.export:
        _export(args.export[0], args.export[1], seed=args.seed)
        return 0

    # Modo por defecto: visualizador interactivo.
    from viewer import launch
    launch(args.movement)
    return 0


if __name__ == "__main__":
    sys.exit(main())
