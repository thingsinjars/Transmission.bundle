# -*- coding: utf-8 -*-
# Set this to the language you want to use.
LANG = "en"

# Singular and plural forms of size units in your language.
limits = [
	(	"TB",		1024 * 1024 * 1024 * 1024	),
	(	"GB",		1024 * 1024 * 1024			),
	(	"MB",		1024 * 1024					),
	(	"KB",		1024						)
]

def prettysize(bytes):
	for name, limit in limits:
		if bytes >= limit:
			return "%.2f %s" % (
				float(bytes) / float(limit),
				name
			)

	return "%d bytes" % bytes

