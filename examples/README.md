> Historical / experimental documentation. Some APIs and commands below are
> outdated. Start with the repository README and docs/POSE_API.md for supported
> commands, tested behavior and limitations. Performance figures below are unverified.

# ArUco Pose Estimation Examples

Current shared-API examples: [Python pose API](pose_api_demo.py),
[printable dodecahedron kit](../docs/DODECAHEDRON_KIT.md), and the optional
[ROS 2 Jazzy pose + TF replay](ros2/README.md). The older sections below remain
historical/experimental.

Organized examples demonstrating ArUco marker detection, pose estimation, and advanced tracking techniques.

## 📁 Directory Structure

```
examples/
├── 01_basic/              # Getting started
├── 02_single_marker/      # Single marker pose estimation
├── 03_multi_marker/       # Multi-marker fusion
├── 04_custom_models/      # Dodecahedron and custom shapes
├── 05_advanced/           # Advanced tracking techniques
└── README.md              # This file
```

---

## 🎯 Learning Path

### Level 1: Basics (01_basic/)
**Start here if you're new to ArUco markers**

1. **Camera calibration** - Get intrinsic parameters
2. **Generate markers** - Create ArUco markers for printing
3. **Basic detection** - Detect markers in images/video
4. **Configuration** - Learn the new config system

**Time required:** 30 minutes  
**Prerequisites:** Webcam, printer (or display)

👉 [Go to basics →](01_basic/)

---

### Level 2: Single Marker Pose (02_single_marker/)
**Learn 6DOF pose estimation for individual markers**

1. **Simple pose estimation** - Get position & orientation
2. **Marker tracking** - Real-time pose tracking
3. **Pose estimation demo** - Full v2.0 features

**Time required:** 1 hour  
**Prerequisites:** Completed Level 1, printed marker

👉 [Go to single marker →](02_single_marker/)

---

### Level 3: Multi-Marker Fusion (03_multi_marker/)
**Improve accuracy by fusing multiple marker poses**

1. **Multi-marker fusion** - Combine multiple markers
2. **Marker groups** - Define marker configurations

**Time required:** 1-2 hours  
**Prerequisites:** Completed Level 2, multiple markers

👉 [Go to multi-marker →](03_multi_marker/)

---

### Level 4: Custom 3D Models (04_custom_models/)
**Track complex 3D objects with markers on multiple faces**

1. **Dodecahedron model** - 12-face polyhedron geometry
2. **Dodecahedron pose** - 360° tracking
3. **Model generation** - Create custom 3D models
4. **Tracking demo** - Complete dodecahedron system

**Time required:** 2-4 hours  
**Prerequisites:** Completed Level 3, dodecahedron (3D printed or paper craft)

👉 [Go to custom models →](04_custom_models/)

---

### Level 5: Advanced Techniques (05_advanced/)
**Master advanced computer vision algorithms**

1. **Optical flow** - Inter-frame tracking
2. **Dense refinement** - Sub-pixel accuracy
3. **Kalman filtering** - Smooth pose estimation
4. **Pose refinement** - Non-linear optimization

**Time required:** 3-5 hours  
**Prerequisites:** Completed Level 4, strong computer vision background

👉 [Go to advanced →](05_advanced/)

---

## 🚀 Quick Start by Use Case

### "I just want to detect markers"
```bash
cd 01_basic
python basic_detection.py
```

### "I need pose estimation"
```bash
# First calibrate
cd 01_basic
python camera_calibration.py

# Then track pose
cd ../02_single_marker
python simple_pose_estimation.py
```

### "I need robust tracking"
```bash
# Use multi-marker system
cd 03_multi_marker
python multi_marker_fusion.py --config marker_group.json
```

### "I need 360° tracking"
```bash
# Use dodecahedron
cd 04_custom_models
python dodecahedron_tracking_demo.py
```

### "I need highest accuracy"
```bash
# Combine all advanced techniques
cd 05_advanced
python advanced_tracking_demo.py --all
```

---

## 📊 Feature Comparison

| Feature | Level 1 | Level 2 | Level 3 | Level 4 | Level 5 |
|---------|---------|---------|---------|---------|---------|
| Detection | ✅ | ✅ | ✅ | ✅ | ✅ |
| Pose estimation | ❌ | ✅ | ✅ | ✅ | ✅ |
| Multi-marker | ❌ | ❌ | ✅ | ✅ | ✅ |
| 360° tracking | ❌ | ❌ | ❌ | ✅ | ✅ |
| Occlusion handling | ❌ | ❌ | ✅ | ✅ | ✅ |
| Sub-pixel accuracy | ❌ | ❌ | ❌ | ❌ | ✅ |
| Temporal smoothing | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## 🛠️ Common Tasks

