from PMS import Log
from PIL import Image, ImageFont, ImageDraw
import cStringIO

LargeFont	= ImageFont.truetype("/Library/Fonts/Arial Bold.ttf", 100)
SmallFont	= ImageFont.truetype("/Library/Fonts/Arial Bold.ttf", 30)

def torrenticon(name, status, progress=100):
	result	= cStringIO.StringIO()
	image	= Image.new("RGBA", (304, 450), (0, 0, 0, 0))
	draw	= ImageDraw.Draw(image)

	Log.Add("name: %s, stats: %s" % (name, status))
	draw.text((1, 1), status, font=LargeFont, fill="black")
	draw.text((0, 0),	status,	font=LargeFont, fill="white")
	draw.text((1, 131),	name,	font=SmallFont, fill="black")
	draw.text((0, 130),	name,	font=SmallFont, fill="white")

	if progress >= 0:
		draw.rectangle((0,				170,
						3 * progress,	200), fill="white", outline="black")
		draw.rectangle((3 * progress,	170,
						300,			200), fill="#444", outline="black")

	image.save(result, "PNG")
	return result.getvalue()
