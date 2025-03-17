# Normally not used any more, as upmpdcli-config is built by meson/ninja as the rest.
# Kept just in case building just upmpdcli-config is needed.

TEMPLATE	= app
LANGUAGE	= C++

QMAKE_CXXFLAGS += -I../ -DENABLE_XMLCONF

DEFINES += MDU_INCLUDE_LOG=\'<libupnpp/log.h>\'

CONFIG	+= c++17 qt warn_on thread release debug
QT += widgets

# upnpp needed just for log.cpp. We could build it locally but having dup copies of log.cpp/h would
# confuse things even if they are not used for upmpdcli itself.
LIBS += -lupnpp

INCLUDEPATH += ../src

HEADERS	+= confgui.h mainwindow.h

SOURCES	+= confmain.cpp \
           confgui.cpp \
           ../src/conftree.cpp \
           ../src/smallut.cpp \
           ../src/pathut.cpp

target.path = "$$PREFIX/bin"
INSTALLS += target
