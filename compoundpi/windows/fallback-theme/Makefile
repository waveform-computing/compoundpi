INKSCAPE=inkscape
SVG_IMAGES:=$(wildcard *.svg)
PNG_IMAGES:=$(SVG_IMAGES:.svg=.png)

%.png: %.svg
	$(INKSCAPE) -e $@ -w 48 -h 48 $<

all: $(PNG_IMAGES)

clean:
	rm -f $(PNG_IMAGES)
