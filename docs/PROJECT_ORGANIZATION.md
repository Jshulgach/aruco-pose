> Historical / experimental documentation. Some APIs and commands below are
> outdated. Start with the repository README and docs/POSE_API.md for supported
> commands, tested behavior and limitations. Performance figures below are unverified.

# Project Organization

Clean, logical structure for the ArUco Pose Estimation package.

## 📁 Directory Structure

```
ArUco_Pose_Estimation/
├── aruco_pose/                          # Source code (all utilities here!)
│   ├── core/                     # Core detection functionality
│   │   └── detector.py          # UnifiedArucoDetector
│   ├── models/                   # 3D models (dodecahedron, etc.)
│   ├── tracking/                 # Tracking algorithms
│   │   ├── optical_flow.py      # Lucas-Kanade tracking
│   │   └── dense_refinement.py  # Dense pose refinement
│   └── utils/                    # Utility functions
│       ├── config.py            # Configuration management
│       ├── io.py                # Video/data I/O
│       ├── logger.py            # Logging setup
│       ├── marker_generator.py  # Marker generation
│       ├── performance.py       # Performance monitoring
│       └── visualization.py     # Visualization tools
│
├── examples/                     # Example scripts organized by use case
│   ├── 01_basic/                # Getting started
│   ├── 02_single_marker/        # Single marker pose
│   ├── 03_multi_marker/         # Multi-marker fusion
│   ├── 04_custom_models/        # Dodecahedron tracking
│   └── 05_advanced/             # Advanced techniques
│
├── tools/                        # Command-line tools
│   ├── cli.py                   # Main CLI interface
│   └── visualize_aruco_extrinsics.py  # 3D visualization
│
├── tests/                        # Unit tests
│   ├── test_installation.py     # Installation verification
│   ├── test_dodecahedron_model.py  # Model tests
│   └── test_visualization.py    # Visualization tests
│
└── docs/                         # Documentation
    ├── README_v2.md             # Main documentation
    ├── QUICK_START.md           # Quick start guide
    ├── MIGRATION_GUIDE.md       # Migration guide
    └── ...
```

## 🎯 Design Principles

### 1. **aruco_pose/ contains ALL utilities**
No more scattered utility folders. Everything is in `aruco_pose/`:
- Core functionality → `aruco_pose/core/`
- Tracking algorithms → `aruco_pose/tracking/`
- Utility functions → `aruco_pose/utils/`
- 3D models → `aruco_pose/models/`

### 2. **examples/ for learning**
Organized by complexity (01→05) and use case:
- Each directory has comprehensive README
- Copy of relevant code for standalone execution
- Clear progression from basic to advanced

### 3. **tools/ for CLI only**
Command-line interface and standalone tools:
- `cli.py` - Main interface (calibrate, track, generate, analyze)
- `visualize_aruco_extrinsics.py` - 3D scene visualization

### 4. **tests/ for testing**
Standard Python testing structure:
- Unit tests for core functionality
- Installation verification
- All tests in one place

## ✅ What Changed

### Removed Directories
- ❌ `utilities/` - Moved to `aruco_pose/tracking/`
- ❌ `scripts/` - Consolidated into `tools/` and `aruco_pose/utils/`

### Consolidated Files
- `utilities/optical_flow.py` → `aruco_pose/tracking/optical_flow.py`
- `utilities/dense_refinement.py` → `aruco_pose/tracking/dense_refinement.py`
- `scripts/generate_markers.py` → `aruco_pose/utils/marker_generator.py`
- `scripts/aruco_cli.py` → (removed, duplicate of `tools/cli.py`)

### Updated Imports
All examples now use:
```python
from aruco_pose.tracking import OpticalFlowTracker, DenseRefiner
from aruco_pose.utils.marker_generator import generate_aruco_marker
from aruco_pose.utils import ProjectConfig, setup_logger
```

## 📦 Package Installation

Install in development mode to use `aruco_pose/` modules anywhere:

