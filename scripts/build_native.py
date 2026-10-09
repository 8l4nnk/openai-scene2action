"""Build the optional geometry library; never run at application startup."""
import argparse
import os
import shutil
import subprocess
from pathlib import Path


def main():
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',help='Path to a clang++ or g++ compatible compiler')
    args=parser.parse_args()
    compiler=args.compiler or shutil.which('clang++') or shutil.which('g++')
    if not compiler and os.name=='nt':
        candidate=Path('C:/Program Files/LLVM/bin/clang++.exe')
        compiler=str(candidate) if candidate.is_file() else None
    if not compiler:
        parser.error('Install clang++ or g++, or pass --compiler; no runtime compiler is installed')
    output=root/'.data/native'
    output.mkdir(parents=True,exist_ok=True)
    filename='s2a_geometry.dll' if os.name=='nt' else 'libs2a_geometry.so'
    command=[compiler,'-std=c++17','-O2','-Wall','-Wextra','-Werror','-shared']
    if os.name!='nt':
        command+=['-fPIC','-fvisibility=hidden']
    # No fast-math: finite-number and boundary checks are safety gates.
    subprocess.run([*command,str(root/'native/geometry.cpp'),'-o',str(output/filename)],check=True)
    print(str(output/filename))


if __name__=='__main__':
    main()
