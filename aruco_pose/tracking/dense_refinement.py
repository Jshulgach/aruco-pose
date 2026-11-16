import cv2
import numpy as np


def refine_pose(pose_init, model_image, camera_image, J_func, max_iter=10, alpha=0.5):
    p = pose_init.copy()
    for _ in range(max_iter):
        residuals, J = J_func(p, model_image, camera_image)
        delta_p = np.linalg.pinv(J.T @ J) @ J.T @ residuals
        p_new = p + alpha * delta_p
        if np.linalg.norm(delta_p) < 1e-4:
            break
        p = p_new
    return p


def draw_dodecahedron_overlay(image, model, K, R=None, t=None, draw_ids=True):
    if R is None:
        R = np.eye(3)
    if t is None:
        t = np.array(
            [[0.0], [0.0], [0.0]], dtype=np.float32
        )  # pulls the model in front of camera

    verts = model.vertices
    centers = model.get_face_centers()
    faces = model.pentagon_faces

    # Project 3D points to 2D
    rvec, _ = cv2.Rodrigues(R)
    projected_verts, _ = cv2.projectPoints(verts, rvec, t, K, np.zeros((5, 1)))
    projected_verts = projected_verts.squeeze().astype(int)

    # Project centers too
    projected_centers, _ = cv2.projectPoints(centers, rvec, t, K, np.zeros((5, 1)))
    projected_centers = projected_centers.squeeze().astype(int)

    # Draw edges
    for idx, face in enumerate(faces):
        pts = projected_verts[face]
        cv2.polylines(image, [pts], isClosed=True, color=(255, 255, 0), thickness=2)

        # Optionally draw face centers and ID labels
        if draw_ids:
            c = tuple(projected_centers[idx])
            cv2.circle(image, c, 3, (0, 0, 255), -1)
            cv2.putText(
                image,
                f"ID {idx}",
                (c[0] + 5, c[1] - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 0, 255),
                1,
            )

    return image


def estimate_pose_kabsch(object_points, camera_points):
    object_points = np.array(object_points)
    camera_points = np.array(camera_points)

    centroid_obj = np.mean(object_points, axis=0)
    centroid_cam = np.mean(camera_points, axis=0)

    X = object_points - centroid_obj
    Y = camera_points - centroid_cam

    H = X.T @ Y
    U, S, Vt = np.linalg.svd(H)
    R = Vt.T @ U.T

    if np.linalg.det(R) < 0:
        Vt[2, :] *= -1
        R = Vt.T @ U.T

    t = centroid_cam - R @ centroid_obj
    return R, t.reshape(3, 1)


class PoseKalmanFilter:
    def __init__(self):
        self.kf = cv2.KalmanFilter(6, 6)  # [rvec, tvec] in state + measurement
        self.kf.measurementMatrix = np.eye(6, dtype=np.float32)
        self.kf.transitionMatrix = np.eye(6, dtype=np.float32)
        self.kf.processNoiseCov = np.eye(6, dtype=np.float32) * 1e-3
        self.kf.measurementNoiseCov = np.eye(6, dtype=np.float32) * 1e-2
        self.kf.errorCovPost = np.eye(6, dtype=np.float32)
        self.kf.statePost = np.zeros((6, 1), dtype=np.float32)

    def update(self, rvec, tvec):
        measurement = np.vstack((rvec.astype(np.float32), tvec.astype(np.float32)))
        self.kf.correct(measurement)
        pred = self.kf.predict()
        rvec_filtered = pred[:3]
        tvec_filtered = pred[3:]
        return rvec_filtered, tvec_filtered


def _shared_result(model, corners, ids, matrix, distortion, marker_size):
    from ..pose import Tracker, TrackerConfig, model_from_extrinsics

    if hasattr(model, "extrinsics"):
        raw = {int(face["aruco_id"]): face["extrinsics"] for face in model.extrinsics}
        data = model_from_extrinsics(raw, marker_size)
    else:
        points = model.get_marker_corners(marker_size)
        data = {
            "units": "meters",
            "object_id": "dodecahedron",
            "dictionary": "DICT_5X5_100",
            "markers": [
                {"id": int(mid), "corners_m": value.tolist()}
                for mid, value in zip(model.aruco_id_order, points)
            ],
        }
    return Tracker(
        data, matrix, distortion, config=TrackerConfig(min_markers=1)
    ).estimate(corners, ids, 0.0)


def estimate_pose_from_individual_markers(
    model, corners, ids, camera_matrix, dist_coeffs, marker_size
):
    """Compatibility result (success, rotation matrix, translation, camera-space center)."""
    result = _shared_result(
        model, corners, ids, camera_matrix, dist_coeffs, marker_size
    )
    if result.pose is None:
        return False, None, None, None
    return (
        True,
        result.pose.matrix[:3, :3],
        result.pose.tvec,
        np.array(result.pose.translation_m),
    )


def estimate_pose_from_dodecahedron(
    model, corners, ids, camera_matrix, dist_coeffs, marker_size=0.015
):
    """Compatibility result (success, rvec, tvec, pixel center); lengths are meters."""
    result = _shared_result(
        model, corners, ids, camera_matrix, dist_coeffs, marker_size
    )
    if result.pose is None:
        return False, None, None, None
    pixel = cv2.projectPoints(
        np.zeros((1, 3)), result.pose.rvec, result.pose.tvec, camera_matrix, dist_coeffs
    )[0][0, 0]
    return True, result.pose.rvec, result.pose.tvec, pixel


def overlay_virtual_dodecahedron(
    frame, model, corners, ids, k_matrix, d_coeffs, marker_size
):
    from ..utils.dodecahedron_overlay import draw_dodecahedron

    result = _shared_result(model, corners, ids, k_matrix, d_coeffs, marker_size)
    if result.pose is not None:
        draw_dodecahedron(
            frame, result.pose.rvec, result.pose.tvec, model, k_matrix, d_coeffs
        )
    return frame
