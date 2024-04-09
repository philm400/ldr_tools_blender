# ** FOR MacOS ONLY **
# Run by typing % sh build.sh
# in the terminal
# Build the main Rust library with Pyo3
# This outputs the compled file to the /target/release folder
# Macos: libldr_tools_py.dylib
echo ""
echo $'\e[38;5;240m==========================================='
# Set temporary $PATH for this session to your Blender addons folder for this addon
BLENDER_PATH="$HOME/Library/Application Support/Blender/4.0/scripts/addons/ldr_tools_blender"
PROJECT_FILES=("__init__.py" "colors.py" "importldr.py" "ldr_tools_py.so" "material.py" "operator.py")
export PYO3_CROSS_PYTHON_VERSION=3.10

# Build the Pyo3 library
PYO3_PYTHON="/Applications/Blender.app/Contents/Resources/4.0/python/bin/python3.10" cargo build --release
echo $'\e[32;1mPyo3 Compile Complete'

# copy python library to local add-on release folder
cp target/release/libldr_tools_py.dylib ldr_tools_blender/ldr_tools_py.so
echo $'\e[36m...Copy library to add-on release folder'

# copy all add-on files to the active addon folder in Blenders config folder using $BLENDER_PATH
echo $'\e[36m...Copying all files to Blender Add-on'
cp -a ldr_tools_blender/. "$BLENDER_PATH/"

echo $'\e[35;1mDeployment Complete'
echo $'\e[38;5;240m==========================================='
echo ""