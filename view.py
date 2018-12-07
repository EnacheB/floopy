from flask import jsonify, render_template, request,session

from lopsy import app

import loopy as lp
import numpy as np


@app.route('/')
def index():
    return render_template('base.html')


@app.route('/add', methods=['POST'])
def add():
    p_range = request.form.get('range', "", type=str)
    p_kernel = request.form.get('kernel', "", type=str)
    p_transform = request.form.get('transform', "", type=str)
    p_transforms = request.form.get('transforms', "", type=str)
    print("Transforms:")
    print(p_transforms)
    knl = lp.make_kernel(p_range,p_kernel,options=lp.Options(allow_terminal_colors=False))
    knl = lp.add_and_infer_dtypes(knl, {
        "a": np.float32,
        })

    if p_transform == 'split':
        knl = lp.split_iname(knl, "i", 128, outer_tag="g.0", inner_tag="l.0")


    code = lp.generate_code_v2(knl).device_code()
    print(session)

    return jsonify(high_level=str(knl),code=code,transforms=p_transforms )

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
