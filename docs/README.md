> Historical / experimental documentation. Some APIs and commands below are
> outdated. Start with the repository README and docs/POSE_API.md for supported
> commands, tested behavior and limitations. Performance figures below are unverified.

# Documentation

Comprehensive documentation for the ArUco Pose Estimation Toolkit.

## 📚 Documentation Index

### Getting Started
- **[Quick Start Guide](QUICK_START.md)** - Get up and running in 5 minutes
  - Installation
  - First example
  - Common workflows

### Migration & Updates
- **[Migration Guide](MIGRATION_GUIDE.md)** - Upgrade from legacy code to v2.0
  - Breaking changes
  - Code migration examples
  - Backward compatibility notes

### Technical Documentation
- **[Implementation Summary](IMPLEMENTATION_SUMMARY.md)** - Technical deep dive
  - Architecture overview
  - Design decisions
  - API reference

- **[Project Organization](PROJECT_ORGANIZATION.md)** - Understanding the codebase
  - Directory structure
  - Module purposes
  - Best practices

- **[Files Reference](FILES.md)** - Complete file listing
  - All files explained
  - Dependencies
  - Purpose of each module

### Development
- **[Checklist](CHECKLIST.md)** - Development and deployment checklist
  - Pre-release checks
  - Testing requirements
  - Documentation updates

## 🎯 Quick Links

### By Use Case

**"I'm new to ArUco markers"**
→ Start with [Quick Start Guide](QUICK_START.md)

**"I have old code to upgrade"**
→ Read [Migration Guide](MIGRATION_GUIDE.md)

**"I want to understand the architecture"**
→ Check [Implementation Summary](IMPLEMENTATION_SUMMARY.md)

**"I need to find a specific file"**
→ Use [Files Reference](FILES.md)

**"I want to contribute"**
→ Review [Project Organization](PROJECT_ORGANIZATION.md) and [Checklist](CHECKLIST.md)

## 📖 Main README

The main [README.md](../README.md) in the project root provides:
- Feature overview
- Installation instructions
- Basic usage examples
- Links to examples and documentation

## 📝 Examples

Practical examples are located in the `examples/` directory:
- `01_basic/` - Camera calibration and marker generation
- `02_single_marker/` - Single marker pose estimation
- `03_multi_marker/` - Multi-marker fusion
- `04_custom_models/` - Dodecahedron tracking
- `05_advanced/` - Optical flow, Kalman filtering, refinement

Each example directory has its own README with detailed usage instructions.

## 🛠️ Tools

Command-line tools are in the `tools/` directory:
- `cli.py` - Main CLI interface
- `visualize_aruco_extrinsics.py` - 3D visualization
- `visualize_dodecahedron_model.py` - Model visualization

See `tools/README.md` for detailed tool documentation.

## ❓ Getting Help

1. Check the relevant documentation file above
2. Review examples in `examples/`
3. Read the main [README.md](../README.md)
4. Open an issue on GitHub if you need assistance

---

**Last Updated:** December 2025  
**Version:** 0.2.0
