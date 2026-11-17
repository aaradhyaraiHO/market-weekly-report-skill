"""Run report Python scripts with scoped BQ rules, including Python children.

Normal interpreter startup has already completed. Never replace sitecustomize,
PYTHONPATH, credential scopes, installed packages, or the analytics checkout.
"""
import runpy
import subprocess
import sys
from pathlib import Path
from report_runtime import install, command

def main():
    install()
    original = subprocess.Popen
    class ReportPopen(original):
        def __init__(self, args, *a, **kw):
            if isinstance(args, (list, tuple)) and not kw.get('shell'):
                args = command(args)
            super().__init__(args, *a, **kw)
    subprocess.Popen = ReportPopen
    target = Path(sys.argv[1]).resolve()
    sys.argv = [str(target), *sys.argv[2:]]
    sys.path.insert(0, str(target.parent))
    runpy.run_path(str(target), run_name='__main__')

if __name__ == '__main__': main()
