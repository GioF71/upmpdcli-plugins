.SUFFIXES: .txt .html

# volnitsky or flask
.txt.html:
	asciidoctor -b html5 -a toc2 -o $@ -a theme=volnitsky $<

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
