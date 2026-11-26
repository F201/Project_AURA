"""Stage phone-size copies of the existing Live2D files for the Android build."""

from pathlib import Path
import shutil

from PIL import Image


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    public = project / "desktop" / "public"
    assets = project / "mobile" / "build" / "assets" / "avatar"
    source = public / "models" / "hutao"
    target = assets / "models" / "hutao"

    shutil.copyfile(public / "live2dcubismcore.min.js", assets / "live2dcubismcore.min.js")
    for file in source.rglob("*"):
        if not file.is_file():
            continue
        output = target / file.relative_to(source)
        output.parent.mkdir(parents=True, exist_ok=True)
        if file.name.startswith("texture_") and file.suffix.lower() == ".png":
            with Image.open(file) as texture:
                texture.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
                texture.save(output)
        else:
            shutil.copyfile(file, output)


if __name__ == "__main__":
    main()
