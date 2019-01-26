# Borrowed from https://gitlab.tiker.net/jdsteve2/perflex
import pyopencl as cl
import loopy as lp
import time
import numpy as np

def time_knl(knl, ctx, param_dict):
    def create_rand_args(ctx, knl, param_dict):
        queue = cl.CommandQueue(ctx)
        info = lp.generate_code_v2(knl).implemented_data_info
        args, arg_data = lp.auto_test.make_ref_args(
                knl,
                info,
                queue, param_dict)
        args.clear()
        del args
        rand_args = lp.auto_test.make_args(knl, info,
                queue, arg_data, param_dict)
        del arg_data[:]
        del arg_data
        return rand_args 

    queue = cl.CommandQueue(ctx)
    trial_wtimes = []
    arg_arrays = create_rand_args(ctx, knl, param_dict)
    knl = lp.set_options(knl, no_numpy=True)
    for t in range(2 + 3):
        queue.finish()
        tstart = time.time()
        evt, out = knl(queue, **arg_arrays)
        queue.finish()
        tend = time.time()
        trial_wtimes.append(tend-tstart)
    return np.average(trial_wtimes[2:])
