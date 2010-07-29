# -*- coding: utf-8 -*-
# Set this to the language you want to use.
LANG = "en"

# Singular and plural forms of time units in your language.
unit_names = dict(
	en = {
		"year":		("year",	"years"		),
		"month":	("month",	"months"	),
		"week":		("week",	"weeks"		),
		"day":		("day",		"days"		),
		"hour":		("hour",	"hours"		),
		"minute":	("minute",	"minutes"	),
		"second":	("second",	"seconds"	)
	}
)

def seconds_in_units(seconds):
    """
    Returns a tuple containing the most appropriate unit for the
    number of seconds supplied and the value in that units form.

        >>> seconds_in_units(7700)
        (2, 'hour')
    """
    unit_limits = [("year",		365 * 24 * 3600	),
                   ("month",	30 * 24 * 3600	),
                   ("week",		7 * 24 * 3600	),
                   ("day",		24 * 3600		),
                   ("hour",		3600			),
                   ("minute",	60				)]
    for unit_name, limit in unit_limits:
        if seconds >= limit:
            amount = int(round(float(seconds) / limit))
            return amount, unit_name
    return seconds, "second"

def prettyduration(seconds):
    """
    Converts seconds into a nicely readable string.
        >>> print readable_timedelta((77 * (24 * 60 * 60)) + 5)
        two months
    """
    amount, unit_name = seconds_in_units(seconds)

    # Localize it.
    i18n_unit	= unit_names[LANG][unit_name][1]
    if amount == 1:
        i18n_unit = unit_names[LANG][unit_name][0]
    return "%d %s" % (amount, i18n_unit)

