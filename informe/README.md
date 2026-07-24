# Informe — Compilación

Artículo científico en LaTeX del proyecto (2–4 páginas sin referencias).

```
informe/
├── informe.tex          # documento principal
└── figs/
    ├── fig_pipeline.png # esqueleto + FK y render final
    ├── fig_loss.png     # curvas de pérdida del GRU
    └── fig_results.png  # resultados cualitativos (patada NN + encadenado)
```

## Opción A — Overleaf (recomendada, sin instalar nada)

1. Entra a <https://overleaf.com> → **New Project** → **Upload Project**.
2. Sube la carpeta `informe/` completa (o un ZIP de ella).
3. Compila con **pdfLaTeX**. Overleaf ya incluye todos los paquetes usados.

## Opción B — Local (requiere instalar LaTeX)

```bash
brew install --cask mactex-no-gui     # macOS (~4 GB), o basictex si prefieres
cd informe
pdflatex informe.tex && pdflatex informe.tex   # dos veces (referencias cruzadas)
```

> Se compila **dos veces** para que se resuelvan las referencias a figuras y
> tablas (`\ref`).

## Paquetes usados

Todos estándar en cualquier distribución TeX:
`inputenc`, `fontenc`, `babel(spanish)`, `geometry`, `graphicx`, `amsmath`,
`booktabs`, `caption`, `url`.

## Regenerar las figuras

Las figuras se generaron desde el propio proyecto (modelo entrenado
`best_model.pt` + `normalizer.npz`). Si reentrenas y quieres actualizarlas,
vuelve a ejecutar las celdas correspondientes de `development.ipynb` o los
scripts de generación de figuras.

## Nota sobre extensión

El cuerpo tiene ~2.900 palabras + 3 figuras + 2 tablas, lo que da
aproximadamente **3–3,5 páginas** a dos columnas. Si al compilar excediera las
4 páginas, se puede recortar en la discusión y las conclusiones (son las
secciones con más margen) sin tocar el contenido técnico exigido.
