"""Generate the printable kit from the exact layout used by the 3D replay."""
import argparse
import json
from pathlib import Path
import shutil
from xml.sax.saxutils import escape

import numpy as np

from scripts.generate_dodecahedron_demo import D, K, ROOT, SIZE, make_target
from aruco_pose.starter import marker_image, save_json


def face_layouts():
    geometry, model, normals = make_target()
    edges = {}
    for index, face in enumerate(geometry.pentagon_faces):
        for a, b in zip(face, face[1:] + face[:1]):
            edges.setdefault(tuple(sorted((a, b))), []).append(index)
    if len(edges) != 30 or any(len(owners) != 2 for owners in edges.values()):
        raise ValueError("Target must have 30 edges, each shared by exactly two faces")
    labels = {edge: f"E{index+1:02}" for index, edge in enumerate(sorted(edges))}
    layouts = []
    for index, (face, marker, normal) in enumerate(zip(geometry.pentagon_faces, model["markers"], normals)):
        vertices = geometry.vertices[face]
        center = vertices.mean(axis=0)
        x = vertices[1] - vertices[0]
        x /= np.linalg.norm(x)
        basis = np.stack([x, np.cross(x, normal)])
        polygon = (vertices-center) @ basis.T * 1000
        # Clockwise in the page's y-down coordinate system.
        a, b = polygon[1]-polygon[0], polygon[2]-polygon[1]
        if a[0]*b[1] - a[1]*b[0] < 0:
            polygon = polygon[::-1]
            face = face[::-1]
        sides = []
        for a, b in zip(face, face[1:] + face[:1]):
            key = tuple(sorted((a, b)))
            neighbor = next(owner for owner in edges[key] if owner != index)
            sides.append({"label": labels[key], "vertices": [a, b],
                          "neighbor_marker_id": model["markers"][neighbor]["id"],
                          "tab": index < neighbor})
        layouts.append({"marker_id": marker["id"], "polygon_mm": polygon.tolist(),
                        "marker_corners_mm": ((np.array(marker["corners_m"])-center) @ basis.T*1000).tolist(),
                        "sides": sides})
    return layouts


def printable_svg(layouts):
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">',
           '<rect width="210" height="297" fill="white"/>']
    def text(x, y, content, size=3, **attrs):
        attributes = " ".join(f'{key.replace("_", "-")}="{value}"' for key, value in attrs.items())
        svg.append(f'<text x="{x:.5f}" y="{y:.5f}" font-family="Helvetica,Arial,sans-serif" font-size="{size}" {attributes}>{escape(content)}</text>')
    def line(a, b, dashed=False):
        dash = ' stroke-dasharray="1,0.7"' if dashed else ''
        svg.append(f'<line x1="{a[0]:.5f}" y1="{a[1]:.5f}" x2="{b[0]:.5f}" y2="{b[1]:.5f}" stroke="black" stroke-width="0.15"{dash}/>')
    text(14, 14, "aruco-pose / DODECAHEDRON KIT", 5)
    text(14, 23, "25 mm edges / 15 mm markers / DICT_5X5_100", 3)
    text(14, 30, "Print at 100%. Cut solid lines; score dashed lines. Read README before assembly.", 2.7)
    for index, layout in enumerate(layouts):
        offset = np.array([40 + 65*(index % 3), 65 + 58*(index // 3)])
        polygon = np.array(layout["polygon_mm"]) + offset
        outline = []
        for a, b, side in zip(polygon, np.roll(polygon, -1, axis=0), layout["sides"]):
            edge = b-a
            outward = np.array([edge[1], -edge[0]]) / np.linalg.norm(edge)
            outline.append(a)
            if side["tab"]:
                outline.extend([a + .15*edge + 4*outward, b - .15*edge + 4*outward])
                line(a, b, dashed=True)
            label = (a+b)/2 - 2.2*outward
            text(*label, side["label"], 1.6, text_anchor="middle")
        points = " ".join(f"{p[0]:.5f},{p[1]:.5f}" for p in outline)
        svg.append(f'<polygon points="{points}" fill="none" stroke="black" stroke-width="0.15"/>')
        # Real ArUco bits: the top-left corner is the model's first corner.
        origin = np.array(layout["marker_corners_mm"])[0] + offset
        bits = marker_image(layout["marker_id"], 7)
        for row, col in zip(*np.where(bits == 0)):
            x, y = origin + np.array([col, row])*15/7
            svg.append(f'<rect x="{x:.8f}" y="{y:.8f}" width="{15/7:.8f}" height="{15/7:.8f}" fill="black"/>')
        text(offset[0], offset[1]-26, f"FACE / ID {layout['marker_id']}", 2.5, text_anchor="middle")
    line(np.array([15, 282]), np.array([65, 282]))
    line(np.array([15, 280]), np.array([15, 284]))
    line(np.array([65, 280]), np.array([65, 284]))
    text(15, 289, "Measure: 50 mm", 2.7)
    text(85, 281, "Match E01 to E01, E02 to E02, etc.", 2.7)
    text(85, 287, "Markers outside. Glue tabs inside. Do not mirror.", 2.7)
    svg.append("</svg>")
    return "\n".join(svg) + "\n"


def build(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    _, model, _ = make_target()
    layouts = face_layouts()
    (output / "faces.svg").write_text(printable_svg(layouts), encoding="utf-8")
    save_json(output / "model.json", model)
    save_json(output / "assembly.json", {"units": "millimeters", "faces": layouts})
    save_json(output / "replay_camera.json", {"image_width": SIZE[0], "image_height": SIZE[1],
        "camera_matrix": K.tolist(), "distortion_coefficients": D.tolist(), "synthetic": True,
        "note": "Only for tracking.mp4. Calibrate your own physical camera."})
    shutil.copyfile(ROOT / "assets/starter/checkerboard.svg", output / "checkerboard.svg")
    shutil.copyfile(ROOT / "docs/DODECAHEDRON_KIT.md", output / "README.md")
    shutil.copyfile(ROOT / "LICENSE", output / "LICENSE")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "assets/dodecahedron")
    args = parser.parse_args()
    print(build(args.output))
