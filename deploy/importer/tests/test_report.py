"""The timings printed after the summary (importer/report.py)."""

from importer.report import Timings


def test_work_is_summed_per_name_and_listed_slowest_first():
    timings = Timings()
    timings.add("PUT products", 0.5)
    timings.add("POST images/products", 2.0)
    timings.add("POST images/products", 1.0)
    assert timings.work == {"PUT products": [1, 0.5], "POST images/products": [2, 3.0]}
    lines = timings.summary().splitlines()
    work = lines[lines.index(next(line for line in lines if line.startswith("work"))) + 1 :]
    assert work[0].split() == ["POST", "images/products", "2", "3.0", "1.500"]
    assert work[1].split() == ["PUT", "products", "1", "0.5", "0.500"]


def test_a_phase_is_timed_even_when_it_fails():
    timings = Timings()
    try:
        with timings.phase("categories"):
            raise RuntimeError("shop gone")
    except RuntimeError:
        pass
    assert "categories" in timings.phases
