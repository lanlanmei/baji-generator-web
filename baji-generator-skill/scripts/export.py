from pathlib import Path


def unique_output(directory, stem, effect, rim, background, size):
    directory=Path(directory); directory.mkdir(parents=True,exist_ok=True)
    base=f"{stem}-{effect}-{rim}-{background}-{size}.png"; path=directory/base; i=2
    while path.exists():
        path=directory/f"{Path(base).stem}-{i}.png"; i+=1
    return path

def animation_output(png_path):
    path=png_path.with_name(f"{png_path.stem}-rotate.gif"); i=2
    while path.exists(): path=png_path.with_name(f"{png_path.stem}-rotate-{i}.gif"); i+=1
    return path
