# O3-OverlayTool

A Tool for rendering videos form .osd files recorded from the O3 Air unit.

## NOTES
- This is a work in progress, there might be bugs.
- The tool doesn't overlay over action footage, it simply creates the OSD frames on top of a chroma key or a transparent background. The overlaying needs to be done in a video editor.
- Transparent background will have better results because it maintains semi-transparency of the OSD font, but it requires FFMPEG to be installed and available in the console.
- Currently works with .osd files created with this mod https://github.com/xNuclearSquirrel/O3-OSD-recording

## Usage
Run OverlayTool.py to launch the GUI. 

## Required libraries
- numpy, pandas, opencv-python, pillow
- FFMPEG (when using transparent backgrounds)

## Credits
Credits to the fpv-wtf devs for making this possible and to SNEAKY_FPV for the fonts! More fonts available at https://sites.google.com/view/sneaky-fpv/home
