# Trivial makefile for the confxml tool.
# - Needs to run in a configured tree (config.h)
# - Needs libupnpp installed, as the rest of the build, for finding log.h

CPPFLAGS = -I../src -I.. -DMDU_INCLUDE_LOG='<libupnpp/log.h>'
VPATH=../src

OBJS = confxml.o smallut.o conftree.o pathut.o

confxml: $(OBJS)
	$(CXX) -o confxml $(CXXFLAGS) $(OBJS)

clean:
	rm -f *.o confxml
