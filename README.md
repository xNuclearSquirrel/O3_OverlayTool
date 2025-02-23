# O3-OverlayTool

A Tool for rendering videos from .osd files recorded from the O3 Air unit.

## NOTES
- A portable version with a standalone executable has been added in the release section. Works without any libraries etc. I recommend using that one, it is a bit simpler.

- This is a work in progress, there might be bugs.
- The tool doesn't directly overlay over footage, it simply creates the OSD frames on top of a chroma key or a transparent background. The overlaying needs to be done in a video editor.
- The best results will be achieved when overlaying over Air Unit DVR rather than goggles DVR.
- Transparent background will have better results because it maintains semi-transparency of the OSD font! It's also faster!
- Works with files created with https://github.com/xNuclearSquirrel/o3-multipage-osd. Files created with Walksnail of Vista-WTFOS (on the newest update) are also supported.


## Usage
To launch the GUI:
-Run OverlayTool.py or the run.bat.
-or download the portable release and run OverlayTool.exe (Windows only). 

## Required libraries
- numpy, pandas, opencv-python, pillow
- ~~FFMPEG (when using transparent backgrounds)~~ included now.

The portable version should work without any libraries.

## TODO
- Add support for other .osd file format. Such as ~~Vista .osd files~~(done) or ~~Walksnail .osd files~~ (done).

## Credits
Credits to the fpv-wtf devs for making this possible and to SNEAKY_FPV for the fonts! More fonts available at https://sites.google.com/view/sneaky-fpv/home
