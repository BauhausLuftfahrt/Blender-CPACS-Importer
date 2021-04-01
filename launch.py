"""
    Created by Marc Engelmann
    Date: 08.07.2019
    © Bauhaus Luftfahrt e.V.

    (c) 2019 - 2021 Bauhaus Luftfahrt e.V.. All rights reserved. This program and the accompanying
    materials are made available under the terms of the GNU General Public License v3.0 which accompanies
    this distribution, and is available at https://www.gnu.org/licenses/gpl-3.0.html.en

"""

import subprocess
import os

if __name__ == "__main__":
    """
    This method launches Blender in the background and feeds the Python script as a launch argument. 
    This skips the manual import and automatically processes the Blender file. This file is used to test the import
    function of the Blender addon.
    Tested with Blender 2.92
    """

    home_path: str = os.path.expanduser('~')
    blender_installation_path: str = os.path.join(home_path, 'Blender\\blender.exe')
    python_script_path: str = os.path.join(home_path, 'git\\blender-cpacs-interface\\blender_cpacs_importer.py')
    cpacs_file_path: str = os.path.join(home_path, 'Desktop\\aircraft.xml')

    # Generate the launch arguments
    args: [str] = [blender_installation_path, "--background", '--python', python_script_path, '--', cpacs_file_path]

    # Run the process
    subprocess.call(args, shell=False)
