.SUFFIXES: .txt .html

# volnitsky or flask
.txt.html:
	asciidoctor -b html5 -a toc2 -o $@ -a theme=volnitsky $<

HTML = $(patsubst %.txt,%.html,$(wildcard *.txt))

all: $(HTML)

upmpdcli-manual.html: upmpdcli-manual.txt upmpdcli-config.txt

upmpdcli-config.txt: ../src/upmpdcli.conf-dist
	confxml --asciidoc ../src/upmpdcli.conf-dist > upmpdcli-config.txt-
	mv -f upmpdcli-config.txt- upmpdcli-config.txt
        
clean:
	rm -f $(HTML)
