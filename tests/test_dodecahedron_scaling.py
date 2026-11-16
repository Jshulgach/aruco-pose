"""Physical edge dimensions and saved marker transforms must agree."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from aruco_pose.models.dodecahedron_model import CleanDodecahedronModel, DodecahedronWithMarkers

ROOT = Path(__file__).resolve().parents[1]


def edge_lengths(vertices):
    vertices = np.asarray(vertices)
    return np.linalg.norm(vertices - np.roll(vertices, -1, axis=0), axis=1)


@pytest.mark.parametrize('cls', [CleanDodecahedronModel, DodecahedronWithMarkers])
@pytest.mark.parametrize('edge', [0.001, 0.017, 0.025, 1.0])
def test_all_thirty_edges_have_requested_length(cls, edge):
    model = cls(edge_length=edge)
    edges = set()
    for face in model.pentagon_faces:
        np.testing.assert_allclose(edge_lengths(model.vertices[face]), edge, rtol=1e-12)
        edges.update(tuple(sorted((face[i], face[(i + 1) % 5]))) for i in range(5))
    assert len(edges) == 30
    if hasattr(model, 'extrinsics'):
        for face in model.extrinsics:
            np.testing.assert_allclose(face['extrinsics'][:3], np.mean(face['vertices'], axis=0), atol=1e-15)


@pytest.mark.parametrize('cls', [CleanDodecahedronModel, DodecahedronWithMarkers])
@pytest.mark.parametrize('edge', [0, -0.025, float('nan'), float('inf')])
def test_invalid_edge_lengths(cls, edge):
    with pytest.raises(ValueError, match='finite and positive'):
        cls(edge_length=edge)


@pytest.mark.parametrize('filename,edge', [
    ('dodecahedron_face_map.json', 0.025),
    ('dodecahedron_with_markers.json', 0.017),
])
def test_saved_faces_match_corrected_geometry(filename, edge):
    data = json.loads((ROOT / 'config' / filename).read_text())
    faces = data if isinstance(data, list) else data['faces']
    model = CleanDodecahedronModel(edge_length=edge)
    assert len(faces) == 12
    for face in faces:
        expected = model.vertices[model.pentagon_faces[face['face_index']]]
        np.testing.assert_allclose(face['vertices'], expected, atol=1e-15)
        np.testing.assert_allclose(edge_lengths(face['vertices']), edge, rtol=1e-12)
        if 'extrinsics' in face:
            center = np.mean(face['vertices'], axis=0)
            np.testing.assert_allclose(face['center'], center, atol=1e-15)
            np.testing.assert_allclose(face['extrinsics'][:3], center, atol=1e-15)


def test_tag_group_translations_match_face_centers():
    data = json.loads((ROOT / 'config/aruco_group.json').read_text())
    faces = json.loads((ROOT / 'config/dodecahedron_face_map.json').read_text())
    assert data['edge_length'] == 0.025
    for face in faces:
        tag = data['tags'][str(face['aruco_id'])]
        np.testing.assert_allclose(tag['extrinsics'][:3], np.mean(face['vertices'], axis=0), atol=1e-15)
        assert tag['size'] == 0.025  # Printed-marker size is independent of solid scale.


def test_generator_matches_saved_model_and_accepts_25mm(tmp_path):
    script = ROOT / 'examples/04_custom_models/generate_model_to_json.py'
    spec = importlib.util.spec_from_file_location('model_generator', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    generated = module.generate_model()
    saved = json.loads((ROOT / 'config/dodecahedron_with_markers.json').read_text())
    for actual, expected in zip(generated['faces'], saved['faces']):
        assert actual['aruco_id'] == expected['aruco_id']
        for key in ['vertices', 'center', 'extrinsics']:
            np.testing.assert_allclose(actual[key], expected[key], atol=1e-12)
    output = tmp_path / 'model.json'
    subprocess.run([sys.executable, str(script), '--edge-length', '0.025', '--output', str(output)], check=True)
    generated = json.loads(output.read_text())
    assert generated['edge_length'] == 0.025
    for face in generated['faces']:
        np.testing.assert_allclose(edge_lengths(face['vertices']), 0.025, rtol=1e-12)


def test_example_uses_canonical_models():
    path = ROOT / 'examples/04_custom_models/dodecahedron_model.py'
    spec = importlib.util.spec_from_file_location('example_model', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.CleanDodecahedronModel is CleanDodecahedronModel
    assert module.DodecahedronWithMarkers is DodecahedronWithMarkers
