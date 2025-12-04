#!/bin/bash

#remove existing virtual environment if it exists
if [ -d "startup_venv" ]; then
    echo "Removing existing virtual environment..."
    rm -fr startup_venv
fi
# Create a new virtual environment
echo "Creating a new virtual environment..."
python3 -m venv startup_venv

# Activate the virtual environment
echo "Activating the virtual environment..."
source startup_venv/bin/activate

# Upgrade pip to the latest version
echo "Upgrading pip..."
pip install --upgrade pip

# Install required packages from requirements.txt
echo "Installing required packages..."
pip install -r requirements.txt

#Change directory to medconsult
cd medconsult

# done
echo "Setup complete. Virtual environment 'startup_venv' is ready and required packages are installed."