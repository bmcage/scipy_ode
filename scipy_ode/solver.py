from __future__ import division, print_function, absolute_import

from enum import Enum, IntEnum

import numpy as np
from scipy.interpolate import interp1d


class OdeSolver(object):
    """Abstract base class of ODE solvers

    This class defines the interface that an ODE solver class must satisfy.

    Parameters
    ----------
    state : self.OdeState
        The initial state of the system
    fun : callable, (t, y) -> ydot
        The ODE system
    t_crit : float
        The boundary of the ODE system.

    Attributes
    ----------
    n : int
        The number of states (i.e. the size of ``y``)
    t : float
        A convenience property that gets ``state.t``
    y : array, shape (n,)
        A convenience property that gets ``state.y``
    state : self.OdeState
        This object holds all the state of the solver that is needed to interpolate the solution. Integrators may keep
        this object from a sequence of steps and provide it to the ``spline`` function of the solver to obtain the
        solution at any time.
        # TODO: decide if the values between two states must only be defined by the adjacent states or can more distant
        # states affect the solution
    initialize : callable, static, ``(t0, t_final, y0, fun) -> (t0, t_final, y0, fun)``
        A convenience function for sanitizing initializer inputs.

    Inheritance
    -----------
    All ODE solvers should override the ``OdeState``
    static member class, must override ``step`` instance method, and and should ``spline`` instance
    method. Furthermore, ``__init__`` must have a particular signature and follow a particular initialization procedure.

    __init__ : ``(fun, y0, t0=0, t_crit=float('inf'), **options)``
        All end-user subclasses must be consistent with this signature. Abstract subclasses that act as base classes
        for other solvers may have whatever signature is appropriate. It is recommended that each initializer follow
        these steps in order to maximize code reuse.
            1. Call ``fun, y0, t0, t_crit = OdeSolver.initialize(fun, y0, t0, t_crit)``
               to perform standardization on those arguments.
            2. Call ``state = self.OdeState(t, y, ...)`` with whatever arguments are appropriate
               for the solver-specific ODE state class.
            3. Call ``super().__init__(fun, state, t_crit)``
            4. Perform any solver-specific initialization.
        Solvers should silently ignore any options that it doesn't understand.
        # TODO: do we want this to actually be silent
    """
    # Abstract attributes
    fun = NotImplemented
    t = NotImplemented
    y = NotImplemented
    n = NotImplemented
    t_crit = NotImplemented
    direction = NotImplemented
    status = NotImplemented

    def initialize(self, fun, y0, t0, t_crit):
        y0 = np.asarray(y0, dtype=float)  # TODO: give user control over dtype?

        if y0.ndim != 1:
            raise ValueError("`y0` must be 1-dimensional.")

        def fun_wrapped(t, y):
            # TODO: decide if passing args and kwargs should be supported f(self, t, y, *args, **kwargs)
            return np.asarray(fun(t, y))

        self.n = y0.size
        self.fun = fun_wrapped
        self.t_crit = t_crit
        if t_crit - t0 >= 0:
            self.direction = SolverDirection.forward
        else:
            self.direction = SolverDirection.reverse

        if t0 == t_crit:
            self.status = SolverStatus.finished
        else:
            self.status = SolverStatus.started

        return fun_wrapped, y0, t0, t_crit

    def assert_step_is_possible(self):
        if self.status != SolverStatus.running and self.status != SolverStatus.started:
            # Only take a step is the solver is running
            raise ValueError("Attempt to step on a failed or finished solver")

    def step(self):
        """Advance the solver by one step

        Mutates ``self`` by advancing the internal state by one step.

        This is an abstract method with no implementation in ``OdeSolver``. Concrete subclasses must implement this
        method. Implementations of ``step`` should first run `self.assert_step_is_possible()`.
        """
        raise NotImplementedError()

    def interpolator(self):
        """Construct an interpolator for the solution within the previous step

        Returns
        -------
        solution : callable, (t) -> y
            If provided with a scalar time, returns the state at that time. If provided with a list of
            times, returns a of list of states at the corresponding times.

        This is an abstract method with no implementation in ``OdeSolver``. Concrete subclasses
        must implement this method with an interpolator suited for the given solver.
        """
        raise NotImplementedError()


class SolverDirection(IntEnum):
    reverse = -1
    forward = 1


class SolverStatus(Enum):
    started = object()
    running = object()
    # TODO: add message to failure
    failed = object()
    finished = object()


class IntegrationException(Exception):
    def __init__(self, message, t, partial_solution):
        super().__init__("Integration failure at t = {}: {}".format(t, message))
        self.partial_solution = partial_solution
