# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/12_speed.ipynb (unless otherwise specified).

__all__ = ['grid_1d', 'grid_2d', 'set_cuda_grid', 'parallel_compiled_func', 'AlphaPool', 'numba', 'cuda']

# Cell

# A decorator for writing GPU/CPU agnostic code
import multiprocessing
import threading
import functools
import math
import numba as numba_
numba = numba_
import numpy as np
from numba import cuda as cuda_
cuda = cuda_
from numba import njit

try:
    import cupy
    jit_fun = cuda.jit(device=True) #Device Function
except ModuleNotFoundError:
    import numpy as cupy
    jit_fun = njit

@numba.njit
def grid_1d(x): return -1
@numba.njit
def grid_2d(x): return -1, -1


def set_cuda_grid(dimensions=0):
    global cuda
    if dimensions == 0:
        cuda = cuda_
        cuda.grid = cuda_.grid
    if dimensions == 1:
        cuda = numba_
        cuda.grid = grid_1d
    if dimensions == 2:
        cuda = numba_
        cuda.grid = grid_2d

def parallel_compiled_func(
    _func=None,
    *,
    cpu_threads=None,
    dimensions=1,
    cpu_only = False,
):
    set_cuda_grid()
    if dimensions not in (1, 2):
        raise ValueError("Only 1D and 2D are supported")

    if cpu_threads is not None:
        use_gpu = False
    else:
        try:
            cuda.get_current_device()
        except cuda.CudaSupportError:
            use_gpu = False
            cpu_threads = 0
        else:
            use_gpu = True
        try:
            import cupy
        except ModuleNotFoundError:
            use_gpu = False
            cpu_threads = 0

    if cpu_only:
        use_gpu = False
        if cpu_threads is None:
            cpu_threads = 0

    if use_gpu:
        set_cuda_grid()
        def parallel_compiled_func_inner(func):
            cuda_func = cuda.jit(func)
            if dimensions == 1:
                def wrapper(iterable_1d, *args):
                    cuda_func.forall(iterable_1d.shape[0], 1)(
                        -1,
                        iterable_1d,
                        *args
                    )
            elif dimensions == 2:
                def wrapper(iterable_2d, *args):
                    threadsperblock = (
                        min(iterable_2d.shape[0], 16),
                        min(iterable_2d.shape[0], 16)
                    )
                    blockspergrid_x = math.ceil(
                        iterable_2d.shape[0] / threadsperblock[0]
                    )
                    blockspergrid_y = math.ceil(
                        iterable_2d.shape[1] / threadsperblock[1]
                    )
                    blockspergrid = (blockspergrid_x, blockspergrid_y)
                    cuda_func[blockspergrid, threadsperblock](
                        -1,
                        -1,
                        iterable_2d,
                        *args
                    )
            return functools.wraps(func)(wrapper)
    else:
        set_cuda_grid(dimensions)
        if cpu_threads <= 0:
            cpu_threads = multiprocessing.cpu_count()
        def parallel_compiled_func_inner(func):
            numba_func = numba.njit(nogil=True)(func)
            if dimensions == 1:
                def numba_func_parallel(
                    thread,
                    iterable_1d,
                    *args
                ):
                    for i in range(
                        thread,
                        len(iterable_1d),
                        cpu_threads
                    ):
                        numba_func(i, iterable_1d, *args)
            elif dimensions == 2:
                def numba_func_parallel(
                    thread,
                    iterable_2d,
                    *args
                ):
                    for i in range(
                        thread,
                        iterable_2d.shape[0],
                        cpu_threads
                    ):
                        for j in range(iterable_2d.shape[1]):
                            numba_func(i, j, iterable_2d, *args)
            numba_func_parallel = numba.njit(nogil=True)(numba_func_parallel)
            def wrapper(iterable, *args):
                threads = []
                for thread_id in range(cpu_threads):
                    t = threading.Thread(
                        target=numba_func_parallel,
                        args=(thread_id, iterable, *args)
                    )
                    t.start()
                    threads.append(t)
                for t in threads:
                    t.join()
                    del t
            return functools.wraps(func)(wrapper)
    if _func is None:
        return parallel_compiled_func_inner
    else:
        return parallel_compiled_func_inner(_func)

import psutil
from multiprocessing import Pool
import os

def AlphaPool(a, *args, **kwargs):

    p = psutil.Process(os.getpid())
    with p.oneshot():
        n_threads = p.num_threads()

    new_max = min(a, 62-n_threads)
    print(f"AlphaPool {n_threads} threads running. Setting max to {new_max}.")

    return Pool(new_max)