PNGS=16x16/cpigui.png 24x24/cpigui.png 32x32/cpigui.png 48x48/cpigui.png 64x64/cpigui.png 128x128/cpigui.png
XPMS=xpm/cpigui.xpm
ICONS=ico/cpigui.ico

all: $(PNGS) $(XPMS) $(ICONS)

clean:
	rm -f $(PNGS) $(XPMS) $(ICONS)

16x16/%.png: scalable/%.svg
	inkscape -e $@ -w 16 -h 16 $<

24x24/%.png: scalable/%.svg
	inkscape -e $@ -w 24 -h 24 $<

32x32/%.png: scalable/%.svg
	inkscape -e $@ -w 32 -h 32 $<

48x48/%.png: scalable/%.svg
	inkscape -e $@ -w 48 -h 48 $<

64x64/%.png: scalable/%.svg
	inkscape -e $@ -w 64 -h 64 $<

128x128/%.png: scalable/%.svg
	inkscape -e $@ -w 128 -h 128 $<

# Starting from a large res PNG and resizing downward seems to produce the best
# "lower resolution" XPMs and ICOs

xpm/%.xpm: 128x128/%.png
	convert $< -resize 32x32 $@

ico/%.ico: 128x128/%.png
	convert $< -bordercolor white -border 0 \
		\( -clone 0 -resize 16x16 \) \
		\( -clone 0 -resize 32x32 \) \
		\( -clone 0 -resize 48x48 \) \
		\( -clone 0 -resize 64x64 \) \
		-delete 0 -alpha off -colors 256 $@