```bash
pip install -e .
```

Now you can import from anywhere:
```python
from aruco_pose.core import UnifiedArucoDetector
from aruco_pose.tracking import OpticalFlowTracker
from aruco_pose.utils import ProjectConfig
```

## 🚀 Usage Patterns

### Using Core Utilities
```python
from aruco_pose.core import UnifiedArucoDetector
from aruco_pose.utils import ProjectConfig, setup_logger

config = ProjectConfig.from_yaml("config.yaml")
detector = UnifiedArucoDetector(config.aruco.dictionary)
logger = setup_logger("my_app")
```

### Using Tracking Utilities
```python
from aruco_pose.tracking import OpticalFlowTracker, DenseRefiner

tracker = OpticalFlowTracker()
refiner = DenseRefiner()
```

### Using CLI Tools
```bash
# Generate markers
python -m aruco_pose generate 0 1 2 --size 200

# Calibrate camera
python -m aruco_pose calibrate --rows 9 --cols 6

# Track markers
python -m aruco_pose track --config config.yaml
```

### Running Examples
```bash
# Basic detection
cd examples/01_basic
python basic_detection.py

# Single marker pose
cd examples/02_single_marker
python simple_pose_estimation.py

# Advanced tracking
cd examples/05_advanced
python optical_flow.py
```

## 📖 Finding What You Need

| I want to... | Look in... |
|--------------|------------|
| Detect ArUco markers | `aruco_pose/core/detector.py` |
| Configure the system | `aruco_pose/utils/config.py` |
| Log messages | `aruco_pose/utils/logger.py` |
| Visualize results | `aruco_pose/utils/visualization.py` |
| Track with optical flow | `aruco_pose/tracking/optical_flow.py` |
| Refine poses | `aruco_pose/tracking/dense_refinement.py` |
| Generate markers | `aruco_pose/utils/marker_generator.py` |
| Use CLI interface | `tools/cli.py` |
| Learn basics | `examples/01_basic/` |
| Learn pose estimation | `examples/02_single_marker/` |
| Track custom models | `examples/04_custom_models/` |
| Run tests | `tests/` |

## 🔧 Development Workflow

### Adding New Features

1. **Utility function** → Add to appropriate `aruco_pose/` module
   - Detection/dictionary related → `aruco_pose/core/`
   - Tracking algorithm → `aruco_pose/tracking/`
   - Helper function → `aruco_pose/utils/`
   - 3D model → `aruco_pose/models/`

2. **CLI command** → Add to `tools/cli.py`

3. **Example** → Add to appropriate `examples/XX_category/`

4. **Test** → Add to `tests/`

### No More Confusion!

Before:
- "Should this go in `utilities/` or `aruco_pose/utils/`?"
- "Is this a `script/` or `tools/` or `examples/`?"
- "Where do I find the optical flow code?"

After:
- All source code → `aruco_pose/`
- All examples → `examples/`
- All CLI tools → `tools/`
- All tests → `tests/`

## 🎓 Benefits

1. **Clear separation of concerns**
   - Source code in `aruco_pose/`
   - Examples in `examples/`
   - Tools in `tools/`
   - Tests in `tests/`

2. **Easy to find things**
   - Want utility? Check `aruco_pose/utils/`
   - Want tracking algorithm? Check `aruco_pose/tracking/`
   - Want example? Check `examples/`

3. **Standard Python structure**
   - Follows Python packaging conventions
   - Works with `pip install -e .`
   - Clean imports

4. **Maintainable**
   - One place for each type of code
   - No duplication
   - Easy to extend

## 📝 Migration Notes

If you have old code importing from removed directories:

### Old imports:
```python
from utilities.optical_flow import OpticalFlowTracker
from scripts.generate_markers import generate_aruco_marker
```

### New imports:
```python
from aruco_pose.tracking import OpticalFlowTracker
from aruco_pose.utils.marker_generator import generate_aruco_marker
```

All examples have been updated to use the new structure!