### Calibrate Camera
```bash
cd 01_basic
python camera_calibration.py
```
Output: `calibration_matrix.npy`, `distortion_coefficients.npy`

### Generate Markers
```bash
cd 01_basic
python generate_markers.py --id 0 --size 200 --dict DICT_4X4_50
```
Output: `marker_0.png`

### Track Single Marker
```bash
cd 02_single_marker
python marker_tracking.py
```

### Track Multiple Markers
```bash
cd 03_multi_marker
python multi_marker_fusion.py --config marker_group.json
```

### Track Dodecahedron
```bash
cd 04_custom_models
python dodecahedron_tracking_demo.py --config dodecahedron_with_markers.json
```

---

## 🎓 Key Concepts

### ArUco Markers
Binary square markers with unique IDs for robust detection.

**Dictionaries:**
- `DICT_4X4_50`: 4×4 bits, 50 markers (most common)
- `DICT_5X5_100`: 5×5 bits, 100 markers
- `DICT_6X6_250`: 6×6 bits, 250 markers (higher ID range)

### 6DOF Pose
Six degrees of freedom: x, y, z (position) + roll, pitch, yaw (orientation)

### Camera Calibration
Process to determine:
- **Camera matrix (K):** Focal length and principal point
- **Distortion coefficients:** Lens distortion parameters

### Multi-Marker Fusion
Combining pose estimates from multiple markers for improved accuracy and robustness.

### Custom 3D Models
Placing markers on multiple faces of 3D objects for 360° tracking.

---

## 📝 Configuration

### YAML Format (v2.0)
```yaml
camera:
  width: 640
  height: 480
  fps: 30
  
aruco:
  dictionary: DICT_4X4_50
  marker_size: 0.05
  
tracking:
  enable_refinement: true
  enable_recording: false
  
visualization:
  show_axes: true
  show_ids: true
  show_fps: true
```

### Legacy Format
Older `config.yaml` still supported via backward compatibility layer.

---

## 🔧 Troubleshooting

### Markers not detected
- Check lighting (avoid glare/shadows)
- Verify correct ArUco dictionary
- Ensure marker is flat and in focus
- Print at higher resolution

### Pose estimation unstable
- Calibrate camera properly
- Verify marker size parameter
- Improve lighting conditions
- Use multiple markers (Level 3)

### Low FPS
- Reduce image resolution
- Use smaller ArUco dictionary
- Limit detection to expected marker IDs
- Skip detection on some frames (use optical flow)

### High reprojection error
- Recalibrate camera
- Check marker size accuracy
- Ensure markers are flat
- Verify coordinate system

---

## 📚 Documentation

- [Main README](../README_v2.md) - Package overview
- [Quick Start Guide](../QUICK_START.md) - Get up and running quickly
- [Migration Guide](../MIGRATION_GUIDE.md) - Upgrade from old code
- [Implementation Summary](../IMPLEMENTATION_SUMMARY.md) - Technical details
- [Files Reference](../FILES.md) - Complete file listing

---

## 💡 Tips for Success

1. **Start simple:** Master basics before moving to advanced
2. **Good calibration:** Spend time on accurate camera calibration
3. **Lighting matters:** Consistent, diffuse lighting gives best results
4. **Marker size:** Larger markers = easier detection, smaller = more per area
5. **Print quality:** 300+ DPI for best marker detection
6. **Flat mounting:** Ensure markers are perfectly flat
7. **Test incrementally:** Verify each step before moving forward

---

## 🤝 Contributing

Found a bug or have an improvement? Check the main README for contribution guidelines.

---

## 📖 References

### ArUco Documentation
- [OpenCV ArUco Documentation](https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html)
- [ArUco Marker Detection Tutorial](https://docs.opencv.org/4.x/d9/d6a/group__aruco.html)

### Computer Vision
- Calibration: Zhang's method
- Pose estimation: solvePnP algorithms
- Optical flow: Lucas-Kanade
- Filtering: Kalman filter theory

### Related Projects
- [ArUco Markers Pose Estimation Generation](https://github.com/GSNCodes/ArUCo-Markers-Pose-Estimation-Generation-Python)
- [OpenCV ArUco Module](https://github.com/opencv/opencv_contrib/tree/master/modules/aruco)

---

## ❓ Getting Help

1. **Read the README** in each example directory
2. **Check troubleshooting** sections
3. **Review existing issues** on GitHub
4. **Open new issue** with details: OS, OpenCV version, error message, steps to reproduce

---

## 📄 License

See main repository [LICENSE](../LICENSE) file.

---

**Happy Tracking! 🎯**
