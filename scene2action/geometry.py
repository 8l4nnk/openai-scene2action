"""Explicit per-engine Python/C++ 2D geometry backends. Native never falls back."""
import ctypes
import math
import os
from pathlib import Path

from .simulator import CLEARANCE, segment_blocked


def _pack(points, boxes, radius):
    if not 2 <= len(points) <= 1024 or len(boxes) > 4096:
        raise ValueError('Geometry exceeds supported bounds')
    if isinstance(radius,bool) or not math.isfinite(radius) or not 0 <= radius <= .5:
        raise ValueError('Invalid radius')
    flattened=[]
    for rows,width in ((points,2),(boxes,4)):
        values=[]
        for row in rows:
            if len(row)!=width:
                raise ValueError('Invalid geometry shape')
            for value in row:
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
                    raise ValueError('Invalid geometry number')
                if not 0 <= value <= 1:
                    raise ValueError('Invalid normalized coordinate')
                values.append(float(value))
            if width==4 and (row[0]>row[2] or row[1]>row[3]):
                raise ValueError('Invalid obstacle bounds')
        flattened.append(values)
    return flattened


class PythonGeometry:
    name='python'

    def _clear(self,points,boxes,radius):
        try:
            _pack(points,boxes,radius)
            return all(not segment_blocked(a,b,boxes,radius) for a,b in zip(points,points[1:]))
        except (ValueError,TypeError,KeyError,OverflowError):
            return False

    def segment_blocked(self,start,end,boxes,radius):
        return not self._clear([start,end],boxes,radius)

    def path_clear(self,commands,world):
        try:
            return self._clear([world['position'],*[c['position'] for c in commands]],world['obstacles'],CLEARANCE)
        except (ValueError,TypeError,KeyError):
            return False


class NativeGeometry(PythonGeometry):
    name='native'

    def __init__(self,library_path):
        try:
            path=Path(library_path).resolve(strict=True)
            if not path.is_file():
                raise ValueError('Not a library file')
            self._library=ctypes.CDLL(str(path))
            abi=self._library.s2a_geometry_abi
            abi.argtypes=[]
            abi.restype=ctypes.c_int
            if abi()!=1:
                raise ValueError('Unsupported ABI')
            self._function=self._library.s2a_path_clear
            self._function.argtypes=[ctypes.POINTER(ctypes.c_double),ctypes.c_size_t,
                                    ctypes.POINTER(ctypes.c_double),ctypes.c_size_t,ctypes.c_double]
            self._function.restype=ctypes.c_int
        except (OSError,ValueError,AttributeError):
            raise RuntimeError('Required native geometry library is missing or incompatible; no fallback') from None

    def _clear(self,points,boxes,radius):
        try:
            p,b=_pack(points,boxes,radius)
            p_buffer=(ctypes.c_double*len(p))(*p)
            b_buffer=(ctypes.c_double*len(b))(*b)
            return self._function(p_buffer,len(points),b_buffer,len(boxes),radius)==1
        except (ValueError,TypeError,KeyError,OverflowError,ctypes.ArgumentError):
            return False


def configured_geometry():
    backend=os.getenv('S2A_GEOMETRY_BACKEND','python')
    if backend=='python':
        return PythonGeometry()
    if backend!='native':
        raise ValueError('Unknown geometry backend; select python or native')
    filename='s2a_geometry.dll' if os.name=='nt' else 'libs2a_geometry.so'
    return NativeGeometry(os.getenv('S2A_NATIVE_LIBRARY') or Path('.data/native')/filename)
