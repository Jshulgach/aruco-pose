"""Convert this project's simple vector print sheet to a dimension-preserving PDF.

Developer asset tool; requires reportlab. The SVG remains the canonical source.
"""
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm


def render(source, output):
    root = ET.parse(source).getroot()
    if root.attrib.get("viewBox") != "0 0 210 297":
        raise ValueError("Expected millimeter A4 artwork")
    pdf = canvas.Canvas(str(output), pagesize=(210*mm, 297*mm), pageCompression=1)
    pdf.setTitle("aruco-pose - 25 mm dodecahedron faces - print actual size")
    for element in root:
        tag = element.tag.rsplit("}", 1)[-1]
        attrs = element.attrib
        pdf.setFillColorRGB(0, 0, 0)
        pdf.setStrokeColorRGB(0, 0, 0)
        pdf.setLineWidth(float(attrs.get("stroke-width", .15))*mm)
        pdf.setDash([float(v)*mm for v in attrs["stroke-dasharray"].split(",")] if "stroke-dasharray" in attrs else [])
        if attrs.get("fill") == "white":
            pdf.setFillColorRGB(1, 1, 1)
        if tag == "rect":
            x, y, width, height = [float(attrs.get(key, 0)) for key in ("x", "y", "width", "height")]
            pdf.rect(x*mm, (297-y-height)*mm, width*mm, height*mm, stroke=0, fill=1)
        elif tag == "line":
            x1, y1, x2, y2 = [float(attrs[key]) for key in ("x1", "y1", "x2", "y2")]
            pdf.line(x1*mm, (297-y1)*mm, x2*mm, (297-y2)*mm)
        elif tag == "polygon":
            points = [tuple(map(float, point.split(","))) for point in attrs["points"].split()]
            path = pdf.beginPath()
            path.moveTo(points[0][0]*mm, (297-points[0][1])*mm)
            for x, y in points[1:]:
                path.lineTo(x*mm, (297-y)*mm)
            path.close()
            pdf.drawPath(path, stroke=1, fill=0)
        elif tag == "text":
            pdf.setFont("Helvetica", float(attrs["font-size"])*mm)
            draw = pdf.drawCentredString if attrs.get("text-anchor") == "middle" else pdf.drawString
            draw(float(attrs["x"])*mm, (297-float(attrs["y"]))*mm, element.text or "")
        else:
            raise ValueError(f"Unsupported print primitive: {tag}")
    pdf.showPage()
    pdf.save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    render(args.source, args.output)
