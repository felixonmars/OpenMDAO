""" Testing for Problem.check_partials and check_totals."""

import unittest
from six import iteritems
from six.moves import cStringIO

import numpy as np

from openmdao.api import Group, ExplicitComponent, IndepVarComp, Problem, NonlinearRunOnce, \
                         ImplicitComponent, NonlinearBlockGS, LinearBlockGS, ParallelGroup, \
                         ExecComp
from openmdao.test_suite.components.impl_comp_array import TestImplCompArrayMatVec
from openmdao.test_suite.components.paraboloid_mat_vec import ParaboloidMatVec
from openmdao.test_suite.components.sellar import SellarDerivatives
from openmdao.test_suite.groups.parallel_groups import FanInSubbedIDVC
from openmdao.utils.assert_utils import assert_rel_error
from openmdao.utils.mpi import MPI

if MPI:
    from openmdao.api import PETScVector
    vector_class = PETScVector
else:
    from openmdao.api import DefaultVector
    vector_class = DefaultVector


class ParaboloidTricky(ExplicitComponent):
    """
    Evaluates the equation f(x,y) = (x-3)^2 + xy + (y+4)^2 - 3.
    """

    def setup(self):
        self.add_input('x', val=0.0)
        self.add_input('y', val=0.0)

        self.add_output('f_xy', val=0.0)

        self.scale = 1e-7

        self.declare_partials(of='*', wrt='*')

    def compute(self, inputs, outputs):
        """
        f(x,y) = (x-3)^2 + xy + (y+4)^2 - 3

        Optimal solution (minimum): x = 6.6667; y = -7.3333
        """
        sc = self.scale
        x = inputs['x']*sc
        y = inputs['y']*sc

        outputs['f_xy'] = (x-3.0)**2 + x*y + (y+4.0)**2 - 3.0

    def compute_partials(self, inputs, partials):
        """
        Jacobian for our paraboloid.
        """
        sc = self.scale
        x = inputs['x']
        y = inputs['y']

        partials['f_xy', 'x'] = 2.0*x*sc*sc - 6.0*sc + y*sc*sc
        partials['f_xy', 'y'] = 2.0*y*sc*sc + 8.0*sc + x*sc*sc


