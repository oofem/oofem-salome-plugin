#!/bin/bash

echo "=== OOFEM-Salome-Plugin Installer (Linux) ==="
echo ""

# Stop script on error
set -e

# 1. Check for SALOME_ROOT_DIR
if [ -z "$SALOME_ROOT_DIR" ]; then
    echo "ERROR: SALOME_ROOT_DIR is not set."
    echo "Please set it to your Salome installation directory, for example:"
    echo "export SALOME_ROOT_DIR=/opt/salome-9.15.0"
    exit 1
fi

SOURCE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/src/OOFEMSalomePlugin"
TARGET_DIR="$SALOME_ROOT_DIR/modules/OOFEMSalomePlugin"

# 2. Validate source directory
if [ ! -d "$SOURCE_DIR" ]; then
    echo "ERROR: Source directory not found at: $SOURCE_DIR"
    echo "Please run this script from the project's root directory."
    exit 1
fi

echo "Installing plugin into: $TARGET_DIR"

# 3. Create target directory and copy files
mkdir -p "$TARGET_DIR"
cp -r "$SOURCE_DIR"/* "$TARGET_DIR"

echo ""
echo "✔ Installation complete. Please restart Salome."
