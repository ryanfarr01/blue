"""
Class definition for OpenMDAOServerRecorder, which provides access to the OpenMDAO server endpoints.
"""

import io
import requests

import json
import numpy as np
from six import iteritems
from six.moves import cPickle as pickle

from openmdao.core.driver import Driver
from openmdao.core.system import System
from openmdao.recorders.base_recorder import BaseRecorder
from openmdao.solvers.solver import Solver, NonlinearSolver
from openmdao.recorders.recording_iteration_stack import get_formatted_iteration_coordinate

format_version = 1
_endpoint = 'http://127.0.0.1:8000/'

class OpenMDAOServerRecorder(BaseRecorder):
    """
    Recorder that saves cases to the OpenMDAO server

    Attributes
    ----------
    model_viewer_data : dict
        Dict that holds the data needed to generate N2 diagram.
    """

    def __init__(self):
        """
        Initialize the OpenMDAOServerRecorder.
        """
        super(OpenMDAOServerRecorder, self).__init__()

        self.model_viewer_data = None
        case_request = requests.post(_endpoint + 'case', data = {
            'case_name': 'test',
            'owner': 'temp_owner'
            })
        response = case_request.json()
        self._case_id = response['case_id']

    def record_iteration(self, object_requesting_recording, metadata, **kwargs):
        """
        Store the provided data in the OpenMDAO server using the iteration coordinate for the key.

        Parameters
        ----------
        object_requesting_recording: <object>
            The item, a System, Solver, or Driver that wants to record an iteration.
        metadata : dict
            Dictionary containing execution metadata (e.g. iteration coordinate).
        **kwargs :
            Various keyword arguments needed for System or Solver recordings.
        """
        super(OpenMDAOServerRecorder, self).record_iteration(object_requesting_recording, metadata)

        if isinstance(object_requesting_recording, Driver):
            self.record_iteration_driver(object_requesting_recording, metadata)

        elif isinstance(object_requesting_recording, System):
            self.record_iteration_system(object_requesting_recording, metadata, kwargs['method'])

        elif isinstance(object_requesting_recording, Solver):
            self.record_iteration_solver(object_requesting_recording, metadata, **kwargs)
        else:
            raise ValueError("Recorders must be attached to Drivers, Systems, or Solvers.")

    def record_iteration_driver(self, object_requesting_recording, metadata):
        """
        Record an iteration using the driver options.

        Parameters
        ----------
        object_requesting_recording: <Driver>
            The Driver object that wants to record an iteration.
        metadata : dict
            Dictionary containing execution metadata (e.g. iteration coordinate).
        """
        # make a nested numpy named array using the example
        #   http://stackoverflow.com/questions/19201868/how-to-set-dtype-for-nested-numpy-ndarray
        # e.g.
        # table = np.array(data, dtype=[('instrument', 'S32'),
        #                        ('filter', 'S64'),
        #                        ('response', [('linenumber', 'i'),
        #                                      ('wavelength', 'f'),
        #                                      ('throughput', 'f')], (2,))
        #                       ])

        desvars_array = None
        responses_array = None
        objectives_array = None
        constraints_array = None

        # Just an example of the syntax for creating a numpy structured array
        # arr = np.zeros((1,), dtype=[('dv_x','(5,)f8'),('dv_y','(10,)f8')])

        # This returns a dict of names and values. Use this to build up the tuples of
        # used for the dtypes in the creation of the numpy structured array
        # we want to write to the OpenMDAO server
        if self.options['record_desvars']:
            if self._filtered_driver:
                desvars_values = \
                    object_requesting_recording.get_design_var_values(self._filtered_driver['des'])
            else:
                desvars_values = object_requesting_recording.get_design_var_values()

            if desvars_values:
                dtype_tuples = []
                for name, value in iteritems(desvars_values):
                    tple = (name, '{}f8'.format(value.shape))
                    dtype_tuples.append(tple)

                desvars_array = np.zeros((1,), dtype=dtype_tuples)

                for name, value in iteritems(desvars_values):
                    desvars_array[name] = value

        if self.options['record_responses']:
            if self._filtered_driver:
                responses_values = \
                    object_requesting_recording.get_response_values(self._filtered_driver['res'])
            else:
                responses_values = object_requesting_recording.get_response_values()

            if responses_values:
                dtype_tuples = []
                for name, value in iteritems(responses_values):
                    tple = (name, '{}f8'.format(value.shape))
                    dtype_tuples.append(tple)

                responses_array = np.zeros((1,), dtype=dtype_tuples)

                for name, value in iteritems(responses_values):
                    responses_array[name] = value

        if self.options['record_objectives']:
            if self._filtered_driver:
                objectives_values = \
                    object_requesting_recording.get_objective_values(self._filtered_driver['obj'])
            else:
                objectives_values = object_requesting_recording.get_objective_values()

            if objectives_values:
                dtype_tuples = []
                for name, value in iteritems(objectives_values):
                    tple = (name, '{}f8'.format(value.shape))
                    dtype_tuples.append(tple)

                objectives_array = np.zeros((1,), dtype=dtype_tuples)

                for name, value in iteritems(objectives_values):
                    objectives_array[name] = value

        if self.options['record_constraints']:
            if self._filtered_driver:
                constraints_values = \
                    object_requesting_recording.get_constraint_values(self._filtered_driver['con'])
            else:
                constraints_values = object_requesting_recording.get_constraint_values()

            if constraints_values:
                dtype_tuples = []
                for name, value in iteritems(constraints_values):
                    tple = (name, '{}f8'.format(value.shape))
                    dtype_tuples.append(tple)

                constraints_array = np.zeros((1,), dtype=dtype_tuples)

                for name, value in iteritems(constraints_values):
                    constraints_array[name] = value

        iteration_coordinate = get_formatted_iteration_coordinate()

        driver_iteration_dict = {
            "counter": self._counter,
            "iteration_coordinate": iteration_coordinate,
            "success": metadata['success'],
            "msg": metadata['msg'],
            "desvars": desvars_array,
            "responses": responses_array,
            "objectives": objectives_array,
            "constraints": constraints_array
        }

        global_iteration_dict = {
            'record_type': 'driver',
            'counter': self._counter
        }

        driver_iteration = json.dumps(driver_iteration_dict)
        global_iteration = json.dumps(global_iteration_dict)
        
        requests.post(_endpoint + self._case_id + '/driver_iterations', data=driver_iteration)
        requests.post(_endpoint + self._case_id + '/global_iterations', data=global_iteration)

    def record_iteration_system(self, object_requesting_recording, metadata, method):
        """
        Record an iteration using system options.

        Parameters
        ----------
        object_requesting_recording: <System>
            The System object that wants to record an iteration.
        metadata : dict
            Dictionary containing execution metadata (e.g. iteration coordinate).
        method : str
            The method that called record_iteration. One of '_apply_linear', '_solve_linear',
            '_apply_nonlinear,' '_solve_nonlinear'. Behavior varies based on from which function
            record_iteration was called.
        """
        if method not in ['_apply_linear', '_apply_nonlinear', '_solve_linear',
                          '_solve_nonlinear']:
            raise ValueError("method must be one of: '_apply_linear, "
                             "_apply_nonlinear, _solve_linear, _solve_nonlinear'")

        if 'nonlinear' in method:
            inputs, outputs, residuals = object_requesting_recording.get_nonlinear_vectors()
        else:
            inputs, outputs, residuals = object_requesting_recording.get_linear_vectors()

        inputs_array = outputs_array = residuals_array = None

        # Inputs
        if self.options['record_inputs'] and inputs._names:
            ins = {}
            if 'i' in self._filtered_system:
                # use filtered inputs
                for inp in self._filtered_system['i']:
                    if inp in inputs._names:
                        ins[inp] = inputs._names[inp]
            else:
                # use all the inputs
                ins = inputs._names

            dtype_tuples = []
            for name, value in iteritems(ins):
                tple = (name, '({},)f8'.format(len(value)))
                dtype_tuples.append(tple)

            inputs_array = np.zeros((1,), dtype=dtype_tuples)
            for name, value in iteritems(ins):
                inputs_array[name] = value

        # Outputs
        if self.options['record_outputs'] and outputs._names:
            outs = {}

            if 'o' in self._filtered_system:
                # use outputs from filtered list.
                for out in self._filtered_system['o']:
                    if out in outputs._names:
                        outs[out] = outputs._names[out]
            else:
                # use all the outputs
                outs = outputs._names

            dtype_tuples = []
            for name, value in iteritems(outs):
                tple = (name, '({},)f8'.format(len(value)))
                dtype_tuples.append(tple)

            outputs_array = np.zeros((1,), dtype=dtype_tuples)
            for name, value in iteritems(outs):
                outputs_array[name] = value

        # Residuals
        if self.options['record_residuals'] and residuals._names:
            resids = {}

            if 'r' in self._filtered_system:
                # use filtered residuals
                for res in self._filtered_system['r']:
                    if res in residuals._names:
                        resids[res] = residuals._names[res]
            else:
                # use all the residuals
                resids = residuals._names

            dtype_tuples = []
            if resids:
                for name, value in iteritems(resids):
                    tple = (name, '({},)f8'.format(len(value)))
                    dtype_tuples.append(tple)

                residuals_array = np.zeros((1,), dtype=dtype_tuples)
                for name, value in iteritems(resids):
                    residuals_array[name] = value

        iteration_coordinate = get_formatted_iteration_coordinate()
        system_iteration_dict = {
            'counter': self._counter,
            'iteration_coordinate': iteration_coordinate,
            'success': metadata['success'],
            'msg': metadata['msg'],
            'inputs': inputs_array,
            'outputs': outputs_array,
            'residuals': residuals_array
        }

        global_iteration_dict = {
            'record_type': 'system',
            'counter': self._counter
        }

        system_iteration = json.dumps(system_iteration_dict)
        global_iteration = json.dumps(global_iteration_dict)

        requests.post(_endpoint + self._case_id + '/system_iterations', data=system_iteration)
        requests.post(_endpoint + self._case_id + '/global_iterations', data=global_iteration)

    def record_iteration_solver(self, object_requesting_recording, metadata, **kwargs):
        """
        Record an iteration using solver options.

        Parameters
        ----------
        object_requesting_recording: <Solver>
            The Solver object that wants to record an iteration.
        metadata : dict
            Dictionary containing execution metadata (e.g. iteration coordinate).
        absolute : float
            The absolute error of the Solver requesting recording. It is not cached in
            the Solver object, so we pass it in here.
        relative : float
            The relative error of the Solver requesting recording. It is not cached in
            the Solver object, so we pass it in here.
        """
        outputs_array = residuals_array = None

        # Go through the recording options of Solver to construct the entry to be inserted.
        if self.options['record_abs_error']:
            abs_error = kwargs.get('abs')
        else:
            abs_error = None

        if self.options['record_rel_error']:
            rel_error = kwargs.get('rel')
        else:
            rel_error = None

        if self.options['record_solver_output']:
            dtype_tuples = []

            if isinstance(object_requesting_recording, NonlinearSolver):
                outputs = object_requesting_recording._system._outputs
            else:  # it's a LinearSolver
                outputs = object_requesting_recording._system._vectors['output']['linear']

            outs = {}
            if 'out' in self._filtered_solver:
                for outp in outputs._names:
                    outs[outp] = outputs._names[outp]
            else:
                outs = outputs

            if outs:
                for name, value in iteritems(outs):
                    tple = (name, '{}f8'.format(value.shape))
                    dtype_tuples.append(tple)

                outputs_array = np.zeros((1,), dtype=dtype_tuples)

                for name, value in iteritems(outs):
                    outputs_array[name] = value

        if self.options['record_solver_residuals']:
            dtype_tuples = []

            if isinstance(object_requesting_recording, NonlinearSolver):
                residuals = object_requesting_recording._system._residuals
            else:  # it's a LinearSolver
                residuals = object_requesting_recording._system._vectors['residual']['linear']

            res = {}
            if 'res' in self._filtered_solver:
                for rez in residuals._names:
                    res[rez] = residuals._names[rez]
            else:
                res = residuals

            if res:
                for name, value in iteritems(res):
                    tple = (name, '{}f8'.format(value.shape))
                    dtype_tuples.append(tple)

                residuals_array = np.zeros((1,), dtype=dtype_tuples)
                for name, value in iteritems(res):
                    residuals_array[name] = value

        iteration_coordinate = get_formatted_iteration_coordinate()

        solver_iteration_dict = {
            'counter': self._counter,
            'iteration_coordinate': iteration_coordinate,
            'success': metadata['success'],
            'msg': metadata['msg'],
            'abs_err': abs_error,
            'rel_err': rel_error,
            'solver_output': outputs_array,
            'solver_residuals': residuals_array
        }

        global_iteration_dict = {
            'record_type': 'solver',
            'counter': self._counter
        }

        solver_iteration = json.dumps(solver_iteration_dict)
        global_iteration = json.dumps(global_iteration_dict)

        requests.post(_endpoint + self._case_id + '/solver_iterations', data=solver_iteration)
        requests.post(_endpoint + self._case_id + '/global_iterations', data=global_iteration)

    def record_metadata(self, object_requesting_recording):
        """
        Route the record_metadata call to the proper object.

        Parameters
        ----------
        object_requesting_recording: <object>
            The object that would like to record its metadata.
        """
        if self.options['record_metadata']:
            if isinstance(object_requesting_recording, Driver):
                self.record_metadata_driver(object_requesting_recording)
            elif isinstance(object_requesting_recording, System):
                self.record_metadata_system(object_requesting_recording)
            elif isinstance(object_requesting_recording, Solver):
                self.record_metadata_solver(object_requesting_recording)

    def record_metadata_driver(self, object_requesting_recording):
        """
        Record driver metadata.

        Parameters
        ----------
        object_requesting_recording: <Driver>
            The Driver that would like to record its metadata.
        """
        driver_class = type(object_requesting_recording).__name__
        model_viewer_data = json.dumps(object_requesting_recording._model_viewer_data)
        
        driver_metadata_dict = {
            'id': driver_class,
            'model_viewer_data': model_viewer_data
        }
        driver_metadata = json.dumps(driver_metadata_dict)

        requests.post(_endpoint + self._case_id + '/driver_metadata', data=driver_metadata)

    def record_metadata_system(self, object_requesting_recording):
        """
        Record system metadata.

        Parameters
        ----------
        object_requesting_recording: <System>
            The System that would like to record its metadata.
        """
        scaling_factors = json.dumps(object_requesting_recording._scaling_vecs)
        system_metadata_dict = {
            'id': object_requesting_recording.pathname,
            'scaling_factors': scaling_factors
        }
        system_metadata = json.dumps(system_metadata_dict)
        
        requests.post(_endpoint + self._case_id + '/system_metadata', data=system_metadata)

    def record_metadata_solver(self, object_requesting_recording):
        """
        Record solver metadata.

        Parameters
        ----------
        object_requesting_recording: <Solver>
            The Solver that would like to record its metadata.
        """
        path = object_requesting_recording._system.pathname
        solver_class = type(object_requesting_recording).__name__
        id = "%s.%s".format(path, solver_class)

        solver_options = json.dumps(object_requesting_recording.options)
        solver_metadata_dict = {
            'id': id,
            'solver_options': solver_options,
            'solver_class': solver_class
        }
        solver_metadata = json.dumps(solver_metadata_dict)

        requests.post(_endpoint + self._case_id + '/solver_metadata', data=solver_metadata)

    def close(self):
        """
        Close `out`.
        """
        pass
