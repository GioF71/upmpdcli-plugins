/* Copyright (C) 2016 J.F.Dockes
 *   This program is free software; you can redistribute it and/or modify
 *   it under the terms of the GNU Lesser General Public License as published by
 *   the Free Software Foundation; either version 2.1 of the License, or
 *   (at your option) any later version.
 *
 *   This program is distributed in the hope that it will be useful,
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *   GNU Lesser General Public License for more details.
 *
 *   You should have received a copy of the GNU Lesser General Public License
 *   along with this program; if not, write to the
 *   Free Software Foundation, Inc.,
 *   59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */
#include <string>
#include <iostream>
#include <sstream>
#include <vector>

#include <QApplication>
#include <QString>
#include <QCloseEvent>
#include <QMenu>
#include <QMenuBar>
#include <QAction>
#include <QFileDialog>
#include <QMessageBox>

#include "confgui.h"
#include "conftree.h"
#include "mainwindow.h"

#include "libupnpp/upnpputils.hxx"

using namespace std;
using namespace confgui;

#ifndef DATADIR
#define DATADIR "/usr/share/upmpdcli"
#endif
string g_datadir(DATADIR "/");

// g_csdef holds the defaults from the XML. g_csout values from a file
// specified on the command line or opened through the menu. The
// latter values override the defaults and will be output in addition
// to user changes.
static ConfSimple g_csdef, g_csout;
// The file we write to. Not necessarily the same as the input one
// (same if coming from the command line).
static string g_outfile;

// Pour the values from src into dest
void confMergeInto(ConfSimple& dest, const ConfSimple& src)
{
    for (const auto& key : src.getSubKeys()) {
        for (const auto& nm : src.getNames(key)) {
            string val;
            src.get(nm, val, key);
            dest.set(nm, val, key);
            //cerr << "confMergeInto: set " << key << ":" << nm << endl;
        }
    }
}

static string qs2utf8s(const QString& qs)
{
    return string((const char *)qs.toUtf8());
}
static string qs2locals(const QString& qs)
{
    return string((const char *)qs.toLocal8Bit());
}

static QString u8s2qs(const string us) 
{
    return QString::fromUtf8(us.c_str());
}

/** 
 * A Gui-to-Data link class for ConfTree
 * Has a subkey pointer member which makes it easy to change the
 * current subkey for a number at a time.
 */
class ConfLinkCS : public confgui::ConfLinkRep {
public:
    ConfLinkCS(ConfNull *conf, ConfNull *confdef, const std::string& nm,
               std::string *sk = 0)
    : m_conf(conf), m_confdef(confdef), m_nm(nm), m_sk(sk) {
    }
    virtual ~ConfLinkCS() {
    }

    virtual bool set(const std::string& val) {
    if (!m_conf)
        return false;
    bool ret = m_conf->set(m_nm, val, m_sk ? *m_sk : "");
    if (!ret) {
            std::cerr << "ConfLinkCS::set: failed for " << m_nm << std::endl;
        } else {
            cerr << "ConfLinkCS::set: " << (m_sk?*m_sk:string()) <<
                "[" << m_nm << "] = " << val << endl;
        }
    return ret;
    }
    virtual bool get(std::string& val) {
        // cerr << "conflinkCS: get value for " << m_nm << endl;
    if (!m_conf)
        return false;
        std::string sk = m_sk ? *m_sk : "";
    bool ret = m_conf->get(m_nm, val, sk);
        if (!ret && m_confdef) {
            // cerr << " no value from conf. Trying default\n";
            ret = m_confdef->get(m_nm, val, sk);
            if (!ret) {
                // cerr << " no value from default either\n";
            }
        }
        std::string sv = ret ? val : "no value";
        //std::cerr << "ConfLinkimpl::get: [" << m_nm << "] sk [" << sk <<
        //"] -> [" << sv << "]\n";
    return ret;
    }
private:
    ConfNull     *m_conf;
    ConfNull     *m_confdef;
    const std::string  m_nm;
    const std::string *m_sk;
};


