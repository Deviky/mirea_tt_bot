import pytest
from main import format_schedule_by_days, GROUP_REGEX, TEACHER_REGEX


@pytest.mark.parametrize("text,expected", [
    ("ИКБО-21-01", True),
    ("БИОА-20-02", True),
    ("12345", False),
    ("ИВТ2101", False)
])
def test_group_regex(text, expected):
    assert bool(GROUP_REGEX.match(text)) == expected

@pytest.mark.parametrize("text,expected", [
    ("Иванов И.П.", True),
    ("Сидорова А.А.", True),
    ("Иванов", False),
    ("Петров А", False),
])
def test_teacher_regex(text, expected):
    assert bool(TEACHER_REGEX.match(text)) == expected

def test_format_schedule_output():
    schedule = [
        {'day_of_week': 'Понедельник', 'week_num': 1, 'couple_num': 1,
         'course_name': 'Математика', 'teacher_full_name': 'Иванов И.П.', 'auditorium': '101'},
        {'day_of_week': 'Понедельник', 'week_num': 2, 'couple_num': 1,
         'course_name': 'Физика', 'teacher_full_name': 'Петров А.В.', 'auditorium': '102'},
    ]

    result = format_schedule_by_days(schedule, for_group=True)
    assert "Понедельник" in result
    assert "Математика" in result
    assert "Физика" in result
    assert "1 (9:00 - 10:30)" in result


