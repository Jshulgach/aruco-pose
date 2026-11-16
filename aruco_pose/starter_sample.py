"""Deterministic, geometrically rendered samples; these are not camera recordings."""
import csv
from pathlib import Path

import cv2
import numpy as np

from .starter import board_model, marker_image, print_kit, save_json


def render_plane(texture, width_m, height_m, rvec, tvec, matrix, size=(640, 480)):
    height, width = texture.shape
    objects = np.array([[-width_m/2, -height_m/2, 0], [width_m/2, -height_m/2, 0],
                        [width_m/2, height_m/2, 0], [-width_m/2, height_m/2, 0]], dtype=float)
    destination = cv2.projectPoints(objects, rvec, tvec, matrix, np.zeros(5))[0].reshape(4, 2)
    source = np.float32([[0, 0], [width-1, 0], [width-1, height-1], [0, height-1]])
    transform = cv2.getPerspectiveTransform(source, destination.astype(np.float32))
    return cv2.warpPerspective(texture, transform, size, flags=cv2.INTER_LINEAR, borderValue=220)


def create_sample(output):
    output = Path(output)
    print_kit(output)
    matrix = np.array([[700., 0, 320.], [0, 700., 240.], [0, 0, 1.]])
    save_json(output / 'reference_camera.json', {
        'image_width': 640, 'image_height': 480, 'camera_matrix': matrix.tolist(),
        'distortion_coefficients': [0.] * 5, 'synthetic': True})
    checker = np.full((700, 1000), 255, np.uint8)
    for row in range(7):
        for col in range(10):
            if (row+col) % 2 == 0:
                checker[row*100:(row+1)*100, col*100:(col+1)*100] = 0
    board = np.full((840, 840), 255, np.uint8)
    for marker in board_model()['markers']:
        x, y = np.round((np.array(marker['corners_m'][0])[:2]+.06)*7000).astype(int)
        board[y:y+280, x:x+280] = marker_image(marker['id'])
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    rng = np.random.default_rng(42)
    for name in ['calibration', 'tracking']:
        writer = cv2.VideoWriter(str(output / f'{name}.mp4'), fourcc, 20., (640, 480))
        if not writer.isOpened():
            raise ValueError('OpenCV cannot encode mp4v samples on this system')
        truth = []
        try:
            count = 30 if name == 'calibration' else 120
            for i in range(count):
                if name == 'calibration':
                    rvec = rng.uniform([-.55, -.55, -.3], [.55, .55, .3])
                    tvec = rng.uniform([-.045, -.035, .46], [.045, .035, .65])
                    frame = render_plane(checker, .2, .14, rvec, tvec, matrix)
                else:
                    phase = i / 20.
                    rvec = np.array([.25*np.sin(phase), .3*np.cos(phase*.7), .12*np.sin(phase*.5)])
                    tvec = np.array([.035*np.sin(phase), .025*np.cos(phase), .42+.04*np.sin(phase*.6)])
                    frame = render_plane(board, .12, .12, rvec, tvec, matrix)
                    # Deliberate complete loss, and a period with only two markers visible.
                    if 50 <= i < 60:
                        frame[:] = 220
                    elif 85 <= i < 100:
                        occluded = board.copy()
                        occluded[:, :420] = 255
                        frame = render_plane(occluded, .12, .12, rvec, tvec, matrix)
                    truth.append([i, i/20., *tvec, *rvec])
                writer.write(cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR))
        finally:
            writer.release()
        if truth:
            with (output / 'ground_truth.csv').open('w', newline='') as stream:
                csv_writer = csv.writer(stream)
                csv_writer.writerow(['frame', 'time_s', 'tx_m', 'ty_m', 'tz_m', 'rx_rad', 'ry_rad', 'rz_rad'])
                csv_writer.writerows(truth)
    save_json(output / 'sample_info.json', {
        'synthetic': True, 'generator': 'python -m aruco_pose kit sample', 'seed': 42,
        'fps': 20, 'tracking_frames': 120, 'calibration_views': 30,
        'description': 'Perspective-rendered DICT_5X5_100 board and checkerboard; not real-world accuracy evidence.',
        'complete_loss_frames': [50, 59], 'partial_occlusion_frames': [85, 99],
        'license': 'Apache-2.0, generated from this repository; no third-party footage'})
    return output
