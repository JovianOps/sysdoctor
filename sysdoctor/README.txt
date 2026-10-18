sysdoctor - cross-platform system diagnostics and safe cleanup

Run without building (needs Python 3.9+):
    python sysdoctor.py info

Build a standalone executable (build on the OS you are targeting):
    Windows : double-click build.bat      -> dist\sysdoctor.exe
    Linux   : ./build.sh                  -> dist/sysdoctor

Commands: info | disk | big PATH | net | path | clean [--days N] [--apply]
Run "sysdoctor --help" for details. "clean" is a dry run unless --apply is given.

Note: unsigned PyInstaller one-file executables are sometimes flagged by
Windows SmartScreen or antivirus. This is a known false positive.