class MyConfLinkFactCS : public confgui::ConfLinkFact {
public:
    MyConfLinkFactCS(ConfSimple *cs, ConfSimple *csdef) 
        : m_cs(cs), m_csdef(csdef) { }
    virtual ConfLink operator()(const QString& nm) {
        return ConfLink(new ConfLinkCS(m_cs, m_csdef, qs2utf8s(nm)));
    }
    ConfSimple *m_cs;
    ConfSimple *m_csdef;
};

MainWindow::MainWindow(ConfTabsW *w)
    : m_tabs(w)
{
    setCentralWidget(w);

    QMenu *fileMenu = menuBar()->addMenu(tr("&File"));

    QAction *act;
    act = new QAction(tr("&Open"), this);
    act->setShortcuts(QKeySequence::Open);
    connect(act, &QAction::triggered, this, &MainWindow::open);
    fileMenu->addAction(act);

    act = new QAction(tr("&Save"), this);
    act->setShortcuts(QKeySequence::Save);
    connect(act, &QAction::triggered, this, &MainWindow::save);
    fileMenu->addAction(act);
    
    act = new QAction(tr("Save &As"), this);
    connect(act, &QAction::triggered, this, &MainWindow::saveAs);
    fileMenu->addAction(act);

    act = new QAction(tr("&Quit"), this);
    act->setShortcuts(QKeySequence::Quit);
    connect(act, &QAction::triggered, this, &QWidget::close);
    fileMenu->addAction(act);
}

bool MainWindow::open()
{
    QFileDialog dialog(this);
    dialog.setWindowModality(Qt::WindowModal);
    if (dialog.exec() != QDialog::Accepted)
        return false;
    string f = qs2locals(dialog.selectedFiles().first());
    ConfSimple cs(f.c_str(), 1);
    if (cs.ok()) {
        g_csout.clear();
        confMergeInto(g_csout, cs);
        m_tabs->reloadPanels();
        return true;
    } else {
        QMessageBox::warning(0, "upmpdcli-config", tr("File parse failed"));
    }

    return false;
}

bool MainWindow::saveAs()
{
    QFileDialog dialog(this);
    dialog.setWindowModality(Qt::WindowModal);
    dialog.setAcceptMode(QFileDialog::AcceptSave);
    if (dialog.exec() != QDialog::Accepted)
        return false;
    g_outfile = qs2locals(dialog.selectedFiles().first());
    return saveToFile();
}

bool MainWindow::save()
{
    //cerr << "MainWindow::save: outfile: " << g_outfile << endl;
    if (g_outfile.empty()) {
        return saveAs();
    } else {
        return saveToFile();
    }
}

bool MainWindow::saveToFile()
{
    m_tabs->acceptChanges();
    ConfSimple fconf(g_outfile.c_str());
    fconf.holdWrites(true);
    confMergeInto(fconf, g_csout);
    bool ret = fconf.holdWrites(false);
    if (!ret) { 
        QMessageBox::warning(0, "upmpdcli-config",
                             tr("Save to file failed: ") + u8s2qs(g_outfile));
    }
    return ret;
}

void MainWindow::closeEvent(QCloseEvent *event)
{
    // Should test for unsaved mods here
    if (true) {
        event->accept();
    } else {
        event->ignore();
    }
}


static char *thisprog;

void Usage()
{
    cerr << "Usage: " << thisprog << " [configfile]\n";
    cerr << " The configuration file parameter will first be used as input,\n"
        "for initializing the current non-default values, and it is also the\n"
        "default output. Use 'Save As' if you can't write to it. \n"
        "If no parameter is given, the initial values will all be defaults.\n";
    exit(1);
}


