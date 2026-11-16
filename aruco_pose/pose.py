"""Shared rigid-marker pose API. All poses map child/object points into parent/camera.

Planar solutions use IPPE's two branches. Unresolved ambiguity carries candidates
but no publishable pose. Robust fitting excludes corners and requires marker-level
support; a rejected observation is never replaced with a prediction.
"""

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Optional, Tuple

import cv2
import numpy as np
from scipy.spatial.transform import Rotation

from .core.detector import UnifiedArucoDetector


@dataclass(frozen=True)
class Pose:
    """p_parent = R @ p_child + t; translation in meters, quaternion x,y,z,w."""

    parent_frame: str
    child_frame: str
    translation_m: Tuple[float, float, float]
    quaternion_xyzw: Tuple[float, float, float, float]

    def __post_init__(self):
        t = np.asarray(self.translation_m, dtype=float)
        q = np.asarray(self.quaternion_xyzw, dtype=float)
        if not self.parent_frame or not self.child_frame:
            raise ValueError("Pose frame names must be nonempty")
        if t.shape != (3,) or not np.isfinite(t).all():
            raise ValueError("Translation must contain three finite meter values")
        if (
            q.shape != (4,)
            or not np.isfinite(q).all()
            or not np.isclose(np.linalg.norm(q), 1.0, atol=1e-6)
        ):
            raise ValueError(
                "Quaternion must contain four finite unit values in x,y,z,w order"
            )
        object.__setattr__(self, "translation_m", tuple(map(float, t)))
        object.__setattr__(
            self, "quaternion_xyzw", tuple(map(float, q / np.linalg.norm(q)))
        )

    @classmethod
    def from_rvec(cls, rvec, tvec, parent_frame, child_frame):
        return cls(
            parent_frame,
            child_frame,
            tuple(np.asarray(tvec).ravel()),
            tuple(Rotation.from_rotvec(np.asarray(rvec).ravel()).as_quat()),
        )

    @property
    def rvec(self):
        return Rotation.from_quat(self.quaternion_xyzw).as_rotvec().reshape(3, 1)

    @property
    def tvec(self):
        return np.array(self.translation_m).reshape(3, 1)

    @property
    def matrix(self):
        result = np.eye(4)
        result[:3, :3] = Rotation.from_quat(self.quaternion_xyzw).as_matrix()
        result[:3, 3] = self.translation_m
        return result

    def transform_points(self, points):
        return (
            Rotation.from_quat(self.quaternion_xyzw).apply(points) + self.translation_m
        )

    def inverse(self):
        rotation = Rotation.from_quat(self.quaternion_xyzw).inv()
        return Pose(
            self.child_frame,
            self.parent_frame,
            tuple(rotation.apply(-np.array(self.translation_m))),
            tuple(rotation.as_quat()),
        )

    def compose(self, other):
        """Return self @ other, requiring self.child_frame == other.parent_frame."""
        if self.child_frame != other.parent_frame:
            raise ValueError("Cannot compose transforms with mismatched frames")
        rotation = Rotation.from_quat(self.quaternion_xyzw) * Rotation.from_quat(
            other.quaternion_xyzw
        )
        return Pose(
            self.parent_frame,
            other.child_frame,
            tuple(self.transform_points(other.translation_m)),
            tuple(rotation.as_quat()),
        )


