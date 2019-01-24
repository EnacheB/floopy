from flask import jsonify, render_template, request,session

from floopy import app

import loopy as lp
import numpy as np
import pyopencl as cl
import collections
import six

from floopy.loopy_bits import knl_to_json
from floopy.perflex_bits import time_knl


# Maker into python string
def mps(thing):
    return """ '""" + thing + """' """


@app.route('/')
def index():
    return render_template('base.html')


@app.route('/process_kernel_transforms', methods=['POST'])
def process_kernel_transforms():
    print("StARTING")
    p_range = request.form.get('range', "", type=str)
    p_kernel = request.form.get('kernel', "", type=str)
    p_transforms = request.form.getlist('transforms[]')
    p_target = request.form.get('target', 'opencl', type=str)
    performance_measure = False
    timing = 0.0
    value_dict = {}

    lines = []
    if p_target == 'c':
        target = "lp.CTarget()"
    elif p_target == 'cuda':
        target = "lp.CudaTarget()"
    else:
        target = "lp.OpenCLTarget()"

    knl = None
    try:
        lines.append("lp.make_kernel(p_range,p_kernel,options=lp.Options(allow_terminal_colors=False), target=" + target +")")
        types = '{ '
        for transf in p_transforms:
            transf_array = transf.split(':')
            target, which, operation = transf_array[:3]
            options = transf_array[3:]
            if operation == 'type':
                assert(len(options) == 1)
                if options[0] == 'f32':
                    typ = 'np.float32'
                elif options[0] == 'f64':
                    typ = 'np.float64'
                elif options[0] == 'i32':
                    typ = 'np.int32'
                else:
                    raise ValueError("Unknown type requested for argument " + which)
                types  = types + mps(which) + ':' + typ + ','

        types = types[:-1] + '}'
        lines.append("lp.add_and_infer_dtypes(knl, " + types + ")")

        for transf in p_transforms:
            transf_array = transf.split(':')
            target, which, operation = transf_array[:3]
            options = transf_array[3:]
            if target == 'iname':
                if operation == 'split':
                    assert(len(options) == 3)
                    lines.append("lp.split_iname(knl," + mps(which) + " , " + options[0] + ", slabs = (" + options[1] + ", " + options[2] + "))")
                if operation == 'tag':
                    assert(len(options) == 1)
                    lines.append("lp.tag_inames(knl, [( " + mps(which) + "," + mps(options[0]) + "),])")
                if operation == 'prioritize':
                    assert(len(options) == 1)
                    lines.append("lp.prioritize_loops(knl," +  mps(options[0]) + ")")

            if target == 'arg':
                if operation == 'prefetch':
                    if options == ['',]:
                        options = []
                    lines.append("lp.add_prefetch(knl, " + mps(which) + "," + str(options) + ")")
                if operation == 'subst':
                    if options == ['',]:
                        options = []
                    lines.append("lp.extract_subst(knl, " + mps(options[0]) + "," + mps(which + '[' + options[1] + ']' ) + ", parameters = " + mps(options[2]) + ")")
                if operation == 'split':
                    if options == ['',]:
                        options = []
                    lines.append("lp.split_array_axis(knl, " + mps(which) + "," + options[0] + ", " +  options[1] + ")")
                if operation == 'perf':
                    if options == ['',]:
                        options = []
                    performance_measure = True
                    value_dict[which] = int(options[0])

            if target == 'rule':
                if operation == 'precompute':
                    if options == ['',]:
                        options = []
                    performance_measure = True
                    lines.append("lp.precompute(knl, " + mps(which) + "," + str(options) + ")")

            if target == 'any':
                    lines.append(operation)


        for line in lines:
            knl = eval(line)

        if p_target == 'python':
            code = '\n'.join(('knl = ' + l for l in lines))
        else:
            code = lp.generate_code_v2(knl).device_code()

        if performance_measure:
            ctx = cl.create_some_context(interactive=False)
            print(value_dict)
            timing = time_knl(knl,ctx,value_dict)
        print("RETURNING")
    except Exception as inst:
        #raise inst
        return jsonify(high_level2=knl_to_json(knl), high_level=str(knl),code=str(inst),transforms=p_transforms, err=True, timing = timing )

    return jsonify(high_level2=knl_to_json(knl), high_level=str(knl),code=code,transforms=p_transforms, err=False, timing = timing)

# TODO remove this
@app.after_request
def add_header(response):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also to cache the rendered page for 10 minutes.
    """
    response.headers['X-UA-Compatible'] = 'IE=Edge,chrome=1'
    response.headers['Cache-Control'] = 'public, max-age=0'
    return response
