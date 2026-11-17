"""Assemble the static GitHub Pages project showcase using only approved assets."""
import argparse
from html.parser import HTMLParser
from pathlib import Path
import shutil
from urllib.parse import unquote, urlparse
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DODECAHEDRON_FILES = (
    "README.md", "LICENSE", "faces.svg", "faces.pdf", "model.json", "assembly.json",
    "checkerboard.svg", "tracking.mp4", "replay_camera.json", "ground_truth.csv",
    "replay_validation.json",
)


class PageReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.references = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        for key in ["href", "src", "poster"]:
            if key in attrs:
                self.references.append(attrs[key])


def validate_page(output):
    output = Path(output)
    parser = PageReferences()
    parser.feed((output / "index.html").read_text(encoding="utf-8"))
    for reference in parser.references:
        parsed = urlparse(reference)
        if parsed.scheme or parsed.netloc:
            continue
        if parsed.path:
            path = (output / unquote(parsed.path)).resolve()
            if not path.is_relative_to(output.resolve()) or not path.is_file():
                raise ValueError(f"Missing/invalid page resource: {reference}")
        elif parsed.fragment and parsed.fragment not in parser.ids:
            raise ValueError(f"Missing page section: {reference}")


def build_page(output):
    output = Path(output).resolve()
    if output == ROOT or output == ROOT / "site" or output in (ROOT / "site").parents:
        raise ValueError("Build output must be separate from the repository/site source")
    output.mkdir(parents=True, exist_ok=True)
    for name in ["index.html", "styles.css", "app.js"]:
        shutil.copyfile(ROOT / "site" / name, output / name)
    assets = output / "assets"
    assets.mkdir(exist_ok=True)
    for name in ["favicon.svg", "tracking-demo.mp4", "preview.jpg",
                 "dodecahedron-demo.mp4", "dodecahedron-preview.jpg", "dodecahedron-demo.json"]:
        shutil.copyfile(ROOT / "site" / "assets" / name, assets / name)
    for name in ["marker_board.svg", "checkerboard.svg", "board.json"]:
        shutil.copyfile(ROOT / "assets" / "starter" / name, assets / name)
    downloads = output / "downloads"
    downloads.mkdir(exist_ok=True)
    with zipfile.ZipFile(downloads / "starter-kit.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / "assets" / "starter").iterdir()):
            if path.is_file() and path.suffix in {".mp4", ".json", ".svg", ".csv"}:
                archive.write(path, "starter/" + path.name)
    with zipfile.ZipFile(downloads / "dodecahedron-kit.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name in DODECAHEDRON_FILES:
            archive.write(ROOT / "assets/dodecahedron" / name, "dodecahedron/" + name)
    for name in ["faces.pdf", "README.md"]:
        shutil.copyfile(ROOT / "assets/dodecahedron" / name, downloads / ("dodecahedron-" + name))
    (output / ".nojekyll").write_text("", encoding="utf-8")
    validate_page(output)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "output/project-page")
    args = parser.parse_args()
    print(f"Built and validated project page: {build_page(args.output)}")
