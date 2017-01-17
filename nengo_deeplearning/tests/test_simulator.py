import pkg_resources

import nengo
from nengo.builder.signal import Signal
from nengo.builder.operator import ElementwiseInc, DotInc
from nengo.utils.testing import warns
import numpy as np

import nengo_deeplearning as nengo_dl

try:
    from nengo.builder.operator import PreserveValue
except:
    PreserveValue = None


def test_warn_on_opensim_del():
    with nengo.Network() as net:
        nengo.Ensemble(10, 1)

    sim = nengo_dl.Simulator(net)
    with warns(RuntimeWarning):
        sim.__del__()
    sim.close()


def test_args():
    class Fn(object):
        def __init__(self):
            self.last_x = None

        def __call__(self, t, x):
            assert isinstance(t, np.float32)
            assert t.shape == ()
            assert isinstance(x, np.ndarray)
            assert self.last_x is not x  # x should be a new copy on each call
            self.last_x = x
            assert x[0] == t

    with nengo.Network() as model:
        u = nengo.Node(lambda t: t)
        v = nengo.Node(Fn(), size_in=1, size_out=0)
        nengo.Connection(u, v, synapse=None)

    with nengo_dl.Simulator(model) as sim:
        sim.run(0.01)


def test_signal_init_values():
    """Tests that initial values are not overwritten."""

    zero = Signal([0.0])
    one = Signal([1.0])
    five = Signal([5.0])
    zeroarray = Signal([[0.0], [0.0], [0.0]])
    array = Signal([1.0, 2.0, 3.0])

    class DummyProbe():
        def __init__(self, target):
            self.target = target
            self.sample_every = None
            self.size_in = target.size

    m = nengo.builder.Model(dt=0)
    m.operators += [ElementwiseInc(zero, zero, five),
                    DotInc(zeroarray, one, array)]
    if PreserveValue is not None:
        m.operators += [PreserveValue(five), PreserveValue(array)]

    probes = [DummyProbe(zero), DummyProbe(one), DummyProbe(five),
              DummyProbe(array)]
    m.probes += probes
    for p in probes:
        m.sig[p]['in'] = p.target

    with nengo_dl.Simulator(None, model=m) as sim:
        sim.run_steps(3)
        assert np.allclose(sim.data[probes[0]], 0)
        assert np.allclose(sim.data[probes[1]], 1)
        assert np.allclose(sim.data[probes[2]], 5)
        assert np.allclose(sim.data[probes[3]], [1, 2, 3])


def test_entry_point():
    sims = [ep.load() for ep in
            pkg_resources.iter_entry_points(group='nengo.backends')]
    assert nengo_dl.Simulator in sims


def test_persistent_state():
    """Make sure that state is preserved between runs."""

    with nengo.Network(seed=0) as net:
        inp = nengo.Node([1])
        ens = nengo.Ensemble(1000, 1)
        nengo.Connection(inp, ens)
        p = nengo.Probe(ens)

    with nengo_dl.Simulator(net, step_blocks=5) as sim:
        sim.run_steps(100)
        data = sim.data[p]
        sim.reset()

        sim.run_steps(100)
        data2 = sim.data[p]
        sim.reset()

        for _ in range(20):
            sim.run_steps(5)
        data3 = sim.data[p]

    assert np.allclose(data, data2)
    assert np.allclose(data2, data3)


def test_step_blocks():
    with nengo.Network(seed=0) as net:
        inp = nengo.Node(np.sin)
        ens = nengo.Ensemble(10, 1)
        nengo.Connection(inp, ens)
        p = nengo.Probe(ens)

    sim1 = nengo_dl.Simulator(net, step_blocks=None)
    sim2 = nengo_dl.Simulator(net, step_blocks=10)

    sim1.run_steps(50)
    sim2.run_steps(50)
    sim1.close()
    sim2.close()

    assert np.allclose(sim1.data[p], sim2.data[p])


def test_unroll_simulation():
    # note: we run this multiple times because the effects of unrolling can
    # be somewhat stochastic depending on the op order
    for _ in range(10):
        with nengo.Network(seed=0) as net:
            inp = nengo.Node(np.sin)
            ens = nengo.Ensemble(10, 1)
            nengo.Connection(inp, ens)
            p = nengo.Probe(ens)

        sim1 = nengo_dl.Simulator(net, step_blocks=10, unroll_simulation=False)
        sim2 = nengo_dl.Simulator(net, step_blocks=10, unroll_simulation=True)

        sim1.run_steps(50)
        sim2.run_steps(50)
        sim1.close()
        sim2.close()

        assert np.allclose(sim1.data[p], sim2.data[p])
