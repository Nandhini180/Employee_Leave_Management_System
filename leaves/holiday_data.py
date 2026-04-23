from datetime import date


# 2026 India gazetted holidays for central government offices.
# State-specific and restricted holidays vary by location, so these are the
# project defaults for company-wide public holiday exclusion.
INDIA_GAZETTED_HOLIDAYS_2026 = [
    ('Republic Day', date(2026, 1, 26)),
    ('Holi', date(2026, 3, 4)),
    ('Id-ul-Fitr', date(2026, 3, 21)),
    ('Ram Navami', date(2026, 3, 26)),
    ('Mahavir Jayanti', date(2026, 3, 31)),
    ('Good Friday', date(2026, 4, 3)),
    ('Buddha Purnima', date(2026, 5, 1)),
    ('Id-ul-Zuha (Bakrid)', date(2026, 5, 27)),
    ('Muharram', date(2026, 6, 26)),
    ('Independence Day', date(2026, 8, 15)),
    ('Milad-un-Nabi', date(2026, 8, 26)),
    ('Janmashtami (Vaishnava)', date(2026, 9, 4)),
    ("Mahatma Gandhi's Birthday", date(2026, 10, 2)),
    ('Dussehra', date(2026, 10, 20)),
    ('Diwali (Deepavali)', date(2026, 11, 8)),
    ("Guru Nanak's Birthday", date(2026, 11, 24)),
    ('Christmas Day', date(2026, 12, 25)),
]