@dataclass(frozen=True)
class MarkerObservation:
    marker_id: int
    corners_px: tuple
    inlier_corners: Tuple[int, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class PoseCandidate:
    pose: Pose
    reprojection_rmse_px: float


@dataclass(frozen=True)
class PoseResult:
    timestamp_s: float
    object_id: str
    parent_frame: str
    child_frame: str
    status: str
    reason: str
    pose: Optional[Pose] = None
    observations: Tuple[MarkerObservation, ...] = ()
    inlier_marker_ids: Tuple[int, ...] = ()
    rejected_marker_ids: Tuple[int, ...] = ()
    reprojection_rmse_px: Optional[float] = None
    candidates: Tuple[PoseCandidate, ...] = ()
    ambiguity_resolved_by: str = ""

    def __post_init__(self):
        if not np.isfinite(self.timestamp_s):
            raise ValueError("timestamp_s must be finite")
        if self.status not in ("measured", "lost", "rejected", "ambiguous"):
            raise ValueError("Unknown pose status")
        if (self.pose is not None) != (self.status == "measured"):
            raise ValueError("Only measured results carry a publishable pose")
        if self.pose is not None and (
            self.pose.parent_frame != self.parent_frame
            or self.pose.child_frame != self.child_frame
        ):
            raise ValueError("Pose frames differ from result frames")

    @property
    def inlier_corner_count(self):
        return sum(len(o.inlier_corners) for o in self.observations)

    def to_dict(self):
        return {"schema_version": 1, "units": "meters", **asdict(self)}

    def to_csv_row(self, frame):
        row = {
            "frame": frame,
            "time_s": f"{self.timestamp_s:.6f}",
            "object_id": self.object_id,
            "status": self.status,
            "marker_ids": ";".join(map(str, self.inlier_marker_ids)),
            "marker_count": len(self.inlier_marker_ids),
            "reason": self.reason,
            "observed_marker_ids": ";".join(
                str(o.marker_id) for o in self.observations
            ),
            "rejected_marker_ids": ";".join(map(str, self.rejected_marker_ids)),
            "inlier_corner_count": self.inlier_corner_count,
            "candidate_count": len(self.candidates),
            "ambiguity_resolved_by": self.ambiguity_resolved_by,
            "parent_frame": self.parent_frame,
            "child_frame": self.child_frame,
        }
        if self.reprojection_rmse_px is not None:
            row["reprojection_rmse_px"] = self.reprojection_rmse_px
        if self.pose is not None:
            row.update(
                zip(
                    ["tx_m", "ty_m", "tz_m", "qx", "qy", "qz", "qw"],
                    self.pose.translation_m + self.pose.quaternion_xyzw,
                )
            )
        return row


@dataclass(frozen=True)
class TrackerConfig:
    min_markers: int = 2
    outlier_threshold_px: float = 3.0
    max_reprojection_rmse_px: float = 3.0
    min_inlier_fraction: float = 0.6
    ambiguity_gap_px: float = 0.05
    prior_max_age_s: float = 0.25
    prior_max_rotation_rad: float = 0.5
    prior_max_translation_m: float = 0.1
    prior_score_margin: float = 0.1

    def __post_init__(self):
        if not isinstance(self.min_markers, int) or self.min_markers < 1:
            raise ValueError("min_markers must be a positive integer")
        positive = [
            self.outlier_threshold_px,
            self.max_reprojection_rmse_px,
            self.prior_max_age_s,
            self.prior_max_rotation_rad,
            self.prior_max_translation_m,
            self.prior_score_margin,
        ]
        if not all(np.isfinite(v) and v > 0 for v in positive):
            raise ValueError("Quality thresholds must be finite and positive")
        if not np.isfinite(self.ambiguity_gap_px) or self.ambiguity_gap_px < 0:
            raise ValueError("ambiguity_gap_px must be finite and nonnegative")
        if (
            not np.isfinite(self.min_inlier_fraction)
            or not 0.5 < self.min_inlier_fraction <= 1
        ):
            raise ValueError(
                "min_inlier_fraction must be greater than .5 and at most 1"
            )


def _pose_distance(first, second):
    angle = (
        Rotation.from_quat(first.quaternion_xyzw).inv()
        * Rotation.from_quat(second.quaternion_xyzw)
    ).magnitude()
    distance = np.linalg.norm(np.array(first.translation_m) - second.translation_m)
    return float(angle), float(distance)


class Tracker:
    """Estimate from images or detected corners; no hidden temporal state.

    Optional previous=PoseResult only selects between ambiguous current-frame
    candidates. It never synthesizes a pose when observations are absent.
    """

    def __init__(
        self,
        model,
        camera_matrix,
        distortion,
        *,
        config=None,
        parent_frame="camera_optical",
        child_frame=None,
        image_size=None,
    ):
        self.config = config or TrackerConfig()
        self.camera_matrix = np.array(camera_matrix, dtype=float, copy=True)
        self.distortion = np.array(distortion, dtype=float, copy=True).ravel()
        if (
            self.camera_matrix.shape != (3, 3)
            or not np.isfinite(self.camera_matrix).all()
            or self.camera_matrix[0, 0] <= 0
            or self.camera_matrix[1, 1] <= 0
            or not np.allclose(self.camera_matrix[2], [0, 0, 1])
            or self.distortion.size not in (0, 4, 5, 8, 12, 14)
            or not np.isfinite(self.distortion).all()
        ):
            raise ValueError("Invalid camera intrinsics/distortion")
        if (
            model.get("units") != "meters"
            or not model.get("object_id")
            or not model.get("markers")
        ):
            raise ValueError("Model needs object_id, units=meters and markers")
        self.object_id = str(model["object_id"])
        self.dictionary = model["dictionary"]
        self.parent_frame = parent_frame
        self.child_frame = child_frame or self.object_id
        if not self.parent_frame or not self.child_frame:
            raise ValueError("Frame names must be nonempty")
        self.markers = {}
        for marker in model["markers"]:
            marker_id = marker["id"]
            points = np.array(marker["corners_m"], dtype=float, copy=True)
            if (
                not isinstance(marker_id, int)
                or marker_id < 0
                or marker_id in self.markers
            ):
                raise ValueError("Model marker IDs must be unique nonnegative integers")
            if points.shape != (4, 3) or not np.isfinite(points).all():
                raise ValueError("Each marker needs four finite 3D corners")
            singular = np.linalg.svd(points - points.mean(axis=0), compute_uv=False)
            if (
                singular[1] <= max(singular[0] * 1e-8, 1e-12)
                or singular[2] > singular[0] * 1e-6
            ):
                raise ValueError("Marker corners must span a nondegenerate plane")
            self.markers[marker_id] = points
        if self.config.min_markers > len(self.markers):
            raise ValueError("min_markers exceeds model marker count")
        all_points = np.concatenate(list(self.markers.values()))
        self.extent_m = max(np.linalg.norm(np.ptp(all_points, axis=0)), 1e-6)
        self.image_size = tuple(image_size) if image_size is not None else None
        self._detector = None

    def process(self, frame, timestamp_s, *, previous=None):
        if (
            self.image_size is not None
            and (frame.shape[1], frame.shape[0]) != self.image_size
        ):
            raise ValueError(
                "Frame size differs from calibration; recalibrate at this resolution"
            )
        if self._detector is None:
            self._detector = UnifiedArucoDetector(self.dictionary)
        corners, ids, _ = self._detector.detect(frame)
        return self.estimate(corners, ids, timestamp_s, previous=previous)

    def _hypotheses(self, objects, images):
        """IPPE in a local plane basis also supports tilted/offset marker planes."""
        center = objects.mean(axis=0)
        _, singular, vt = np.linalg.svd(objects - center)
        if singular[1] < max(singular[0] * 1e-8, 1e-12):
            return []
        planar = singular[2] <= max(singular[0] * 1e-6, 1e-12)
        try:
            if planar:
                # SVD's in-plane axes are arbitrary for symmetric layouts. Use
                # fixed projected axes to avoid IPPE NaNs at exact frontal views.
                normal = vt[2].copy()
                if normal[np.argmax(np.abs(normal))] < 0:
                    normal *= -1
                axis = (
                    np.array([1.0, 0.0, 0.0])
                    if abs(normal[0]) < 0.9
                    else np.array([0.0, 1.0, 0.0])
                )
                x_axis = axis - np.dot(axis, normal) * normal
                x_axis /= np.linalg.norm(x_axis)
                basis = np.column_stack((x_axis, np.cross(normal, x_axis), normal))
                points = (objects - center) @ basis
                points[:, 2] = 0
                solved = cv2.solvePnPGeneric(
                    np.ascontiguousarray(points),
                    np.ascontiguousarray(images),
                    self.camera_matrix,
                    self.distortion,
                    flags=cv2.SOLVEPNP_IPPE,
                )
                values = []
                for rvec, tvec in zip(solved[1], solved[2]):
                    rotation = cv2.Rodrigues(rvec)[0] @ basis.T
                    values.append(
                        (
                            cv2.Rodrigues(rotation)[0],
                            tvec - rotation @ center.reshape(3, 1),
                        )
                    )
                return values
            solved = cv2.solvePnPGeneric(
                np.ascontiguousarray(objects),
                np.ascontiguousarray(images),
                self.camera_matrix,
                self.distortion,
                flags=cv2.SOLVEPNP_SQPNP,
            )
            return list(zip(solved[1], solved[2]))
        except cv2.error:
            return []

    def _residuals(self, objects, images, rvec, tvec):
        if not np.isfinite(rvec).all() or not np.isfinite(tvec).all():
            return np.full(len(objects), np.inf)
        projected = cv2.projectPoints(
            objects, rvec, tvec, self.camera_matrix, self.distortion
        )[0].reshape(-1, 2)
        depths = (cv2.Rodrigues(rvec)[0] @ objects.T).T[:, 2] + np.asarray(
            tvec
        ).ravel()[2]
        errors = np.linalg.norm(projected - images, axis=1)
        errors[(depths <= 0) | ~np.isfinite(errors)] = np.inf
        return errors

    def _mask(self, errors):
        mask = errors <= self.config.outlier_threshold_px
        # A marker with two or more bad corners provides no accepted support.
        groups = mask.reshape(-1, 4)
        return (groups & (groups.sum(axis=1) >= 3)[:, None]).ravel()

    def _enough(self, mask):
        return (
            np.count_nonzero(mask.reshape(-1, 4).any(axis=1)) >= self.config.min_markers
            and np.mean(mask) >= self.config.min_inlier_fraction
        )

    def estimate(self, corners, ids, timestamp_s, *, previous=None):
        if not np.isfinite(timestamp_s):
            raise ValueError("timestamp_s must be finite")
        corners = list(corners) if corners is not None else []
        ids = np.asarray(ids).ravel() if ids is not None else np.array([], dtype=int)
        if (
            len(corners) != len(ids)
            or not np.isfinite(ids).all()
            or np.any(ids != np.floor(ids))
        ):
            raise ValueError(
                "IDs must be finite integers matching the number of corner observations"
            )
        ids = [int(i) for i in ids]
        counts = Counter(ids)
        observations, usable_ids, observation_indices = [], [], []
        object_points, image_points = [], []
        for marker_id, points in zip(ids, corners):
            points = np.asarray(points, dtype=float)
            valid = points.shape in ((1, 4, 2), (4, 2)) and np.isfinite(points).all()
            reason = (
                "unknown_id"
                if marker_id not in self.markers
                else (
                    "duplicate_id"
                    if counts[marker_id] > 1
                    else "invalid_corners" if not valid else ""
                )
            )
            coordinates = (
                tuple(tuple(map(float, p)) for p in points.reshape(4, 2))
                if valid
                else ()
            )
            observations.append(
                MarkerObservation(marker_id, coordinates, reason=reason)
            )
            if not reason:
                usable_ids.append(marker_id)
                observation_indices.append(len(observations) - 1)
                object_points.extend(self.markers[marker_id])
                image_points.extend(points.reshape(4, 2))

        def result(
            status, reason, mask=None, candidates=(), chosen=None, resolved_by=""
        ):
            updated = list(observations)
            accepted = []
            if mask is not None:
                for group, observation_index in enumerate(observation_indices):
                    inliers = tuple(
                        int(i) for i in np.flatnonzero(mask[group * 4 : group * 4 + 4])
                    )
                    old = observations[observation_index]
                    updated[observation_index] = MarkerObservation(
                        old.marker_id,
                        old.corners_px,
                        inliers,
                        "" if len(inliers) == 4 else "outlier_corners",
                    )
                    if inliers:
                        accepted.append(old.marker_id)
            rejected = tuple(
                sorted(
                    {o.marker_id for o in observations if o.marker_id in self.markers}
                    - set(accepted)
                )
            )
            error = (
                chosen.reprojection_rmse_px
                if chosen is not None
                else (candidates[0].reprojection_rmse_px if candidates else None)
            )
            return PoseResult(
                float(timestamp_s),
                self.object_id,
                self.parent_frame,
                self.child_frame,
                status,
                reason,
                chosen.pose if chosen is not None else None,
                tuple(updated),
                tuple(accepted),
                rejected,
                error,
                tuple(candidates),
                resolved_by,
            )

        if len(usable_ids) < self.config.min_markers:
            invalid = any(
                o.reason in ("duplicate_id", "invalid_corners") for o in observations
            )
            return result(
                "rejected" if invalid else "lost",
                "invalid_observations" if invalid else "insufficient_markers",
            )
        objects = np.ascontiguousarray(object_points, dtype=np.float64)
        images = np.ascontiguousarray(image_points, dtype=np.float64)
        hypotheses = self._hypotheses(objects, images)
        # Whole-marker hypotheses recover even when an entire detected marker is misplaced.
        for start in range(0, len(objects), 4):
            hypotheses.extend(
                self._hypotheses(objects[start : start + 4], images[start : start + 4])
            )
        # Corner-level RANSAC also handles cases with no completely clean marker.
        try:
            ok, rvec, tvec, _ = cv2.solvePnPRansac(
                objects,
                images,
                self.camera_matrix,
                self.distortion,
                iterationsCount=200,
                reprojectionError=self.config.outlier_threshold_px,
                confidence=0.999,
                flags=cv2.SOLVEPNP_EPNP,
            )
            if ok:
                hypotheses.append((rvec, tvec))
        except cv2.error:
            pass
        scored = []
        for rvec, tvec in hypotheses:
            errors = self._residuals(objects, images, rvec, tvec)
            mask = self._mask(errors)
            if self._enough(mask):
                clipped_cost = float(
                    np.minimum(errors, self.config.outlier_threshold_px).sum()
                )
                scored.append((-int(mask.sum()), clipped_cost, mask))
        if not scored:
            return result("rejected", "no_majority_consensus")
        mask = min(scored, key=lambda value: value[:2])[2]
        # Refit only the consensus. Reclassify conservatively until stable; removed
        # corners do not re-enter and contaminate subsequent refinement.
        for _ in range(4):
            fits = self._hypotheses(objects[mask], images[mask])
            candidates = []
            for rvec, tvec in fits:
                errors = self._residuals(objects[mask], images[mask], rvec, tvec)
                error = float(np.sqrt(np.mean(errors**2)))
                if np.isfinite(error):
                    pose = Pose.from_rvec(
                        rvec, tvec, self.parent_frame, self.child_frame
                    )
                    candidates.append(PoseCandidate(pose, error))
            candidates.sort(key=lambda candidate: candidate.reprojection_rmse_px)
            if not candidates:
                return result("rejected", "no_positive_depth_solution")
            best = candidates[0]
            new_mask = mask & self._mask(
                self._residuals(objects, images, best.pose.rvec, best.pose.tvec)
            )
            if not self._enough(new_mask):
                return result("rejected", "insufficient_inliers")
            if np.array_equal(mask, new_mask):
                break
            mask = new_mask
        else:
            return result("rejected", "unstable_consensus")
        if best.reprojection_rmse_px > self.config.max_reprojection_rmse_px:
            return result("rejected", "high_reprojection_error", mask, candidates)
        close = [best]
        for candidate in candidates[1:]:
            angle, distance = _pose_distance(best.pose, candidate.pose)
            if (
                candidate.reprojection_rmse_px <= self.config.max_reprojection_rmse_px
                and candidate.reprojection_rmse_px - best.reprojection_rmse_px
                <= self.config.ambiguity_gap_px
                and (angle > 1e-3 or distance > 1e-6)
            ):
                close.append(candidate)
        resolved_by = "reprojection"
        if len(close) > 1:
            chosen = self._choose_with_prior(close, previous, timestamp_s)
            if chosen is None:
                return result("ambiguous", "planar_pose_ambiguity", mask, candidates)
            best = chosen
            resolved_by = "recent_measurement"
        # Refine only the selected branch, retaining both pre-refinement hypotheses
        # for ambiguity diagnostics. Never collapse both branches before comparing.
        try:
            rvec, tvec = cv2.solvePnPRefineLM(
                objects[mask],
                images[mask],
                self.camera_matrix,
                self.distortion,
                best.pose.rvec,
                best.pose.tvec,
            )
            refined_pose = Pose.from_rvec(
                rvec, tvec, self.parent_frame, self.child_frame
            )
        except (cv2.error, ValueError):
            return result("rejected", "refinement_numerical_failure", mask, candidates)
        if len(close) > 1:

            def branch_distance(candidate):
                angle, distance = _pose_distance(refined_pose, candidate.pose)
                return angle + distance / self.extent_m

            # An unconstrained optimizer may cross to the other local minimum.
            # Keep the selected current-frame solution rather than silently flip.
            if any(
                branch_distance(candidate) + 1e-9 < branch_distance(best)
                for candidate in close
                if candidate is not best
            ):
                rvec, tvec = best.pose.rvec, best.pose.tvec
        errors = self._residuals(objects, images, rvec, tvec)
        if not np.all(errors[mask] <= self.config.outlier_threshold_px):
            return result(
                "rejected", "refinement_failed_quality_gate", mask, candidates
            )
        error = float(np.sqrt(np.mean(errors[mask] ** 2)))
        if error > best.reprojection_rmse_px + 1e-9:
            rvec, tvec, error = (
                best.pose.rvec,
                best.pose.tvec,
                best.reprojection_rmse_px,
            )
        if error > self.config.max_reprojection_rmse_px:
            return result("rejected", "high_reprojection_error", mask, candidates)
        refined = PoseCandidate(
            Pose.from_rvec(rvec, tvec, self.parent_frame, self.child_frame), error
        )
        return result("measured", "accepted", mask, candidates, refined, resolved_by)

    def _choose_with_prior(self, candidates, previous, timestamp_s):
        c = self.config
        if (
            previous is None
            or previous.status != "measured"
            or previous.pose is None
            or previous.object_id != self.object_id
            or previous.parent_frame != self.parent_frame
            or previous.child_frame != self.child_frame
            or not 0 < timestamp_s - previous.timestamp_s <= c.prior_max_age_s
        ):
            return None
        values = []
        for candidate in candidates:
            angle, distance = _pose_distance(previous.pose, candidate.pose)
            values.append(
                (angle + distance / self.extent_m, angle, distance, candidate)
            )
        values.sort(key=lambda value: value[0])
        score, angle, distance, candidate = values[0]
        if (
            angle > c.prior_max_rotation_rad
            or distance > c.prior_max_translation_m
            or values[1][0] - score < c.prior_score_margin
        ):
            return None
        return candidate


def model_from_extrinsics(
    extrinsics, marker_size, *, object_id="rigid_object", dictionary="DICT_5X5_100"
):
    """Adapt legacy [tx,ty,tz,rx,ry,rz] marker frames, preserving their y-up corner order."""
    if not np.isfinite(marker_size) or marker_size <= 0:
        raise ValueError("marker_size must be finite and positive")
    local = np.array([[-1, 1, 0], [1, 1, 0], [1, -1, 0], [-1, -1, 0]]) * marker_size / 2
    markers = []
    for marker_id, extrinsic in extrinsics.items():
        value = np.asarray(extrinsic, dtype=float)
        if value.shape != (6,) or not np.isfinite(value).all():
            raise ValueError(
                "Extrinsics must contain six finite translation/rotation values"
            )
        points = (cv2.Rodrigues(value[3:])[0] @ local.T).T + value[:3]
        markers.append({"id": int(marker_id), "corners_m": points.tolist()})
    return {
        "object_id": object_id,
        "dictionary": dictionary,
        "units": "meters",
        "markers": markers,
    }


def draw_pose_result(frame, result, camera_matrix, distortion, axis_length=0.04):
    """Draw current observations and only an accepted pose; modify frame in place."""
    for observation in result.observations:
        if not observation.corners_px:
            continue
        points = np.array(observation.corners_px).round().astype(np.int32)
        color = (0, 180, 0) if observation.inlier_corners else (0, 100, 255)
        cv2.polylines(frame, [points], True, color, 1)
        cv2.putText(
            frame,
            str(observation.marker_id),
            tuple(points[0]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            color,
            1,
        )
    if result.pose is not None:
        cv2.drawFrameAxes(
            frame,
            camera_matrix,
            distortion,
            result.pose.rvec,
            result.pose.tvec,
            axis_length,
        )
    cv2.putText(
        frame,
        f"{result.status} | inlier markers: {len(result.inlier_marker_ids)}",
        (12, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 100, 255),
        2,
    )
    return frame