int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    QCoreApplication::setOrganizationName("Upmpd.org");
    QCoreApplication::setApplicationName("upmpdcli-config");
    app.setQuitOnLastWindowClosed(true);

    thisprog = *argv++; argc--;
    if (argc > 1)
        Usage();
    if (argc) {
        if (*argv[0] == '-')
            Usage();
        g_outfile = *argv++;argc--;
    }

    // Note: there are ultimately 3 ConfSimple objects which are used here:
    //  - A ConfSimple built from the distributed config file, from
    //    which *only the XML-formatted comments are used*. Any actual
    //    assignement is ignored.
    //  - A ConfSimple which is built from the assignments defined in
    //    the top-level XML text from above (*Not* from any actual
    //    assignment), and which provides the initial values displayed
    //    in the data entry elements.
    //  - A ConfSimple which corresponds to the output file. If the
    //    file is not initially empty, any current assignement will
    //    override the default value and be displayed.
    // When the values are accepted, any value changed by the user in
    // the dialogs will be set in the output confsimple. Unchanged
    // values will do nothing, which means that we don't output
    // assignements for default values, and that assignements
    // initially present in the output file but unchanged are left
    // undisturbed.

    // Configuration file from the distribution, with the
    // XML-formatted comments, used to create the appropriate data
    // input objects, and supply them with initial values.
    string reffile(path_cat(g_datadir, "upmpdcli.conf-xml"));
    ConfSimple sconf(reffile.c_str(), 1);
    if (!sconf.ok()) {
        cerr << "Could not parse reference configuration: " << reffile << "\n";
        exit(1);
    }
    stringstream stream;
    bool ok = sconf.commentsAsXML(stream);
    if (!ok) {
        cerr << "Could not extract xml comments\n";
        exit(1);
    }

    // This is a bit tricky because we need the address of the
    // ConfSimple which will hold the defaults while we build the GUI
    // (because/so-that it can be stored in the conflink objects), but
    // it's not built yet (because we use the top level assignement
    // lines in the output of the XML parser to do it). So we'll
    // copy-assign the real confsimple to the provisional one once the
    // GUI is built, and reload the defaults. Slightly inefficient,
    // but does the job.
    string data;
    g_csout = ConfSimple(data);
    // If outfile was specd on the command line, it's both the input
    // and the output. Get existing parameters.
    if (!g_outfile.empty()) {
        ConfSimple cs(g_outfile.c_str(), 1);
        if (cs.ok()) {
            confMergeInto(g_csout, cs);
        } else {
            QMessageBox::warning(0, "upmpdcli-config", "File parse failed");
            return 1;
        }
    }
    MyConfLinkFactCS fact(&g_csout, &g_csdef);

    string toptext;
    ConfTabsW *w = xmlToConfGUI(stream.str(), toptext, &fact, 0);
    if (!w) {
        cerr << "Could not parse xml / create GUI\n";
        return 1;
    }
    // toptext contains the commented out variable assignements. Parse
    // it for defaults, assign to the defaults confsimple, and reload
    // the values.
    g_csdef = ConfSimple(toptext, true);
    if (!g_csdef.ok()) {
        cerr << "default config parse failed\n";
        return 1;
    }
    w->reloadPanels();

    // Find the network interfaces choice and load the interfaces names
    ConfParamW *pw = w->findParamW("upnpiface");
    if (pw == 0) {
        cerr << "upnpiface not found\n";
    } else {
        ConfParamCStrW *cpw = dynamic_cast<ConfParamCStrW*>(pw);
        if (cpw) {
            vector<string> adapters;
            UPnPP::getAdapterNames(adapters);
            QStringList qadapters;
            qadapters.push_back("");
            for (unsigned int i = 0; i < adapters.size(); i++) {
                qadapters.push_back(u8s2qs(adapters[i]));
            }
            cpw->setList(qadapters);
        } else {
            cerr << "upnpiface not a cstrl?\n";
        }
    }
    w->hideButtons();
    MainWindow mainWin(w);
    mainWin.show();
    return app.exec();
}
