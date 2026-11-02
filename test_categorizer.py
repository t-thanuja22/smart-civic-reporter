import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from categorizer import (classify_department, classify_priority,
                          haversine_distance_metres, find_duplicate)


class FakeComplaint:
    def __init__(self, lat, lon, category, status="Pending Approval"):
        self.latitude, self.longitude = lat, lon
        self.category, self.status = category, status


def test_classifies_streetlight_issue():
    category, dept = classify_department("Street light near the bus stop is not working")
    assert category == "Streetlight Fault"
    assert dept == "Electricity Board (EB)"


def test_classifies_electrical_hazard():
    category, dept = classify_department("A live wire has fallen on the main road, very dangerous")
    assert category == "Electrical Hazard"


def test_classifies_water_leakage():
    category, dept = classify_department("Water pipe burst near my house, wasting a lot of water")
    assert category == "Water Leakage"


def test_classifies_pothole():
    category, dept = classify_department("There is a big pothole on MG road causing accidents")
    assert category == "Pothole"


def test_unrecognised_text_falls_back_to_other():
    category, dept = classify_department("Random unrelated text about nothing civic")
    assert category == "Other"


def test_classifies_sanitation_issue():
    category, dept = classify_department("Garbage not cleaned for a week, full of trash")
    assert category == "Sanitation Issue"
    assert dept == "Municipal Corporation - Sanitation"


def test_classifies_mosquito_menace():
    category, dept = classify_department("Mosquito breeding in the stagnant drain, dengue risk")
    assert category == "Mosquito Menace"
    assert dept == "Public Health Department"


def test_classifies_overgrown_bushes():
    category, dept = classify_department("Overgrown bushes blocking the footpath near the park")
    assert category == "Overgrown Bushes"
    assert dept == "Municipal Corporation - General"


def test_classifies_animal_intrusion():
    category, dept = classify_department("Stray dogs chasing children near the school gate")
    assert category == "Animal Intrusion"
    assert dept == "Animal Control Department"


def test_critical_priority_for_fire_or_shock_risk():
    assert classify_priority("Live wire fallen, risk of electrocution near school") == "Critical"


def test_high_priority_for_exposed_wire():
    assert classify_priority("Exposed wire near the park, looks dangerous") == "High"


def test_medium_priority_for_generic_leak():
    assert classify_priority("Small water leak near the footpath") == "Medium"


def test_low_priority_default():
    assert classify_priority("Minor crack on the pavement") == "Low"


def test_priority_escalates_with_report_count():
    assert classify_priority("road issue", report_count=1) == "Low"
    assert classify_priority("road issue", report_count=6) == "High"


def test_distance_zero_for_same_point():
    assert haversine_distance_metres(13.08, 80.27, 13.08, 80.27) == 0


def test_finds_duplicate_within_radius():
    existing = [FakeComplaint(13.0800, 80.2700, "Pothole")]
    dup = find_duplicate(13.08005, 80.27005, "Pothole", existing)
    assert dup is not None


def test_no_duplicate_when_far_away():
    existing = [FakeComplaint(13.0800, 80.2700, "Pothole")]
    dup = find_duplicate(13.2000, 80.5000, "Pothole", existing)
    assert dup is None