class TestProblemCheckPartials(unittest.TestCase):

    def test_incorrect_jacobian(self):
        class MyComp(ExplicitComponent):
            def setup(self):
                self.add_input('x1', 3.0)
                self.add_input('x2', 5.0)

                self.add_output('y', 5.5)

                self.declare_partials(of='*', wrt='*')

            def compute(self, inputs, outputs):
                """ Doesn't do much. """
                outputs['y'] = 3.0*inputs['x1'] + 4.0*inputs['x2']

            def compute_partials(self, inputs, partials):
                """Intentionally incorrect derivative."""
                J = partials
                J['y', 'x1'] = np.array([4.0])
                J['y', 'x2'] = np.array([40])

        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x1', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('x2', 5.0))
        prob.model.add_subsystem('comp', MyComp())

        prob.model.connect('p1.x1', 'comp.x1')
        prob.model.connect('p2.x2', 'comp.x2')

        prob.set_solver_print(level=0)

        prob.setup(check=False)
        prob.run_model()

        stream = cStringIO()
        prob.check_partials(out_stream=stream)
        lines = stream.getvalue().splitlines()

        y_wrt_x1_line = lines.index("  comp: 'y' wrt 'x1'")

        print(lines)
        self.assertTrue(lines[y_wrt_x1_line+3].endswith('*'),
                        msg='Error flag expected in output but not displayed')
        self.assertTrue(lines[y_wrt_x1_line+5].endswith('*'),
                        msg='Error flag expected in output but not displayed')

        y_wrt_x2_line = lines.index("  comp: 'y' wrt 'x2'")
        self.assertTrue(lines[y_wrt_x2_line+3].endswith('*'),
                         msg='Error flag not expected in output but displayed')
        self.assertTrue(lines[y_wrt_x2_line+5].endswith('*'),
                         msg='Error flag not expected in output but displayed')

    def test_component_only(self):
        class MyComp(ExplicitComponent):
            def setup(self):
                self.add_input('x1', 3.0)
                self.add_input('x2', 5.0)

                self.add_output('y', 5.5)

                self.declare_partials(of='*', wrt='*')

            def compute(self, inputs, outputs):
                """ Doesn't do much. """
                outputs['y'] = 3.0*inputs['x1'] + 4.0*inputs['x2']

            def compute_partials(self, inputs, partials):
                """Intentionally incorrect derivative."""
                J = partials
                J['y', 'x1'] = np.array([4.0])
                J['y', 'x2'] = np.array([40])

        prob = Problem()
        prob.model = MyComp()

        prob.set_solver_print(level=0)

        prob.setup(check=False)
        prob.run_model()

        stream = cStringIO()
        prob.check_partials(out_stream=stream)
        lines = stream.getvalue().splitlines()

        y_wrt_x1_line = lines.index("  : 'y' wrt 'x1'")


        print(lines)

        self.assertTrue(lines[y_wrt_x1_line+3].endswith('*'),
                        msg='Error flag expected in output but not displayed')
        self.assertTrue(lines[y_wrt_x1_line+5].endswith('*'),
                        msg='Error flag expected in output but not displayed')
        # self.assertFalse(lines[y_wrt_x1_line+6].endswith('*'),
        #                  msg='Error flag not expected in output but displayed')

    def test_component_only_suppress(self):
        class MyComp(ExplicitComponent):
            def setup(self):
                self.add_input('x1', 3.0)
                self.add_input('x2', 5.0)

                self.add_output('y', 5.5)

                self.declare_partials(of='*', wrt='*')

            def compute(self, inputs, outputs):
                """ Doesn't do much. """
                outputs['y'] = 3.0*inputs['x1'] + 4.0*inputs['x2']

            def compute_partials(self, inputs, partials):
                """Intentionally incorrect derivative."""
                J = partials
                J['y', 'x1'] = np.array([4.0])
                J['y', 'x2'] = np.array([40])

        prob = Problem()
        prob.model = MyComp()

        prob.set_solver_print(level=0)

        prob.setup(check=False)
        prob.run_model()

        stream = cStringIO()
        data = prob.check_partials(out_stream=stream, suppress_output=True)

        subheads = data[''][('y', 'x1')]
        self.assertTrue('J_fwd' in subheads)
        self.assertTrue('rel error' in subheads)
        self.assertTrue('abs error' in subheads)
        self.assertTrue('magnitude' in subheads)

        lines = stream.getvalue().splitlines()
        self.assertEqual(len(lines), 0)

    def test_missing_entry(self):
        class MyComp(ExplicitComponent):
            def setup(self):
                self.add_input('x1', 3.0)
                self.add_input('x2', 5.0)

                self.add_output('y', 5.5)

                self.declare_partials(of='*', wrt='*')

            def compute(self, inputs, outputs):
                """ Doesn't do much. """
                outputs['y'] = 3.0*inputs['x1'] + 4.0*inputs['x2']

            def compute_partials(self, inputs, partials):
                """Intentionally left out derivative."""
                J = partials
                J['y', 'x1'] = np.array([3.0])

        prob = Problem()
        prob.model = Group()
        prob.model.add_subsystem('p1', IndepVarComp('x1', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('x2', 5.0))
        prob.model.add_subsystem('comp', MyComp())

        prob.model.connect('p1.x1', 'comp.x1')
        prob.model.connect('p2.x2', 'comp.x2')

        prob.set_solver_print(level=0)

        prob.setup(check=False)
        prob.run_model()

        data = prob.check_partials(suppress_output=True)

        abs_error = data['comp']['y', 'x1']['abs error']
        rel_error = data['comp']['y', 'x1']['rel error']
        self.assertAlmostEqual(abs_error.forward, 0.)
        self.assertAlmostEqual(abs_error.reverse, 0.)
        self.assertAlmostEqual(rel_error.forward, 0.)
        self.assertAlmostEqual(rel_error.reverse, 0.)
        self.assertAlmostEqual(np.linalg.norm(data['comp']['y', 'x1']['J_fd'] - 3.), 0.,
                               delta=1e-6)

        abs_error = data['comp']['y', 'x2']['abs error']
        rel_error = data['comp']['y', 'x2']['rel error']
        self.assertAlmostEqual(abs_error.forward, 4.)
        self.assertAlmostEqual(abs_error.reverse, 4.)
        self.assertAlmostEqual(rel_error.forward, 1.)
        self.assertAlmostEqual(rel_error.reverse, 1.)
        self.assertAlmostEqual(np.linalg.norm(data['comp']['y', 'x2']['J_fd'] - 4.), 0.,
                               delta=1e-6)

    def test_nested_fd_units(self):
        class UnitCompBase(ExplicitComponent):
            def setup(self):
                self.add_input('T', val=284., units="degR", desc="Temperature")
                self.add_input('P', val=1., units='lbf/inch**2', desc="Pressure")

                self.add_output('flow:T', val=284., units="degR", desc="Temperature")
                self.add_output('flow:P', val=1., units='lbf/inch**2', desc="Pressure")

                # Finite difference everything
                self.declare_partials(of='*', wrt='*', method='fd')

            def compute(self, inputs, outputs):
                outputs['flow:T'] = inputs['T']
                outputs['flow:P'] = inputs['P']

        p = Problem()
        model = p.model = Group()
        indep = model.add_subsystem('indep', IndepVarComp(), promotes=['*'])

        indep.add_output('T', val=100., units='degK')
        indep.add_output('P', val=1., units='bar')

        units = model.add_subsystem('units', UnitCompBase(), promotes=['*'])

        p.setup()
        data = p.check_partials(suppress_output=True)

        for comp_name, comp in iteritems(data):
            for partial_name, partial in iteritems(comp):
                forward = partial['J_fwd']
                reverse = partial['J_rev']
                fd = partial['J_fd']
                self.assertAlmostEqual(np.linalg.norm(forward - reverse), 0.)
                self.assertAlmostEqual(np.linalg.norm(forward - fd), 0., delta=1e-6)

    def test_units(self):
        class UnitCompBase(ExplicitComponent):
            def setup(self):
                self.add_input('T', val=284., units="degR", desc="Temperature")
                self.add_input('P', val=1., units='lbf/inch**2', desc="Pressure")

                self.add_output('flow:T', val=284., units="degR", desc="Temperature")
                self.add_output('flow:P', val=1., units='lbf/inch**2', desc="Pressure")

                self.run_count = 0

                self.declare_partials(of='*', wrt='*')

            def compute_partials(self, inputs, partials):
                partials['flow:T', 'T'] = 1.
                partials['flow:P', 'P'] = 1.

            def compute(self, inputs, outputs):
                outputs['flow:T'] = inputs['T']
                outputs['flow:P'] = inputs['P']

                self.run_count += 1

        p = Problem()
        model = p.model = Group()
        indep = model.add_subsystem('indep', IndepVarComp(), promotes=['*'])

        indep.add_output('T', val=100., units='degK')
        indep.add_output('P', val=1., units='bar')

        units = model.add_subsystem('units', UnitCompBase(), promotes=['*'])

        model.nonlinear_solver = NonlinearRunOnce()

        p.setup()
        data = p.check_partials(suppress_output=True)

        for comp_name, comp in iteritems(data):
            for partial_name, partial in iteritems(comp):
                abs_error = partial['abs error']
                self.assertAlmostEqual(abs_error.forward, 0.)
                self.assertAlmostEqual(abs_error.reverse, 0.)
                self.assertAlmostEqual(abs_error.forward_reverse, 0.)

        # Make sure we only FD this twice.
        # The count is 5 because in check_partials, there are two calls to apply_nonlinear
        # when compute the fwd and rev analytic derivatives, then one call to apply_nonlinear
        # to compute the reference point for FD, then two additional calls for the two inputs.
        self.assertEqual(units.run_count, 5)

    def test_scalar_val(self):
        class PassThrough(ExplicitComponent):
            """
            Helper component that is needed when variables must be passed
            directly from input to output
            """

            def __init__(self, i_var, o_var, val, units=None):
                super(PassThrough, self).__init__()
                self.i_var = i_var
                self.o_var = o_var
                self.units = units
                self.val = val

                if isinstance(val, (float, int)) or np.isscalar(val):
                    size = 1
                else:
                    size = np.prod(val.shape)

                self.size = size

            def setup(self):
                if self.units is None:
                    self.add_input(self.i_var, self.val)
                    self.add_output(self.o_var, self.val)
                else:
                    self.add_input(self.i_var, self.val, units=self.units)
                    self.add_output(self.o_var, self.val, units=self.units)

                row_col = np.arange(self.size)
                self.declare_partials(of=self.o_var, wrt=self.i_var,
                                      val=1, rows=row_col, cols=row_col)

            def compute(self, inputs, outputs):
                outputs[self.o_var] = inputs[self.i_var]

            def linearize(self, inputs, outputs, J):
                pass

        p = Problem()

        indeps = p.model.add_subsystem('indeps', IndepVarComp(), promotes=['*'])
        indeps.add_output('foo', val=np.ones(4))
        indeps.add_output('foo2', val=np.ones(4))

        p.model.add_subsystem('pt', PassThrough("foo", "bar", val=np.ones(4)), promotes=['*'])
        p.model.add_subsystem('pt2', PassThrough("foo2", "bar2", val=np.ones(4)), promotes=['*'])

        p.set_solver_print(level=0)

        p.setup()
        p.run_model()

        data = p.check_partials(suppress_output=True)
        identity = np.eye(4)
        assert_rel_error(self, data['pt'][('bar', 'foo')]['J_fwd'], identity, 1e-15)
        assert_rel_error(self, data['pt'][('bar', 'foo')]['J_rev'], identity, 1e-15)
        assert_rel_error(self, data['pt'][('bar', 'foo')]['J_fd'], identity, 1e-9)

        assert_rel_error(self, data['pt2'][('bar2', 'foo2')]['J_fwd'], identity, 1e-15)
        assert_rel_error(self, data['pt2'][('bar2', 'foo2')]['J_rev'], identity, 1e-15)
        assert_rel_error(self, data['pt2'][('bar2', 'foo2')]['J_fd'], identity, 1e-9)

    def test_matrix_free_explicit(self):
        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        prob.model.add_subsystem('comp', ParaboloidMatVec())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')

        prob.set_solver_print(level=0)

        prob.setup(check=False)
        prob.run_model()

        data = prob.check_partials(suppress_output=True)

        for comp_name, comp in iteritems(data):
            for partial_name, partial in iteritems(comp):
                abs_error = partial['abs error']
                rel_error = partial['rel error']
                assert_rel_error(self, abs_error.forward, 0., 1e-5)
                assert_rel_error(self, abs_error.reverse, 0., 1e-5)
                assert_rel_error(self, abs_error.forward_reverse, 0., 1e-5)
                assert_rel_error(self, rel_error.forward, 0., 1e-5)
                assert_rel_error(self, rel_error.reverse, 0., 1e-5)
                assert_rel_error(self, rel_error.forward_reverse, 0., 1e-5)

        assert_rel_error(self, data['comp'][('f_xy', 'x')]['J_fwd'][0][0], 5.0, 1e-6)
        assert_rel_error(self, data['comp'][('f_xy', 'x')]['J_rev'][0][0], 5.0, 1e-6)
        assert_rel_error(self, data['comp'][('f_xy', 'y')]['J_fwd'][0][0], 21.0, 1e-6)
        assert_rel_error(self, data['comp'][('f_xy', 'y')]['J_rev'][0][0], 21.0, 1e-6)

    def test_matrix_free_implicit(self):
        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('rhs', np.ones((2, ))))
        prob.model.add_subsystem('comp', TestImplCompArrayMatVec())

        prob.model.connect('p1.rhs', 'comp.rhs')

        prob.set_solver_print(level=0)

        prob.setup(check=False)
        prob.run_model()

        data = prob.check_partials(suppress_output=True)

        for comp_name, comp in iteritems(data):
            for partial_name, partial in iteritems(comp):
                abs_error = partial['abs error']
                rel_error = partial['rel error']
                assert_rel_error(self, abs_error.forward, 0., 1e-5)
                assert_rel_error(self, abs_error.reverse, 0., 1e-5)
                assert_rel_error(self, abs_error.forward_reverse, 0., 1e-5)
                assert_rel_error(self, rel_error.forward, 0., 1e-5)
                assert_rel_error(self, rel_error.reverse, 0., 1e-5)
                assert_rel_error(self, rel_error.forward_reverse, 0., 1e-5)

    def test_implicit_undeclared(self):
        # Test to see that check_partials works when state_wrt_input and state_wrt_state
        # partials are missing.

        class ImplComp4Test(ImplicitComponent):

            def setup(self):
                self.add_input('x', np.ones(2))
                self.add_input('dummy', np.ones(2))
                self.add_output('y', np.ones(2))
                self.add_output('extra', np.ones(2))
                self.mtx = np.array([
                    [3., 4.],
                    [2., 3.],
                ])

                self.declare_partials(of='*', wrt='*')

            def apply_nonlinear(self, inputs, outputs, residuals):
                residuals['y'] = self.mtx.dot(outputs['y']) - inputs['x']

            def linearize(self, inputs, outputs, partials):
                partials['y', 'x'] = -np.eye(2)
                partials['y', 'y'] = self.mtx

        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', np.ones((2, ))))
        prob.model.add_subsystem('p2', IndepVarComp('dummy', np.ones((2, ))))
        prob.model.add_subsystem('comp', ImplComp4Test())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.dummy', 'comp.dummy')

        prob.set_solver_print(level=0)

        prob.setup(check=False)
        prob.run_model()

        data = prob.check_partials(suppress_output=True)

        assert_rel_error(self, data['comp']['y', 'extra']['J_fwd'], np.zeros((2, 2)))
        assert_rel_error(self, data['comp']['y', 'extra']['J_rev'], np.zeros((2, 2)))
        assert_rel_error(self, data['comp']['y', 'dummy']['J_fwd'], np.zeros((2, 2)))
        assert_rel_error(self, data['comp']['y', 'dummy']['J_rev'], np.zeros((2, 2)))

    def test_dependent_false_hide(self):
        # Test that we omit derivs declared with dependent=False

        class SimpleComp1(ExplicitComponent):
            def setup(self):
                self.add_input('z', shape=(2, 2))
                self.add_input('x', shape=(2, 2))
                self.add_output('g', shape=(2, 2))

                self.declare_partials(of='g', wrt='x')
                self.declare_partials(of='g', wrt='z', dependent=False)

            def compute(self, inputs, outputs):
                outputs['g'] = 3.0*inputs['x']

            def compute_partials(self, inputs, partials):
                partials['g', 'x'] = 3.


        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('z', np.ones((2, 2))))
        prob.model.add_subsystem('p2', IndepVarComp('x', np.ones((2, 2))))
        prob.model.add_subsystem('comp', SimpleComp1())
        prob.model.connect('p1.z', 'comp.z')
        prob.model.connect('p2.x', 'comp.x')

        prob.setup(check=False)

        stream = cStringIO()
        data = prob.check_partials(out_stream=stream)
        lines = stream.getvalue().splitlines()

        self.assertTrue("  comp: 'g' wrt 'z'" not in lines)
        self.assertTrue(('g', 'z') not in data['comp'])
        self.assertTrue("  comp: 'g' wrt 'x'"  in lines)
        self.assertTrue(('g', 'x') in data['comp'])

    def test_dependent_false_show(self):
        # Test that we show derivs declared with dependent=False if the fd is not
        # ~zero.

        class SimpleComp2(ExplicitComponent):
            def setup(self):
                self.add_input('z', shape=(2, 2))
                self.add_input('x', shape=(2, 2))
                self.add_output('g', shape=(2, 2))

                self.declare_partials(of='g', wrt='x')
                self.declare_partials('g', 'z', dependent=False)

            def compute(self, inputs, outputs):
                outputs['g'] = 2.0*inputs['z'] + 3.0*inputs['x']

            def compute_partials(self, inputs, partials):
                partials['g', 'x'] = 3.


        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('z', np.ones((2, 2))))
        prob.model.add_subsystem('p2', IndepVarComp('x', np.ones((2, 2))))
        prob.model.add_subsystem('comp', SimpleComp2())
        prob.model.connect('p1.z', 'comp.z')
        prob.model.connect('p2.x', 'comp.x')

        prob.setup(check=False)

        stream = cStringIO()
        data = prob.check_partials(out_stream=stream)
        lines = stream.getvalue().splitlines()

        self.assertTrue("  comp: 'g' wrt 'z'" in lines)
        self.assertTrue(('g', 'z') in data['comp'])
        self.assertTrue("  comp: 'g' wrt 'x'"  in lines)
        self.assertTrue(('g', 'x') in data['comp'])

    def test_set_step_on_comp(self):
        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        comp = prob.model.add_subsystem('comp', ParaboloidTricky())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')

        prob.set_solver_print(level=0)

        comp.set_check_partial_options(wrt='*', step=1e-2)

        prob.setup(check=False)
        prob.run_model()

        data = prob.check_partials(suppress_output=True)

        # This will fail unless you set the check_step.
        x_error = data['comp']['f_xy', 'x']['rel error']
        self.assertLess(x_error.forward, 1e-5)
        self.assertLess(x_error.reverse, 1e-5)

    def test_set_step_global(self):
        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        comp = prob.model.add_subsystem('comp', ParaboloidTricky())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')

        prob.set_solver_print(level=0)

        prob.setup(check=False)
        prob.run_model()

        data = prob.check_partials(suppress_output=True, step=1e-2)

        # This will fail unless you set the global step.
        x_error = data['comp']['f_xy', 'x']['rel error']
        self.assertLess(x_error.forward, 1e-5)
        self.assertLess(x_error.reverse, 1e-5)

    def test_complex_step_not_allocated(self):
        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        comp = prob.model.add_subsystem('comp', ParaboloidTricky())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')

        prob.set_solver_print(level=0)

        comp.set_check_partial_options(wrt='*', method='cs')

        prob.setup(check=False)
        prob.run_model()

        with self.assertRaises(RuntimeError) as context:
            data = prob.check_partials(suppress_output=True)

        msg = 'In order to check partials with complex step, you need to set ' + \
            '"force_alloc_complex" to True during setup.'
        self.assertEqual(str(context.exception), msg)

    def test_set_method_on_comp(self):
        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        comp = prob.model.add_subsystem('comp', ParaboloidTricky())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')

        prob.set_solver_print(level=0)

        comp.set_check_partial_options(wrt='*', method='cs')

        prob.setup(check=False, force_alloc_complex=True)
        prob.run_model()

        data = prob.check_partials(suppress_output=True)

        x_error = data['comp']['f_xy', 'x']['rel error']
        self.assertLess(x_error.forward, 1e-5)
        self.assertLess(x_error.reverse, 1e-5)

    def test_set_method_global(self):
        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        comp = prob.model.add_subsystem('comp', ParaboloidTricky())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')

        prob.set_solver_print(level=0)

        prob.setup(check=False, force_alloc_complex=True)
        prob.run_model()

        data = prob.check_partials(suppress_output=True, method='cs')

        x_error = data['comp']['f_xy', 'x']['rel error']
        self.assertLess(x_error.forward, 1e-5)
        self.assertLess(x_error.reverse, 1e-5)

    def test_set_form_on_comp(self):
        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        comp = prob.model.add_subsystem('comp', ParaboloidTricky())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')

        prob.set_solver_print(level=0)

        comp.set_check_partial_options(wrt='*', form='central')

        prob.setup(check=False)
        prob.run_model()

        data = prob.check_partials(suppress_output=True)

        # This will fail unless you set the check_step.
        x_error = data['comp']['f_xy', 'x']['rel error']
        self.assertLess(x_error.forward, 1e-3)
        self.assertLess(x_error.reverse, 1e-3)

    def test_set_form_global(self):
        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        comp = prob.model.add_subsystem('comp', ParaboloidTricky())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')

        prob.set_solver_print(level=0)

        prob.setup(check=False)
        prob.run_model()

        data = prob.check_partials(suppress_output=True, form='central')

        # This will fail unless you set the check_step.
        x_error = data['comp']['f_xy', 'x']['rel error']
        self.assertLess(x_error.forward, 1e-3)
        self.assertLess(x_error.reverse, 1e-3)

    def test_set_step_calc_on_comp(self):
        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        comp = prob.model.add_subsystem('comp', ParaboloidTricky())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')

        prob.set_solver_print(level=0)

        comp.set_check_partial_options(wrt='*', step_calc='rel')

        prob.setup(check=False)
        prob.run_model()

        data = prob.check_partials(suppress_output=True)

        # This will fail unless you set the check_step.
        x_error = data['comp']['f_xy', 'x']['rel error']
        self.assertLess(x_error.forward, 3e-3)
        self.assertLess(x_error.reverse, 3e-3)

    def test_set_step_calc_global(self):
        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        comp = prob.model.add_subsystem('comp', ParaboloidTricky())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')

        prob.set_solver_print(level=0)

        prob.setup(check=False)
        prob.run_model()

        data = prob.check_partials(suppress_output=True, step_calc='rel')

        # This will fail unless you set the global step.
        x_error = data['comp']['f_xy', 'x']['rel error']
        self.assertLess(x_error.forward, 3e-3)
        self.assertLess(x_error.reverse, 3e-3)

    def test_set_check_option_precedence(self):
        # Test that we omit derivs declared with dependent=False

        class SimpleComp1(ExplicitComponent):
            def setup(self):
                self.add_input('ab', 13.0)
                self.add_input('aba', 13.0)
                self.add_input('ba', 13.0)
                self.add_output('y', 13.0)

                self.declare_partials(of='*', wrt='*')

            def compute(self, inputs, outputs):
                ab = inputs['ab']
                aba = inputs['aba']
                ba = inputs['ba']

                outputs['y'] = ab**3 + aba**3 + ba**3

            def compute_partials(self, inputs, partials):
                ab = inputs['ab']
                aba = inputs['aba']
                ba = inputs['ba']

                partials['y', 'ab'] = 3.0*ab**2
                partials['y', 'aba'] = 3.0*aba**2
                partials['y', 'ba'] = 3.0*ba**2


        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('ab', 13.0))
        prob.model.add_subsystem('p2', IndepVarComp('aba', 13.0))
        prob.model.add_subsystem('p3', IndepVarComp('ba', 13.0))
        comp = prob.model.add_subsystem('comp', SimpleComp1())

        prob.model.connect('p1.ab', 'comp.ab')
        prob.model.connect('p2.aba', 'comp.aba')
        prob.model.connect('p3.ba', 'comp.ba')

        prob.setup(check=False)

        comp.set_check_partial_options(wrt='a*', step=1e-2)
        comp.set_check_partial_options(wrt='*a', step=1e-4)

        prob.run_model()

        data = prob.check_partials(suppress_output=True)

        # Note 'aba' gets the better value from the second options call with the *a wildcard.
        assert_rel_error(self, data['comp']['y', 'ab']['J_fd'][0][0], 507.3901, 1e-4)
        assert_rel_error(self, data['comp']['y', 'aba']['J_fd'][0][0], 507.0039, 1e-4)
        assert_rel_error(self, data['comp']['y', 'ba']['J_fd'][0][0], 507.0039, 1e-4)

    def test_option_printing(self):
        # Make sure we print the approximation type for each variable.
        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        comp = prob.model.add_subsystem('comp', ParaboloidTricky())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')

        prob.set_solver_print(level=0)

        comp.set_check_partial_options(wrt='x', method='cs')
        comp.set_check_partial_options(wrt='y', form='central')

        prob.setup(check=False, force_alloc_complex=True)
        prob.run_model()

        stream = cStringIO()
        prob.check_partials()
        totals = prob.check_partials(out_stream=stream)

        lines = stream.getvalue().splitlines()
        print(lines)
        self.assertTrue('cs' in lines[5], msg='Did you change the format for printing check derivs?')
        self.assertTrue('fd' in lines[19], msg='Did you change the format for printing check derivs?')

    def test_compact_print_formatting(self):
        class MyCompShortVarNames(ExplicitComponent):
            def setup(self):
                self.add_input('x1', 3.0)
                self.add_input('x2', 5.0)
                self.add_output('y', 5.5)
                self.declare_partials(of='*', wrt='*')

            def compute(self, inputs, outputs):
                """ Doesn't do much. """
                outputs['y'] = 3.0*inputs['x1'] + 4.0*inputs['x2']

            def compute_partials(self, inputs, partials):
                """Intentionally incorrect derivative."""
                J = partials
                J['y', 'x1'] = np.array([4.0])
                J['y', 'x2'] = np.array([40])

        class MyCompLongVarNames(ExplicitComponent):
            def setup(self):
                self.add_input('really_long_variable_name_x1', 3.0)
                self.add_input('x2', 5.0)
                self.add_output('really_long_variable_name_y', 5.5)
                self.declare_partials(of='*', wrt='*')

            def compute(self, inputs, outputs):
                """ Doesn't do much. """
                outputs['really_long_variable_name_y'] = 3.0*inputs['really_long_variable_name_x1'] + 4.0*inputs['x2']

            def compute_partials(self, inputs, partials):
                """Intentionally incorrect derivative."""
                J = partials
                J['really_long_variable_name_y', 'really_long_variable_name_x1'] = np.array([4.0])
                J['really_long_variable_name_y', 'x2'] = np.array([40])

        # First short var names
        prob = Problem()
        prob.model = Group()
        prob.model.add_subsystem('p1', IndepVarComp('x1', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('x2', 5.0))
        prob.model.add_subsystem('comp', MyCompShortVarNames())
        prob.model.connect('p1.x1', 'comp.x1')
        prob.model.connect('p2.x2', 'comp.x2')
        prob.set_solver_print(level=0)
        prob.setup(check=False)
        prob.run_model()
        stream = cStringIO()
        prob.check_partials(out_stream=stream, compact_print=True)
        lines = stream.getvalue().splitlines()
        # Check to make sure all the header and value lines have their columns lined up
        header_locations_of_bars = None
        sep = '|'
        for line in lines:
            if sep in line:
                if header_locations_of_bars:
                    value_locations_of_bars = [i for i, ltr in enumerate(line) if ltr == sep]
                    self.assertEqual(value_locations_of_bars, header_locations_of_bars,
                                     msg="Column separators should all be aligned")
                else:
                    header_locations_of_bars = [i for i, ltr in enumerate(line) if ltr == sep]

        # Then long var names
        prob = Problem()
        prob.model = Group()
        prob.model.add_subsystem('p1', IndepVarComp('really_long_variable_name_x1', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('x2', 5.0))
        prob.model.add_subsystem('comp', MyCompLongVarNames())
        prob.model.connect('p1.really_long_variable_name_x1', 'comp.really_long_variable_name_x1')
        prob.model.connect('p2.x2', 'comp.x2')
        prob.set_solver_print(level=0)
        prob.setup(check=False)
        prob.run_model()
        stream = cStringIO()
        prob.check_partials(out_stream=stream, compact_print=True)
        lines = stream.getvalue().splitlines()
        # Check to make sure all the header and value lines have their columns lined up
        header_locations_of_bars = None
        sep = '|'
        for line in lines:
            if sep in line:
                if header_locations_of_bars:
                    value_locations_of_bars = [i for i, ltr in enumerate(line) if ltr == sep]
                    self.assertEqual(value_locations_of_bars, header_locations_of_bars,
                                     msg="Column separators should all be aligned")
                else:
                    header_locations_of_bars = [i for i, ltr in enumerate(line) if ltr == sep]

    def test_compact_print_exceed_tol(self):
        class MyCompGoodPartials(ExplicitComponent):
            def setup(self):
                self.add_input('x1', 3.0)
                self.add_input('x2', 5.0)
                self.add_output('y', 5.5)
                self.declare_partials(of='*', wrt='*')

            def compute(self, inputs, outputs):
                """ Doesn't do much. """
                outputs['y'] = 3.0 * inputs['x1'] + 4.0 * inputs['x2']

            def compute_partials(self, inputs,     partials):
                """Correct derivative."""
                J = partials
                J['y', 'x1'] = np.array([3.0])
                J['y', 'x2'] = np.array([4.0])

        class MyCompBadPartials(MyCompGoodPartials):
            def compute_partials(self, inputs, partials):
                """Intentionally incorrect derivative."""
                J = partials
                J['y', 'x1'] = np.array([4.0])
                J['y', 'x2'] = np.array([40])


        prob = Problem()
        prob.model = MyCompGoodPartials()
        prob.set_solver_print(level=0)
        prob.setup(check=False)
        prob.run_model()
        stream = cStringIO()
        prob.check_partials(out_stream=stream, compact_print=True)
        self.assertEqual(stream.getvalue().count('>ABS_TOL'),0)
        self.assertEqual(stream.getvalue().count('>REL_TOL'),0)

        prob = Problem()
        prob.model = MyCompBadPartials()
        prob.set_solver_print(level=0)
        prob.setup(check=False)
        prob.run_model()
        stream = cStringIO()
        prob.check_partials(out_stream=stream, compact_print=True)
        self.assertEqual(stream.getvalue().count('>ABS_TOL'),2)
        self.assertEqual(stream.getvalue().count('>REL_TOL'),2)

    def test_check_partials_compute_rev(self):

        # 1: Implicit comp
        from openmdao.core.tests.test_impl_comp import QuadraticLinearize, QuadraticJacVec
        group = Group()

        comp1 = group.add_subsystem('comp1', IndepVarComp())
        comp1.add_output('a', 1.0)
        comp1.add_output('b', -4.0)
        comp1.add_output('c', 3.0)

        group.add_subsystem('comp2', QuadraticLinearize())
        group.add_subsystem('comp3', QuadraticJacVec())

        group.connect('comp1.a', 'comp2.a')
        group.connect('comp1.b', 'comp2.b')
        group.connect('comp1.c', 'comp2.c')

        group.connect('comp1.a', 'comp3.a')
        group.connect('comp1.b', 'comp3.b')
        group.connect('comp1.c', 'comp3.c')

        prob = Problem(model=group)
        prob.setup(check=False)
        stream = cStringIO()
        prob.check_partials(out_stream=stream, compact_print=True)
        self.assertEqual(stream.getvalue().count('n/a'),20)
        self.assertEqual(stream.getvalue().count('rev'),10)
        self.assertEqual(stream.getvalue().count('Component'),2)
        self.assertEqual(stream.getvalue().count('wrt'),10)

        print(stream.getvalue())
        # So for this case, they do all provide them, so rev should not be shown
        # self.assertEqual(stream.getvalue().count('Reverse'),0)
        # self.assertEqual(stream.getvalue().count('Jrev'),0)

        stream = cStringIO()
        prob.check_partials(out_stream=stream, compact_print=False)
        print(stream.getvalue())



        print('aaaaaaaaa')

        class MyComp(ExplicitComponent):
            def setup(self):
                self.add_input('x1', 3.0)
                self.add_input('x2', 5.0)
                self.add_output('z', 5.5)
                self.declare_partials(of='*', wrt='*')

            def compute(self, inputs, outputs):
                """ Doesn't do much. """
                outputs['z'] = 3.0 * inputs['x1'] + -4444.0 * inputs['x2']

            def compute_partials(self, inputs, partials):
                """Correct derivative."""
                J = partials
                J['z', 'x1'] = np.array([3.0])
                J['z', 'x2'] = np.array([-4444.0])

        # 1: All components define Jacobians
        prob = Problem()
        prob.model = MyComp()
        prob.set_solver_print(level=0)
        prob.setup(check=False)
        prob.run_model()
        stream = cStringIO()
        prob.check_partials(out_stream=stream, compact_print=True)
        print(stream.getvalue())
        self.assertEqual(stream.getvalue().count('rev'),0)

        stream = cStringIO()
        prob.check_partials(out_stream=stream, compact_print=False)
        print(stream.getvalue())
        # So for this case, they do all provide them, so rev should not be shown
        self.assertEqual(stream.getvalue().count('Forward Magnitude'),2)
        self.assertEqual(stream.getvalue().count('Reverse Magnitude'),0)
        self.assertEqual(stream.getvalue().count('Absolute Error'),2)
        self.assertEqual(stream.getvalue().count('Relative Error'),2)
        self.assertEqual(stream.getvalue().count('Raw Forward Derivative'),2)
        self.assertEqual(stream.getvalue().count('Raw Reverse Derivative'),0)
        self.assertEqual(stream.getvalue().count('Raw FD Derivative'),2)

        # check partials will only show fwd check when all components provide their jacobians
        # self.assertEqual(stream.getvalue().count('rev'),5)

        # # 2: All components define Jacobians but force it to display rev checks
        # prob = Problem()
        # prob.model = MyComp()
        # prob.set_solver_print(level=0)
        # prob.setup(check=False)
        # prob.run_model()
        # stream = cStringIO()
        # # prob.check_partials(out_stream=stream, compact_print=True, compute_rev=True)
        # prob.check_partials(out_stream=stream, compact_print=True)
        # # check partials will only show fwd check when all components provide their jacobians
        # # So for this case, they do all provide them, so rev should not be shown
        # self.assertEqual(stream.getvalue().count('rev'),5)

        # Need to also test for non-compact. Need to make sure it shows up !!!!!!!!!!!!!!

        # from openmdao.test_suite.components.paraboloid import Paraboloid
        # 3: Not all components define Jacobians because one defines compute_jacvec_product
        from openmdao.test_suite.components.paraboloid_mat_vec import ParaboloidMatVec
        prob = Problem()
        prob.model = Group()
        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        prob.model.add_subsystem('comp', ParaboloidMatVec())
        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')
        prob.set_solver_print(level=0)
        prob.setup(check=False)
        prob.run_model()
        stream = cStringIO()
        prob.check_partials(out_stream=stream, compact_print=True)
        self.assertEqual(stream.getvalue().count('rev'),5)
        print(stream.getvalue())

        stream = cStringIO()
        prob.check_partials(out_stream=stream, compact_print=False)
        print(stream.getvalue())
        self.assertEqual(stream.getvalue().count('Reverse'),4)
        self.assertEqual(stream.getvalue().count('Jrev'),8)


        # 4: Mixed comps. Some with jacobians. Some not
        from openmdao.test_suite.components.paraboloid_mat_vec import ParaboloidMatVec
        prob = Problem()
        prob.model = Group()
        prob.model.add_subsystem('c0', MyComp()) # in x1,x2, out is z
        # prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        prob.model.add_subsystem('comp', ParaboloidMatVec())
        # prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('c0.z', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')
        prob.set_solver_print(level=0)
        prob.setup(check=False)
        prob.run_model()

        stream = cStringIO()
        prob.check_partials(out_stream=stream, compact_print=True)
        self.assertEqual(stream.getvalue().count('n/a'),10)
        self.assertEqual(stream.getvalue().count('rev'),10)
        self.assertEqual(stream.getvalue().count('Component'),2)
        self.assertEqual(stream.getvalue().count('wrt'),6)
        print(stream.getvalue())

        stream = cStringIO()
        prob.check_partials(out_stream=stream, compact_print=False)
        print(stream.getvalue())
        self.assertEqual(stream.getvalue().count('Forward Magnitude'),4)
        self.assertEqual(stream.getvalue().count('Reverse Magnitude'),2)
        self.assertEqual(stream.getvalue().count('Absolute Error'),8)
        self.assertEqual(stream.getvalue().count('Relative Error'),8)
        self.assertEqual(stream.getvalue().count('Raw Forward Derivative'),4)
        self.assertEqual(stream.getvalue().count('Raw Reverse Derivative'),2)
        self.assertEqual(stream.getvalue().count('Raw FD Derivative'),4)

        # 4: Not all components define Jacobians because one defines compute_multi_jacvec_product
        class JacVec(ExplicitComponent):

            def __init__(self, size):
                super(JacVec, self).__init__()
                self.size = size

            def setup(self):
                size = self.size
                self.add_input('x', val=np.zeros(size))
                self.add_input('y', val=np.zeros(size))
                self.add_output('f_xy', val=np.zeros(size))

            def compute(self, inputs, outputs):
                outputs['f_xy'] = inputs['x'] * inputs['y']

            def compute_jacvec_product(self, inputs, d_inputs, d_outputs, mode):
                if mode == 'fwd':
                    if 'x' in d_inputs:
                        d_outputs['f_xy'] += d_inputs['x'] * inputs['y']
                    if 'y' in d_inputs:
                        d_outputs['f_xy'] += d_inputs['y'] * inputs['x']
                else:
                    d_fxy = d_outputs['f_xy']
                    if 'x' in d_inputs:
                        d_inputs['x'] += d_fxy * inputs['y']
                    if 'y' in d_inputs:
                        d_inputs['y'] += d_fxy * inputs['x']

        class MultiJacVec(JacVec):
            def compute_multi_jacvec_product(self, inputs, d_inputs, d_outputs, mode):
                # same as compute_jacvec_product in this case
                self.compute_jacvec_product(inputs, d_inputs, d_outputs, mode)

        size = 5
        vectorize = False
        p = Problem()
        model = p.model
        model.add_subsystem('px', IndepVarComp('x', val=(np.arange(5, dtype=float) + 1.) * 3.0))
        model.add_subsystem('py', IndepVarComp('y', val=(np.arange(5, dtype=float) + 1.) * 2.0))
        model.add_subsystem('comp', MultiJacVec(size))

        model.connect('px.x', 'comp.x')
        model.connect('py.y', 'comp.y')

        model.add_design_var('px.x', vectorize_derivs=vectorize)
        model.add_design_var('py.y', vectorize_derivs=vectorize)
        model.add_constraint('comp.f_xy', vectorize_derivs=vectorize)

        p.setup(check=False)
        p.run_model()
        stream = cStringIO()
        p.check_partials(out_stream=stream, compact_print=True)
        self.assertEqual(stream.getvalue().count('rev'),5)
        print(stream.getvalue())

class TestCheckPartialsFeature(unittest.TestCase):

    def test_feature_incorrect_jacobian(self):
        import numpy as np

        from openmdao.api import Group, ExplicitComponent, IndepVarComp, Problem

        class MyComp(ExplicitComponent):
            def setup(self):
                self.add_input('x1', 3.0)
                self.add_input('x2', 5.0)

                self.add_output('y', 5.5)

                self.declare_partials(of='*', wrt='*')

            def compute(self, inputs, outputs):
                """ Doesn't do much. """
                outputs['y'] = 3.0*inputs['x1'] + 4.0*inputs['x2']

            def compute_partials(self, inputs, partials):
                """Intentionally incorrect derivative."""
                J = partials
                J['y', 'x1'] = np.array([4.0])
                J['y', 'x2'] = np.array([40])

        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x1', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('x2', 5.0))
        prob.model.add_subsystem('comp', MyComp())

        prob.model.connect('p1.x1', 'comp.x1')
        prob.model.connect('p2.x2', 'comp.x2')

        prob.set_solver_print(level=0)

        prob.setup(check=False)
        prob.run_model()

        data = prob.check_partials()

        x1_error = data['comp']['y', 'x1']['abs error']

        assert_rel_error(self, x1_error.forward, 1., 1e-8)
        assert_rel_error(self, x1_error.reverse, 1., 1e-8)

        x2_error = data['comp']['y', 'x2']['rel error']

        assert_rel_error(self, x2_error.forward, 9., 1e-8)
        assert_rel_error(self, x2_error.reverse, 9., 1e-8)

    def test_feature_check_partials_suppress(self):
        import numpy as np

        from openmdao.api import Group, ExplicitComponent, IndepVarComp, Problem

        class MyComp(ExplicitComponent):
            def setup(self):
                self.add_input('x1', 3.0)
                self.add_input('x2', 5.0)

                self.add_output('y', 5.5)

                self.declare_partials(of='*', wrt='*')

            def compute(self, inputs, outputs):
                """ Doesn't do much. """
                outputs['y'] = 3.0*inputs['x1'] + 4.0*inputs['x2']

            def compute_partials(self, inputs, partials):
                """Intentionally incorrect derivative."""
                J = partials
                J['y', 'x1'] = np.array([4.0])
                J['y', 'x2'] = np.array([40])

        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x1', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('x2', 5.0))
        prob.model.add_subsystem('comp', MyComp())

        prob.model.connect('p1.x1', 'comp.x1')
        prob.model.connect('p2.x2', 'comp.x2')

        prob.set_solver_print(level=0)

        prob.setup(check=False)
        prob.run_model()

        data = prob.check_partials(suppress_output=True)
        print(data)

    def test_set_step_on_comp(self):
        from openmdao.api import Problem, Group, IndepVarComp
        from openmdao.core.tests.test_check_derivs import ParaboloidTricky
        from openmdao.test_suite.components.paraboloid_mat_vec import ParaboloidMatVec

        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        comp = prob.model.add_subsystem('comp', ParaboloidTricky())
        prob.model.add_subsystem('comp2', ParaboloidMatVec())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')
        prob.model.connect('comp.f_xy', 'comp2.x')

        prob.set_solver_print(level=0)

        comp.set_check_partial_options(wrt='*', step=1e-2)

        prob.setup()
        prob.run_model()

        prob.check_partials()

    def test_set_step_global(self):
        from openmdao.api import Problem, Group, IndepVarComp
        from openmdao.core.tests.test_check_derivs import ParaboloidTricky
        from openmdao.test_suite.components.paraboloid_mat_vec import ParaboloidMatVec

        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        comp = prob.model.add_subsystem('comp', ParaboloidTricky())
        prob.model.add_subsystem('comp2', ParaboloidMatVec())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')
        prob.model.connect('comp.f_xy', 'comp2.x')

        prob.set_solver_print(level=0)

        prob.setup()
        prob.run_model()

        prob.check_partials(step=1e-2)

    def test_set_method_on_comp(self):
        from openmdao.api import Problem, Group, IndepVarComp
        from openmdao.core.tests.test_check_derivs import ParaboloidTricky
        from openmdao.test_suite.components.paraboloid_mat_vec import ParaboloidMatVec

        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        comp = prob.model.add_subsystem('comp', ParaboloidTricky())
        prob.model.add_subsystem('comp2', ParaboloidMatVec())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')
        prob.model.connect('comp.f_xy', 'comp2.x')

        prob.set_solver_print(level=0)

        comp.set_check_partial_options(wrt='*', method='cs')

        prob.setup(force_alloc_complex=True)
        prob.run_model()

        prob.check_partials()

    def test_set_method_global(self):
        from openmdao.api import Problem, Group, IndepVarComp
        from openmdao.core.tests.test_check_derivs import ParaboloidTricky
        from openmdao.test_suite.components.paraboloid_mat_vec import ParaboloidMatVec

        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        comp = prob.model.add_subsystem('comp', ParaboloidTricky())
        prob.model.add_subsystem('comp2', ParaboloidMatVec())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')
        prob.model.connect('comp.f_xy', 'comp2.x')

        prob.set_solver_print(level=0)

        prob.setup(force_alloc_complex=True)
        prob.run_model()

        prob.check_partials(method='cs')

    def test_set_form_on_comp(self):
        from openmdao.api import Problem, Group, IndepVarComp
        from openmdao.core.tests.test_check_derivs import ParaboloidTricky
        from openmdao.test_suite.components.paraboloid_mat_vec import ParaboloidMatVec

        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        comp = prob.model.add_subsystem('comp', ParaboloidTricky())
        prob.model.add_subsystem('comp2', ParaboloidMatVec())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')
        prob.model.connect('comp.f_xy', 'comp2.x')

        prob.set_solver_print(level=0)

        comp.set_check_partial_options(wrt='*', form='central')

        prob.setup()
        prob.run_model()

        prob.check_partials()

    def test_set_form_global(self):
        from openmdao.api import Problem, Group, IndepVarComp
        from openmdao.core.tests.test_check_derivs import ParaboloidTricky
        from openmdao.test_suite.components.paraboloid_mat_vec import ParaboloidMatVec

        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        comp = prob.model.add_subsystem('comp', ParaboloidTricky())
        prob.model.add_subsystem('comp2', ParaboloidMatVec())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')
        prob.model.connect('comp.f_xy', 'comp2.x')

        prob.set_solver_print(level=0)

        prob.setup()
        prob.run_model()

        prob.check_partials(form='central')

    def test_set_step_calc_on_comp(self):
        from openmdao.api import Problem, Group, IndepVarComp
        from openmdao.core.tests.test_check_derivs import ParaboloidTricky
        from openmdao.test_suite.components.paraboloid_mat_vec import ParaboloidMatVec

        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        comp = prob.model.add_subsystem('comp', ParaboloidTricky())
        prob.model.add_subsystem('comp2', ParaboloidMatVec())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')
        prob.model.connect('comp.f_xy', 'comp2.x')

        prob.set_solver_print(level=0)

        comp.set_check_partial_options(wrt='*', step_calc='rel')

        prob.setup()
        prob.run_model()

        prob.check_partials()

    def test_set_step_calc_global(self):
        from openmdao.api import Problem, Group, IndepVarComp
        from openmdao.core.tests.test_check_derivs import ParaboloidTricky

        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        comp = prob.model.add_subsystem('comp', ParaboloidTricky())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')

        prob.set_solver_print(level=0)

        prob.setup()
        prob.run_model()

        prob.check_partials(step_calc='rel')

    def test_feature_compact_print_formatting(self):
        import numpy as np
        from openmdao.api import Group, ExplicitComponent, IndepVarComp, Problem

        class MyComp(ExplicitComponent):
            def setup(self):
                self.add_input('x1', 3.0)
                self.add_input('x2', 5.0)
                self.add_output('y', 5.5)
                self.declare_partials(of='*', wrt='*')

            def compute(self, inputs, outputs):
                """ Doesn't do much. """
                outputs['y'] = 3.0*inputs['x1'] + 4.0*inputs['x2']

            def compute_partials(self, inputs, partials):
                """Intentionally incorrect derivative."""
                J = partials
                J['y', 'x1'] = np.array([4.0])
                J['y', 'x2'] = np.array([40])

        prob = Problem()
        prob.model = Group()
        prob.model.add_subsystem('p1', IndepVarComp('x1', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('x2', 5.0))
        prob.model.add_subsystem('comp', MyComp())
        prob.model.connect('p1.x1', 'comp.x1')
        prob.model.connect('p2.x2', 'comp.x2')
        prob.set_solver_print(level=0)
        prob.setup(check=False)
        prob.run_model()
        prob.check_partials(compact_print=True)


    def test_feature_compact_print_formatting(self):
        from openmdao.api import Problem, Group, IndepVarComp
        from openmdao.core.tests.test_check_derivs import ParaboloidTricky
        from openmdao.test_suite.components.paraboloid_mat_vec import ParaboloidMatVec

        prob = Problem()
        prob.model = Group()

        prob.model.add_subsystem('p1', IndepVarComp('x', 3.0))
        prob.model.add_subsystem('p2', IndepVarComp('y', 5.0))
        comp = prob.model.add_subsystem('comp', ParaboloidTricky())
        prob.model.add_subsystem('comp2', ParaboloidMatVec())

        prob.model.connect('p1.x', 'comp.x')
        prob.model.connect('p2.y', 'comp.y')
        prob.model.connect('comp.f_xy', 'comp2.x')

        prob.set_solver_print(level=0)

        comp.set_check_partial_options(wrt='*', step_calc='rel')

        prob.setup()
        prob.run_model()

        prob.check_partials(compact_print=True)


class TestProblemCheckTotals(unittest.TestCase):

    def test_cs(self):
        prob = Problem()
        prob.model = SellarDerivatives()
        prob.model.nonlinear_solver = NonlinearBlockGS()

        prob.model.add_design_var('x', lower=-100, upper=100)
        prob.model.add_design_var('z', lower=-100, upper=100)
        prob.model.add_objective('obj')
        prob.model.add_constraint('con1', upper=0.0)
        prob.model.add_constraint('con2', upper=0.0)

        prob.set_solver_print(level=0)

        prob.setup(force_alloc_complex=True)

        # We don't call run_driver() here because we don't
        # actually want the optimizer to run
        prob.run_model()

        # check derivatives with complex step and a larger step size.
        stream = cStringIO()
        totals = prob.check_totals(method='cs', step=1.0e-1, out_stream=stream)

        lines = stream.getvalue().splitlines()

        self.assertTrue('9.80614' in lines[4], "'9.80614' not found in '%s'" % lines[4])
        self.assertTrue('9.80614' in lines[5], "'9.80614' not found in '%s'" % lines[5])

        assert_rel_error(self, totals['con_cmp2.con2', 'px.x']['J_fwd'], [[0.09692762]], 1e-5)
        assert_rel_error(self, totals['con_cmp2.con2', 'px.x']['J_fd'], [[0.09692762]], 1e-5)

    def test_desvar_as_obj(self):
        prob = Problem()
        prob.model = SellarDerivatives()
        prob.model.nonlinear_solver = NonlinearBlockGS()

        prob.model.add_design_var('x', lower=-100, upper=100)
        prob.model.add_objective('x')

        prob.set_solver_print(level=0)

        prob.setup(force_alloc_complex=True)

        # We don't call run_driver() here because we don't
        # actually want the optimizer to run
        prob.run_model()

        # check derivatives with complex step and a larger step size.
        stream = cStringIO()
        totals = prob.check_totals(method='cs', step=1.0e-1, out_stream=stream)

        lines = stream.getvalue().splitlines()

        self.assertTrue('1.000' in lines[4])
        self.assertTrue('1.000' in lines[5])
        self.assertTrue('0.000' in lines[6])
        self.assertTrue('0.000' in lines[8])

        assert_rel_error(self, totals['px.x', 'px.x']['J_fwd'], [[1.0]], 1e-5)
        assert_rel_error(self, totals['px.x', 'px.x']['J_fd'], [[1.0]], 1e-5)

    def test_desvar_and_response_with_indices(self):

        class ArrayComp2D(ExplicitComponent):
            """
            A fairly simple array component.
            """

            def setup(self):

                self.JJ = np.array([[1.0, 3.0, -2.0, 7.0],
                                    [6.0, 2.5, 2.0, 4.0],
                                    [-1.0, 0.0, 8.0, 1.0],
                                    [1.0, 4.0, -5.0, 6.0]])

                # Params
                self.add_input('x1', np.zeros([4]))

                # Unknowns
                self.add_output('y1', np.zeros([4]))

                self.declare_partials(of='*', wrt='*')

            def compute(self, inputs, outputs):
                """
                Execution.
                """
                outputs['y1'] = self.JJ.dot(inputs['x1'])

            def compute_partials(self, inputs, partials):
                """
                Analytical derivatives.
                """
                partials[('y1', 'x1')] = self.JJ

        prob = Problem()
        prob.model = model = Group()
        model.add_subsystem('x_param1', IndepVarComp('x1', np.ones((4))),
                            promotes=['x1'])
        mycomp = model.add_subsystem('mycomp', ArrayComp2D(), promotes=['x1', 'y1'])

        model.add_design_var('x1', indices=[1, 3])
        model.add_constraint('y1', indices=[0, 2])

        prob.set_solver_print(level=0)

        prob.setup(check=False, mode='fwd')
        prob.run_model()

        Jbase = mycomp.JJ
        of = ['y1']
        wrt = ['x1']

        J = prob.compute_totals(of=of, wrt=wrt, return_format='flat_dict')
        assert_rel_error(self, J['y1', 'x1'][0][0], Jbase[0, 1], 1e-8)
        assert_rel_error(self, J['y1', 'x1'][0][1], Jbase[0, 3], 1e-8)
        assert_rel_error(self, J['y1', 'x1'][1][0], Jbase[2, 1], 1e-8)
        assert_rel_error(self, J['y1', 'x1'][1][1], Jbase[2, 3], 1e-8)

        totals = prob.check_totals()
        jac = totals[('mycomp.y1', 'x_param1.x1')]['J_fd']
        assert_rel_error(self, jac[0][0], Jbase[0, 1], 1e-8)
        assert_rel_error(self, jac[0][1], Jbase[0, 3], 1e-8)
        assert_rel_error(self, jac[1][0], Jbase[2, 1], 1e-8)
        assert_rel_error(self, jac[1][1], Jbase[2, 3], 1e-8)

        # Objective instead

        prob = Problem()
        prob.model = model = Group()
        model.add_subsystem('x_param1', IndepVarComp('x1', np.ones((4))),
                            promotes=['x1'])
        mycomp = model.add_subsystem('mycomp', ArrayComp2D(), promotes=['x1', 'y1'])

        model.add_design_var('x1', indices=[1, 3])
        model.add_objective('y1', index=1)

        prob.set_solver_print(level=0)

        prob.setup(check=False, mode='fwd')
        prob.run_model()

        Jbase = mycomp.JJ
        of = ['y1']
        wrt = ['x1']

        J = prob.compute_totals(of=of, wrt=wrt, return_format='flat_dict')
        assert_rel_error(self, J['y1', 'x1'][0][0], Jbase[1, 1], 1e-8)
        assert_rel_error(self, J['y1', 'x1'][0][1], Jbase[1, 3], 1e-8)

        totals = prob.check_totals()
        jac = totals[('mycomp.y1', 'x_param1.x1')]['J_fd']
        assert_rel_error(self, jac[0][0], Jbase[1, 1], 1e-8)
        assert_rel_error(self, jac[0][1], Jbase[1, 3], 1e-8)

    def test_cs_suppress(self):
        prob = Problem()
        prob.model = SellarDerivatives()
        prob.model.nonlinear_solver = NonlinearBlockGS()

        prob.model.add_design_var('x', lower=-100, upper=100)
        prob.model.add_design_var('z', lower=-100, upper=100)
        prob.model.add_objective('obj')
        prob.model.add_constraint('con1', upper=0.0)
        prob.model.add_constraint('con2', upper=0.0)

        prob.set_solver_print(level=0)

        prob.setup(force_alloc_complex=True)

        # We don't call run_driver() here because we don't
        # actually want the optimizer to run
        prob.run_model()

        # check derivatives with complex step and a larger step size.
        stream = cStringIO()
        totals = prob.check_totals(method='cs', step=1.0e-1, out_stream=stream,
                                   suppress_output=True)

        data = totals['con_cmp2.con2', 'px.x']
        self.assertTrue('J_fwd' in data)
        self.assertTrue('rel error' in data)
        self.assertTrue('abs error' in data)
        self.assertTrue('magnitude' in data)

        lines = stream.getvalue().splitlines()
        self.assertEqual(len(lines), 0)

    def test_two_desvar_as_con(self):
        prob = Problem()
        prob.model = SellarDerivatives()
        prob.model.nonlinear_solver = NonlinearBlockGS()

        prob.model.add_design_var('z', lower=-100, upper=100)
        prob.model.add_design_var('x', lower=-100, upper=100)
        prob.model.add_constraint('x', upper=0.0)
        prob.model.add_constraint('z', upper=0.0)

        prob.set_solver_print(level=0)

        prob.setup(check=False)

        # We don't call run_driver() here because we don't
        # actually want the optimizer to run
        prob.run_model()

        stream = cStringIO()
        totals = prob.check_totals(method='fd', step=1.0e-1, out_stream=stream)

        lines = stream.getvalue().splitlines()

        assert_rel_error(self, totals['px.x', 'px.x']['J_fwd'], [[1.0]], 1e-5)
        assert_rel_error(self, totals['px.x', 'px.x']['J_fd'], [[1.0]], 1e-5)
        assert_rel_error(self, totals['pz.z', 'pz.z']['J_fwd'], np.eye(2), 1e-5)
        assert_rel_error(self, totals['pz.z', 'pz.z']['J_fd'], np.eye(2), 1e-5)
        assert_rel_error(self, totals['px.x', 'pz.z']['J_fwd'], [[0.0, 0.0]], 1e-5)
        assert_rel_error(self, totals['px.x', 'pz.z']['J_fd'], [[0.0, 0.0]], 1e-5)
        assert_rel_error(self, totals['pz.z', 'px.x']['J_fwd'], [[0.0], [0.0]], 1e-5)
        assert_rel_error(self, totals['pz.z', 'px.x']['J_fd'], [[0.0], [0.0]], 1e-5)

    def test_full_con_with_index_desvar(self):
        prob = Problem()
        prob.model = SellarDerivatives()
        prob.model.nonlinear_solver = NonlinearBlockGS()

        prob.model.add_design_var('z', lower=-100, upper=100, indices=[1])
        prob.model.add_constraint('z', upper=0.0)

        prob.set_solver_print(level=0)

        prob.setup(check=False)

        # We don't call run_driver() here because we don't
        # actually want the optimizer to run
        prob.run_model()

        stream = cStringIO()
        totals = prob.check_totals(method='fd', step=1.0e-1, out_stream=stream)

        lines = stream.getvalue().splitlines()

        assert_rel_error(self, totals['pz.z', 'pz.z']['J_fwd'], [[0.0], [1.0]], 1e-5)
        assert_rel_error(self, totals['pz.z', 'pz.z']['J_fd'], [[0.0], [1.0]], 1e-5)

    def test_full_desvar_with_index_con(self):
        prob = Problem()
        prob.model = SellarDerivatives()
        prob.model.nonlinear_solver = NonlinearBlockGS()

        prob.model.add_design_var('z', lower=-100, upper=100)
        prob.model.add_constraint('z', upper=0.0, indices=[1])

        prob.set_solver_print(level=0)

        prob.setup(check=False)

        # We don't call run_driver() here because we don't
        # actually want the optimizer to run
        prob.run_model()

        stream = cStringIO()
        totals = prob.check_totals(method='fd', step=1.0e-1, out_stream=stream)

        lines = stream.getvalue().splitlines()

        assert_rel_error(self, totals['pz.z', 'pz.z']['J_fwd'], [[0.0, 1.0]], 1e-5)
        assert_rel_error(self, totals['pz.z', 'pz.z']['J_fd'], [[0.0, 1.0]], 1e-5)

    def test_full_desvar_with_index_obj(self):
        prob = Problem()
        prob.model = SellarDerivatives()
        prob.model.nonlinear_solver = NonlinearBlockGS()

        prob.model.add_design_var('z', lower=-100, upper=100)
        prob.model.add_objective('z', index=1)

        prob.set_solver_print(level=0)

        prob.setup(check=False)

        # We don't call run_driver() here because we don't
        # actually want the optimizer to run
        prob.run_model()

        stream = cStringIO()
        totals = prob.check_totals(method='fd', step=1.0e-1, out_stream=stream)

        lines = stream.getvalue().splitlines()

        assert_rel_error(self, totals['pz.z', 'pz.z']['J_fwd'], [[0.0, 1.0]], 1e-5)
        assert_rel_error(self, totals['pz.z', 'pz.z']['J_fd'], [[0.0, 1.0]], 1e-5)


@unittest.skipIf(MPI and not PETScVector, "only run under MPI if we have PETSc.")
class TestProblemCheckTotalsMPI(unittest.TestCase):

    N_PROCS = 2

    def test_indepvarcomp_under_par_sys(self):

        prob = Problem()
        group = prob.model = FanInSubbedIDVC()

        prob.setup(vector_class=vector_class, check=False, mode='rev')
        prob.set_solver_print(level=0)
        prob.run_model()

        J = prob.check_totals(suppress_output=True)
        assert_rel_error(self, J['sum.y', 'sub.sub1.p1.x']['J_fwd'], [[2.0]], 1.0e-6)
        assert_rel_error(self, J['sum.y', 'sub.sub2.p2.x']['J_fwd'], [[4.0]], 1.0e-6)
        assert_rel_error(self, J['sum.y', 'sub.sub1.p1.x']['J_fd'], [[2.0]], 1.0e-6)
        assert_rel_error(self, J['sum.y', 'sub.sub2.p2.x']['J_fd'], [[4.0]], 1.0e-6)

if __name__ == "__main__":
    unittest.main()
