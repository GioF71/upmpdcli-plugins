.SUFFIXES: .txt .html

# volnitsky or flask. Volnitsky, which we used to use for the left side
# contents with asciidoc, does not work with asciidoctor.
# https://discuss.asciidoctor.org/asciidoctor-html-table-of-contents-in-sidebar-with-volnitsky-td5220.html
#.txt.html:
#	asciidoc -b html5 -a toc2 -o $@ -a theme=volnitsky $<

# Use the more modern asciidoctor
.txt.html:
	asciidoctor -b html5 -a toc=left -o $@ $<

HTML = $(patsubst %.txt,%.html,$(wildcard *.txt))

all: $(HTML)

upmpdcli-manual.html: upmpdcli-manual.txt upmpdcli-config.txt \
					  ../src/upmpdcli.conf-dist

upmpdcli-config.txt: ../src/upmpdcli.conf-xml
	confxml --asciidoc $< > upmpdcli-config.txt-
	mv -f upmpdcli-config.txt- upmpdcli-config.txt

# We rebuild this as a side-effect of building the doc (not needed for the doc)
../src/upmpdcli.conf-dist : ../src/upmpdcli.conf-xml
	confxml --strip $< > $@
        
clean:
	rm -f $(HTML) upmpdcli-config.txt
