from openmdao.test_suite.components.paraboloid import Paraboloid


class ParaboloidMatVec(Paraboloid):
    """ Use matrix-vector product."""

    def compute_partials(self, inputs, outputs, partials):
        """Analytical derivatives."""
        pass

    def compute_jacvec_product(self, inputs, outputs, dinputs, dresids, mode):
        """Returns the product of the incoming vector with the Jacobian."""

        x = inputs['x']
        y = inputs['y']

        if mode == 'fwd':
            if 'x' in dinputs:
                dresids['f_xy'] += (2.0*x - 6.0 + y)*dinputs['x']
            if 'y' in dinputs:
                dresids['f_xy'] += (2.0*y + 8.0 + x)*dinputs['y']

        elif mode == 'rev':
            if 'x' in dinputs:
                dinputs['x'] += (2.0*x - 6.0 + y)*dresids['f_xy']
            if 'y' in dinputs:
                dinputs['y'] += (2.0*y + 8.0 + x)*dresids['f_xy']
