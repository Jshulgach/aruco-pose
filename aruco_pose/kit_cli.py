"""Commands for the supported print -> calibrate -> track -> CSV workflow."""

from pathlib import Path
import click
import cv2

from aruco_pose import starter as workflow


def fail_cleanly(function, **kwargs):
    try:
        return function(**kwargs)
    except (ValueError, OSError, KeyError, cv2.error) as error:
        raise click.ClickException(str(error)) from error


@click.group()
def kit():
    """Print, calibrate and track a rigid four-marker board. Headless by default."""


@kit.command("print")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default="output/print",
    show_default=True,
)
def print_targets(output):
    """Write dimensioned A4 SVG targets and board.json. Print at actual size."""
    fail_cleanly(workflow.print_kit, output=output)
    click.echo(
        f"Wrote targets and model to {output}. Print SVGs at 100% and verify dimensions."
    )


@kit.command()
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default="output/sample",
    show_default=True,
)
def sample(output):
    """Generate synthetic calibration/tracking videos and known reference poses."""
    from aruco_pose.starter_sample import create_sample

    fail_cleanly(create_sample, output=output)
    click.echo(f"Wrote SYNTHETIC sample videos and targets to {output}")


@kit.command()
@click.option(
    "--source", required=True, help="Camera index (e.g. 0) or checkerboard video path"
)
@click.option(
    "--output", required=True, type=click.Path(path_type=Path), help="Calibration JSON"
)
@click.option(
    "--cols",
    type=click.IntRange(min=3),
    default=9,
    show_default=True,
    help="Inner corner columns",
)
@click.option(
    "--rows",
    type=click.IntRange(min=3),
    default=6,
    show_default=True,
    help="Inner corner rows",
)
@click.option(
    "--square-size",
    type=click.FloatRange(min=0, min_open=True),
    default=0.02,
    show_default=True,
    help="Square side in meters",
)
@click.option(
    "--stride",
    type=click.IntRange(min=1),
    default=10,
    show_default=True,
    help="Sample every N video frames",
)
@click.option("--max-views", type=click.IntRange(min=8), default=40, show_default=True)
@click.option(
    "--preview", is_flag=True, help="Show capture window; required for a live camera"
)
def calibrate(**kwargs):
    """Estimate camera intrinsics from at least eight diverse board observations."""
    result = fail_cleanly(workflow.calibrate, **kwargs)
    click.echo(
        f"Saved calibration: {result['views']} views, RMS {result['rms_px']:.3f} px"
    )
    if result["rms_px"] > 1.0:
        click.echo(
            "Warning: RMS exceeds 1 px; inspect calibration and capture better views.",
            err=True,
        )


@kit.command()
@click.option(
    "--source", required=True, help="Camera index (e.g. 0) or tracking video path"
)
@click.option(
    "--model", "model_path", required=True, type=click.Path(exists=True, path_type=Path)
)
@click.option(
    "--calibration",
    "calibration_path",
    required=True,
    type=click.Path(exists=True, path_type=Path),
)
@click.option("--csv", "csv_path", required=True, type=click.Path(path_type=Path))
@click.option("--preview", is_flag=True, help="Show live display (Q to stop)")
@click.option(
    "--output-video", type=click.Path(path_type=Path), help="Annotated MP4 or AVI"
)
@click.option("--min-markers", type=click.IntRange(min=1), default=2, show_default=True)
@click.option(
    "--max-error",
    type=click.FloatRange(min=0, min_open=True),
    default=3.0,
    show_default=True,
    help="Maximum reprojection RMSE in pixels",
)
@click.option(
    "--outlier-threshold",
    type=click.FloatRange(min=0, min_open=True),
    default=3.0,
    show_default=True,
    help="Maximum accepted corner residual in pixels",
)
@click.option(
    "--ambiguity-gap",
    type=click.FloatRange(min=0),
    default=0.05,
    show_default=True,
    help="Planar branches this close in RMSE need a recent compatible measurement",
)
def track(**kwargs):
    """Write one CSV row per frame, including blank poses when lost/rejected."""
    result = fail_cleanly(workflow.track, **kwargs)
    click.echo(
        f"{result['frames']} frames: {result['measured']} measured, {result['lost']} lost, {result['rejected']} rejected, {result['ambiguous']} ambiguous"
    )
    click.echo(f"CSV: {result['csv']} (plus .summary.json)")
