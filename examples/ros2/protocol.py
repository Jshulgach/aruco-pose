"""ROS-free status/frame contract for the optional ROS 2 example."""

import re


def validate_frames(parent, child):
    for frame in (parent, child):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(/[A-Za-z_][A-Za-z0-9_]*)*", frame):
            raise ValueError(
                "Frame IDs need nonempty slash-separated names, without a leading slash"
            )
    if parent == child:
        raise ValueError("Camera and target frames must differ")


def status_values(
    result,
    *,
    parent,
    child,
    frame_index,
    source_time_s,
    source_state="active",
    reason="",
):
    """All numbers are measurements/diagnostics, never an invented confidence."""
    validate_frames(parent, child)
    if result is not None and (
        result.parent_frame != parent or result.child_frame != child
    ):
        raise ValueError("Result frames do not match the publisher frames")
    return {
        "tracking_status": result.status if result else "lost",
        "measurement_valid": str(
            result is not None and result.pose is not None
        ).lower(),
        "source_state": source_state,
        "reason": result.reason if result else reason,
        "parent_frame": parent,
        "child_frame": child,
        "object_id": result.object_id if result else "",
        "frame_index": str(frame_index),
        "source_time_s": (
            "unavailable" if source_time_s is None else f"{source_time_s:.9f}"
        ),
        "inlier_marker_ids": (
            ";".join(map(str, result.inlier_marker_ids)) if result else ""
        ),
        "observed_marker_ids": (
            ";".join(str(o.marker_id) for o in result.observations) if result else ""
        ),
        "rejected_marker_ids": (
            ";".join(map(str, result.rejected_marker_ids)) if result else ""
        ),
        "reprojection_rmse_px": (
            str(result.reprojection_rmse_px)
            if result and result.reprojection_rmse_px is not None
            else "unavailable"
        ),
        "candidate_count": str(len(result.candidates)) if result else "0",
        "ambiguity_resolved_by": result.ambiguity_resolved_by if result else "",
    }
