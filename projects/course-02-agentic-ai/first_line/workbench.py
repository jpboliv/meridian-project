"""Project fixture: one collector stops polling while the exchange keeps running."""

from meridian.signals import MetricStore
from meridian.simulator import Simulator


class StoppedCollector(MetricStore):
    def __init__(self, metrics, component, last_poll_tick):
        super().__init__(history=metrics.history)
        self.component = component
        self.last_poll = MetricStore(history=[s for s in self.history if s["tick"] <= last_poll_tick])
        if not self.last_poll.history or self.last_poll.history[-1]["tick"] != last_poll_tick:
            raise ValueError("last_poll_tick must name a recorded warm-up sample")

    def series(self, component, last_ticks):
        if component == self.component:
            return self.last_poll.series(component, last_ticks)
        return super().series(component, last_ticks)


def start_exchange(case):
    sim = Simulator(case)
    collector = sim.scenario.tools.get("metric_collector")
    if collector:
        sim.metrics = StoppedCollector(sim.metrics, **collector)
    return sim
