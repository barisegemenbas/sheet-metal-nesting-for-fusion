# Contributing

Thanks for helping! Issues and pull requests are welcome in English or Turkish.

## Reporting a problem

Open an [issue](https://github.com/barisegemenbas/sheet-metal-nesting-for-fusion/issues/new/choose) and include:

- your system (macOS / Windows, Apple silicon or Intel) and the add-in version (bottom of its dialog);
- what you did and what happened, with a screenshot of any error;
- `_log.txt` from the output folder (and `_install.log` from the add-in folder for install problems);
- if you can, the part (or a simplified copy) that causes it.

Windows reports are especially useful: the Windows installer has not been tested on a real PC yet.

## How the code is laid out

| Path | What |
|---|---|
| `SacAcinimDXF/SacAcinimDXF.py` | the dialog (runs inside Fusion; changes need *Stop / Run* of the add-in) |
| `SacAcinimDXF/sac_core.py` | flattening in Fusion: copies, flat patterns, thickness changes, DXF export (reloaded on every click) |
| `SacAcinimDXF/nest_dxf.py` | runs in the add-in's own Python: DXF styling, model-making lines, nesting, pictures, scrap and cost |
| `SacAcinimDXF/dil.py` | interface text: the code is written in Turkish, `EN` holds the English; add a language there |
| `installer/` | the Mac and Windows installers |
| `tools/build_release.sh` | builds the release zip; `tools/build_guides.py` builds the PDF guides |

## Pull requests

- Keep changes focused; match the surrounding style (short functions, comments that say why).
- Test in Fusion with a copy of a real design, never the original.
- New user-facing text goes through `L()` with its English in `dil.py`.
- Bump `version` in `SacAcinimDXF/SacAcinimDXF.manifest` (fix: last number, feature: middle number).

By contributing you agree that your contribution is licensed under the [MIT License](LICENSE).
