/* Copyright (C) 2005-2021 J.F.Dockes
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
 *   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 */

#include "confgui.h"

#include <stdio.h>
#include <stdlib.h>
#include <vector>
#include <iostream>
#include <algorithm>
#include <string>

#include <qglobal.h>
#include <QHBoxLayout>
#include <QVBoxLayout>
#include <QTabWidget>
#include <QDialogButtonBox>
#include <QFrame>
#include <QListWidget>
#include <QFileDialog>
#include <QDebug>
#include <QDir>
#include <qobject.h>
#include <qlayout.h>
#include <qsize.h>
#include <qsizepolicy.h>
#include <qlabel.h>
#include <qspinbox.h>
#include <qtooltip.h>
#include <qlineedit.h>
#include <qcheckbox.h>
#include <qinputdialog.h>
#include <qpushbutton.h>
#include <qstringlist.h>
#include <qcombobox.h>

#include "smallut.h"

#ifdef ENABLE_XMLCONF
#include "picoxml.h"
#endif

namespace confgui {

// Main layout spacing
static const int spacing = 3;

// left,top,right, bottom
static QMargins margin(4,3,4,3);

// Margin around text to explicitely set pushbutton sizes lower than
// the default min (80?). Different on Mac OS for some reason
#ifdef __APPLE__
static const int pbTextMargin = 30;
#else
static const int pbTextMargin = 15;
#endif

ConfTabsW::ConfTabsW(QWidget *parent, const QString& title, ConfLinkFact *fact)
    : QDialog(parent), m_makelink(fact)
{
    setWindowTitle(title);
    tabWidget = new QTabWidget;

    buttonBox = new QDialogButtonBox(QDialogButtonBox::Ok | QDialogButtonBox::Cancel);

    QVBoxLayout *mainLayout = new QVBoxLayout;
    mainLayout->setSpacing(spacing);
    mainLayout->setContentsMargins(margin);
    mainLayout->addWidget(tabWidget);
    mainLayout->addWidget(buttonBox);
    setLayout(mainLayout);

    resize(QSize(500, 400).expandedTo(minimumSizeHint()));

    connect(buttonBox, SIGNAL(accepted()), this, SLOT(acceptChanges()));
    connect(buttonBox, SIGNAL(rejected()), this, SLOT(rejectChanges()));
}

void ConfTabsW::hideButtons()
{
    if (buttonBox)
        buttonBox->hide();
}

void ConfTabsW::acceptChanges()
{
    for (auto& entry : m_panels) {
        entry->storeValues();
    }
    for (auto& entry : m_widgets) {
        entry->storeValues();
    }
    emit sig_prefsChanged();
    if (!buttonBox->isHidden())
        close();
}

void ConfTabsW::rejectChanges()
{
    reloadPanels();
    if (!buttonBox->isHidden())
        close();
}

void ConfTabsW::reloadPanels()
{
    for (auto& entry : m_panels) {
        entry->loadValues();
    }
    for (auto& entry : m_widgets) {
        entry->loadValues();
    }
}

int ConfTabsW::addPanel(const QString& title)
{
    ConfPanelW *w = new ConfPanelW(this);
    m_panels.push_back(w);
    return tabWidget->addTab(w, title);
}

int ConfTabsW::addForeignPanel(ConfPanelWIF* w, const QString& title)
{
    m_widgets.push_back(w);
    QWidget *qw = dynamic_cast<QWidget *>(w);
    if (qw == 0) {
        qDebug() << "addForeignPanel: can't cast panel to QWidget";
        abort();
    }
    return tabWidget->addTab(qw, title);
}

void ConfTabsW::setCurrentIndex(int idx)
{
    if (tabWidget) {
        tabWidget->setCurrentIndex(idx);
    }
}

QWidget *ConfTabsW::addBlurb(int tabindex, const QString& txt)
{
    ConfPanelW *panel = (ConfPanelW*)tabWidget->widget(tabindex);
    if (panel == 0) {
        return 0;
    }

    QFrame *line = new QFrame(panel);
    line->setFrameShape(QFrame::HLine);
    line->setFrameShadow(QFrame::Sunken);
    panel->addWidget(line);

    QLabel *explain = new QLabel(panel);
    explain->setWordWrap(true);
    explain->setText(txt);
    panel->addWidget(explain);

    line = new QFrame(panel);
    line->setFrameShape(QFrame::HLine);
    line->setFrameShadow(QFrame::Sunken);
    panel->addWidget(line);
    return explain;
}

ConfParamW *ConfTabsW::addParam(
    int tabindex, ParamType tp, const QString& varname,
    const QString& label, const QString& tooltip,
    int ival, int maxval, const QStringList* sl)
{
    ConfLink lnk = (*m_makelink)(varname);

    ConfPanelW *panel = (ConfPanelW*)tabWidget->widget(tabindex);
    if (panel == 0) {
        return 0;
    }

    ConfParamW *cp = 0;
    switch (tp) {
    case CFPT_BOOL:
        cp = new ConfParamBoolW(varname, this, lnk, label, tooltip, ival);
        break;
    case CFPT_INT: {
        size_t v = (size_t)sl;
        int v1 = (v & 0xffffffff);
        cp = new ConfParamIntW(varname, this, lnk, label, tooltip, ival, maxval, v1);
        break;
    }
    case CFPT_STR:
        cp = new ConfParamStrW(varname, this, lnk, label, tooltip);
        break;
    case CFPT_CSTR:
        cp = new ConfParamCStrW(varname, this, lnk, label, tooltip, *sl);
        break;
    case CFPT_FN:
        cp = new ConfParamFNW(varname, this, lnk, label, tooltip, ival);
        break;
    case CFPT_STRL:
        cp = new ConfParamSLW(varname, this, lnk, label, tooltip);
        break;
    case CFPT_DNL:
        cp = new ConfParamDNLW(varname, this, lnk, label, tooltip);
        break;
    case CFPT_CSTRL:
        cp = new ConfParamCSLW(varname, this, lnk, label, tooltip, *sl);
        break;
    }
    cp->setToolTip(tooltip);
    panel->addParam(cp);
    return cp;
}

ConfParamW *ConfTabsW::findParamW(const QString& varname)
{
    for (const auto& panel : m_panels) {
        ConfParamW *w = panel->findParamW(varname);
        if (w)
            return w;
    }
    return nullptr;
}

void ConfTabsW::endOfList(int tabindex)
{
    ConfPanelW *panel = dynamic_cast<ConfPanelW*>(tabWidget->widget(tabindex));
    // panel may be null if this is a foreign panel (not a conftabsw)
    if (nullptr == panel) {
        return;
    }
    panel->endOfList();
}

bool ConfTabsW::enableLink(ConfParamW* boolw, ConfParamW* otherw, bool revert)
{
    ConfParamBoolW *bw = dynamic_cast<ConfParamBoolW*>(boolw);
    if (bw == 0) {
        std::cerr << "ConfTabsW::enableLink: not a boolw\n";
        return false;
    }
    otherw->setEnabled(revert ? !bw->m_cb->isChecked() : bw->m_cb->isChecked());
    if (revert) {
        connect(bw->m_cb, SIGNAL(toggled(bool)), otherw, SLOT(setDisabled(bool)));
    } else {
        connect(bw->m_cb, SIGNAL(toggled(bool)), otherw, SLOT(setEnabled(bool)));
    }
    return true;
}

ConfPanelW::ConfPanelW(QWidget *parent)
    : QWidget(parent)
{
    m_vboxlayout = new QVBoxLayout(this);
    m_vboxlayout->setSpacing(spacing);
    m_vboxlayout->setAlignment(Qt::AlignTop);
    m_vboxlayout->setContentsMargins(margin);
}

void ConfPanelW::addParam(ConfParamW *w)
{
    m_vboxlayout->addWidget(w);
    m_params.push_back(w);
}

void ConfPanelW::addWidget(QWidget *w)
{
    m_vboxlayout->addWidget(w);
}

ConfParamW *ConfPanelW::findParamW(const QString& varname)
{
    for (const auto& param : m_params) {
        if (varname == param->getVarName()) {
            return param;
        }
    }
    return nullptr;
}

void ConfPanelW::endOfList()
{
    m_vboxlayout->addStretch(2);
}

void ConfPanelW::storeValues()
{
    for (auto& widgetp : m_params) {
        widgetp->storeValue();
    }
}

void ConfPanelW::loadValues()
{
    for (auto& widgetp : m_params) {
        widgetp->loadValue();
    }
}

static QString myGetFileName(bool isdir, QString caption = QString(), bool filenosave = false);

static QString myGetFileName(bool isdir, QString caption, bool filenosave)
{
    QFileDialog dialog(0, caption);

    if (isdir) {
        dialog.setFileMode(QFileDialog::Directory);
        dialog.setOptions(QFileDialog::ShowDirsOnly);
    } else {
        dialog.setFileMode(QFileDialog::AnyFile);
        if (filenosave) {
            dialog.setAcceptMode(QFileDialog::AcceptOpen);
        } else {
            dialog.setAcceptMode(QFileDialog::AcceptSave);
        }
    }
    dialog.setViewMode(QFileDialog::List);
    QFlags<QDir::Filter> flags = QDir::NoDotAndDotDot | QDir::Hidden;
    if (isdir) {
        flags |= QDir::Dirs;
    } else {
        flags |= QDir::Dirs | QDir::Files;
    }
    dialog.setFilter(flags);

    if (dialog.exec() == QDialog::Accepted) {
        return dialog.selectedFiles().value(0);
    }
    return QString();
}

void ConfParamW::setValue(const QString& value)
{
    if (m_fsencoding) {
#ifdef _WIN32
        m_cflink->set(std::string((const char *)value.toUtf8()));
#else
        m_cflink->set(std::string((const char *)value.toLocal8Bit()));
#endif
    } else {
        m_cflink->set(std::string((const char *)value.toUtf8()));
    }
}

void ConfParamW::setValue(int value)
{
    m_cflink->set(std::to_string(value));
}

void ConfParamW::setValue(bool value)
{
    m_cflink->set(std::to_string(value));
}

extern void setSzPol(QWidget *w, QSizePolicy::Policy hpol,
                     QSizePolicy::Policy vpol, int hstretch, int vstretch);

void setSzPol(QWidget *w, QSizePolicy::Policy hpol,
              QSizePolicy::Policy vpol, int hstretch, int vstretch)
{
    QSizePolicy policy(hpol, vpol);
    policy.setHorizontalStretch(hstretch);
    policy.setVerticalStretch(vstretch);
    policy.setHeightForWidth(w->sizePolicy().hasHeightForWidth());
    w->setSizePolicy(policy);
    w->resize(w->sizeHint().width(), w->sizeHint().height());
}

bool ConfParamW::createCommon(const QString& lbltxt, const QString& tltptxt)
{
    m_hl = new QHBoxLayout(this);
    m_hl->setSpacing(spacing);
    m_hl->setContentsMargins(margin);

    QLabel *tl = new QLabel(this);
    tl->setToolTip(tltptxt);
    setSzPol(tl, QSizePolicy::Preferred, QSizePolicy::Fixed, 0, 0);
    tl->setText(lbltxt);

    m_hl->addWidget(tl);

    return true;
}

ConfParamIntW::ConfParamIntW(
    const QString& varnm, QWidget *parent, ConfLink cflink,
    const QString& lbltxt, const QString& tltptxt,
    int minvalue, int maxvalue, int defaultvalue)
    : ConfParamW(varnm, parent, cflink), m_defaultvalue(defaultvalue)
{
    if (!createCommon(lbltxt, tltptxt)) {
        return;
    }

    m_sb = new QSpinBox(this);
    m_sb->setMinimum(minvalue);
    m_sb->setMaximum(maxvalue);
    setSzPol(m_sb, QSizePolicy::Fixed, QSizePolicy::Fixed, 0, 0);
    m_hl->addWidget(m_sb);

    QFrame *fr = new QFrame(this);
    setSzPol(fr, QSizePolicy::Preferred, QSizePolicy::Fixed, 0, 0);
    m_hl->addWidget(fr);

    loadValue();
}

void ConfParamIntW::storeValue()
{
    if (m_origvalue != m_sb->value()) {
        setValue(m_sb->value());
    }
}

void ConfParamIntW::loadValue()
{
    std::string s;
    if (m_cflink->get(s)) {
        m_sb->setValue(m_origvalue = atoi(s.c_str()));
    } else {
        m_sb->setValue(m_origvalue = m_defaultvalue);
    }
}

void ConfParamIntW::setImmediate()
{
    connect(m_sb, SIGNAL(valueChanged(int)), this, SLOT(setValue(int)));
}

ConfParamStrW::ConfParamStrW(
    const QString& varnm, QWidget *parent, ConfLink cflink,
    const QString& lbltxt, const QString& tltptxt)
    : ConfParamW(varnm, parent, cflink)
{
    if (!createCommon(lbltxt, tltptxt)) {
        return;
    }

    m_le = new QLineEdit(this);
    setSzPol(m_le, QSizePolicy::Preferred, QSizePolicy::Fixed, 1, 0);

    m_hl->addWidget(m_le);

    loadValue();
}

void ConfParamStrW::storeValue()
{
    if (m_origvalue.compare(m_le->text())) {
        setValue(m_le->text());
    }
}

void ConfParamStrW::loadValue()
{
    std::string s;
    if (!m_cflink->get(s)) {
        s = m_strdefault;
    }
    if (m_fsencoding) {
#ifdef _WIN32
        m_le->setText(m_origvalue = QString::fromUtf8(s.c_str()));
#else
        m_le->setText(m_origvalue = QString::fromLocal8Bit(s.c_str()));
#endif
    } else {
        m_le->setText(m_origvalue = QString::fromUtf8(s.c_str()));
    }
}

void ConfParamStrW::setImmediate()
{
    connect(m_le, SIGNAL(textChanged(const QString&)), this, SLOT(setValue(const QString&)));
}

ConfParamCStrW::ConfParamCStrW(
    const QString& varnm, QWidget *parent, ConfLink cflink,
    const QString& lbltxt, const QString& tltptxt, const QStringList& sl)
    : ConfParamW(varnm, parent, cflink)
{
    if (!createCommon(lbltxt, tltptxt)) {
        return;
    }
    m_cmb = new QComboBox(this);
    m_cmb->setEditable(false);
    m_cmb->insertItems(0, sl);

    setSzPol(m_cmb, QSizePolicy::Preferred, QSizePolicy::Fixed, 1, 0);

    m_hl->addWidget(m_cmb);

    loadValue();
}

void ConfParamCStrW::setList(const QStringList& sl)
{
    m_cmb->clear();
    m_cmb->insertItems(0, sl);
    loadValue();
}

void ConfParamCStrW::storeValue()
{
    if (m_origvalue.compare(m_cmb->currentText())) {
        setValue(m_cmb->currentText());
    }
}

void ConfParamCStrW::loadValue()
{
    std::string s;
    if (!m_cflink->get(s)) {
        s = m_strdefault;
    }
    QString cs;
    if (m_fsencoding) {
#ifdef _WIN32
        cs = QString::fromUtf8(s.c_str());
#else
        cs = QString::fromLocal8Bit(s.c_str());
#endif        
    } else {
        cs = QString::fromUtf8(s.c_str());
    }

    for (int i = 0; i < m_cmb->count(); i++) {
        if (!cs.compare(m_cmb->itemText(i))) {
            m_cmb->setCurrentIndex(i);
            break;
        }
    }
    m_origvalue = cs;
}

void ConfParamCStrW::setImmediate()
{
    connect(m_cmb, SIGNAL(textActivated(const QString&)), this, SLOT(setValue(const QString&)));
}

ConfParamBoolW::ConfParamBoolW(
    const QString& varnm, QWidget *parent, ConfLink cflink,
    const QString& lbltxt, const QString& tltptxt, bool deflt)
    : ConfParamW(varnm, parent, cflink), m_dflt(deflt)
{
    // No createCommon because the checkbox has a label
    m_hl = new QHBoxLayout(this);
    m_hl->setSpacing(spacing);
    m_hl->setContentsMargins(margin);

    m_cb = new QCheckBox(lbltxt, this);
    setSzPol(m_cb, QSizePolicy::Fixed, QSizePolicy::Fixed, 0, 0);
    m_hl->addWidget(m_cb);
    m_cb->setToolTip(tltptxt);
    
    QFrame *fr = new QFrame(this);
    setSzPol(fr, QSizePolicy::Preferred, QSizePolicy::Fixed, 1, 0);
    m_hl->addWidget(fr);

    loadValue();
}

void ConfParamBoolW::storeValue()
{
    if (m_origvalue != m_cb->isChecked()) {
        setValue(m_cb->isChecked());
    }
}

void ConfParamBoolW::loadValue()
{
    std::string s;
    if (!m_cflink->get(s)) {
        m_origvalue = m_dflt;
    } else {
        m_origvalue = stringToBool(s);
    }
    m_cb->setChecked(m_origvalue);
}

void ConfParamBoolW::setImmediate()
{
    connect(m_cb, SIGNAL(toggled(bool)), this, SLOT(setValue(bool)));
}

ConfParamFNW::ConfParamFNW(
    const QString& varnm, QWidget *parent, ConfLink cflink,
    const QString& lbltxt, const QString& tltptxt, bool isdir)
    : ConfParamW(varnm, parent, cflink), m_isdir(isdir)
{
    if (!createCommon(lbltxt, tltptxt)) {
        return;
    }

    m_fsencoding = true;

    m_le = new QLineEdit(this);
    m_le->setMinimumSize(QSize(150, 0));
    setSzPol(m_le, QSizePolicy::Preferred, QSizePolicy::Fixed, 1, 0);
    m_hl->addWidget(m_le);

    m_pb = new QPushButton(this);

    QString text = tr("Choose");
    m_pb->setText(text);
    setSzPol(m_pb, QSizePolicy::Minimum, QSizePolicy::Fixed, 0, 0);
    m_hl->addWidget(m_pb);

    loadValue();
    QObject::connect(m_pb, SIGNAL(clicked()), this, SLOT(showBrowserDialog()));
}

void ConfParamFNW::storeValue()
{
    if (m_origvalue.compare(m_le->text())) {
        setValue(m_le->text());
    }
}

void ConfParamFNW::loadValue()
{
    std::string s;
    if (!m_cflink->get(s)) {
        s = m_strdefault;
    }
#ifdef _WIN32
    m_le->setText(m_origvalue = QString::fromUtf8(s.c_str()));
#else
    m_le->setText(m_origvalue = QString::fromLocal8Bit(s.c_str()));
#endif
}

void ConfParamFNW::showBrowserDialog()
{
    QString s = myGetFileName(m_isdir);
    if (!s.isEmpty()) {
        m_le->setText(s);
    }
}

void ConfParamFNW::setImmediate()
{
    connect(m_le, SIGNAL(textChanged(const QString&)), this, SLOT(setValue(const QString&)));
}

class SmallerListWidget: public QListWidget {
public:
    SmallerListWidget(QWidget *parent)
        : QListWidget(parent) {}
    virtual QSize sizeHint() const {
        return QSize(150, 40);
    }
};

ConfParamSLW::ConfParamSLW(
    const QString& varnm, QWidget *parent, ConfLink cflink,
    const QString& lbltxt, const QString& tltptxt)
    : ConfParamW(varnm, parent, cflink)
{
    // Can't use createCommon here cause we want the buttons below the label
    m_hl = new QHBoxLayout(this);
    m_hl->setSpacing(spacing);
    m_hl->setContentsMargins(margin);

    QVBoxLayout *vl1 = new QVBoxLayout();
    vl1->setSpacing(spacing);
    vl1->setContentsMargins(margin);
    QHBoxLayout *hl1 = new QHBoxLayout();
    hl1->setSpacing(spacing);
    hl1->setContentsMargins(margin);

    QLabel *tl = new QLabel(this);
    setSzPol(tl, QSizePolicy::Preferred, QSizePolicy::Fixed, 0, 0);
    tl->setText(lbltxt);
    tl->setToolTip(tltptxt);
    vl1->addWidget(tl);

    QPushButton *pbA = new QPushButton(this);
    QString text = tr("+");
    pbA->setText(text);
    pbA->setToolTip(tr("Add entry"));
    int width = pbA->fontMetrics().boundingRect(text).width() + pbTextMargin;
    pbA->setMaximumWidth(width);
    setSzPol(pbA, QSizePolicy::Minimum, QSizePolicy::Fixed, 0, 0);
    hl1->addWidget(pbA);
    QObject::connect(pbA, SIGNAL(clicked()), this, SLOT(showInputDialog()));

    QPushButton *pbD = new QPushButton(this);
    text = tr("-");
    pbD->setText(text);
    pbD->setToolTip(tr("Delete selected entries"));
    width = pbD->fontMetrics().boundingRect(text).width() + pbTextMargin;
    pbD->setMaximumWidth(width);
    setSzPol(pbD, QSizePolicy::Minimum, QSizePolicy::Fixed, 0, 0);
    hl1->addWidget(pbD);
    QObject::connect(pbD, SIGNAL(clicked()), this, SLOT(deleteSelected()));

    m_pbE = new QPushButton(this);
    text = tr("~");
    m_pbE->setText(text);
    m_pbE->setToolTip(tr("Edit selected entries"));
    width = m_pbE->fontMetrics().boundingRect(text).width() + pbTextMargin;
    m_pbE->setMaximumWidth(width);
    setSzPol(m_pbE, QSizePolicy::Minimum, QSizePolicy::Fixed, 0, 0);
    hl1->addWidget(m_pbE);
    QObject::connect(m_pbE, SIGNAL(clicked()), this, SLOT(editSelected()));
    m_pbE->hide();
    
    vl1->addLayout(hl1);
    m_hl->addLayout(vl1);

    m_lb = new SmallerListWidget(this);
    m_lb->setSelectionMode(QAbstractItemView::ExtendedSelection);
    connect(m_lb, SIGNAL(currentTextChanged(const QString&)),
            this, SIGNAL(currentTextChanged(const QString&)));

    setSzPol(m_lb, QSizePolicy::Preferred, QSizePolicy::Preferred, 1, 1);
    m_hl->addWidget(m_lb);

    setSzPol(this, QSizePolicy::Preferred, QSizePolicy::Preferred, 1, 1);
    loadValue();
}

void ConfParamSLW::setEditable(bool onoff)
{
    if (onoff) {
        m_pbE->show();
    } else {
        m_pbE->hide();
    }
}

std::string ConfParamSLW::listToString()
{
    std::vector<std::string> ls;
    for (int i = 0; i < m_lb->count(); i++) {
        // General parameters are encoded as utf-8.
        // Linux file names as local8bit There is no hope for 8bit
        // file names anyway except for luck: the original encoding is
        // unknown. In most modern configs, local8Bits will be UTF-8.
        // Except on Windows: we store file names as UTF-8
        QString text = m_lb->item(i)->text();
        if (m_fsencoding) {
#ifdef _WIN32
            ls.push_back((const char *)(text.toUtf8()));
#else
            ls.push_back((const char *)(text.toLocal8Bit()));
#endif
        } else {
            ls.push_back((const char *)(text.toUtf8()));
        }
    }
    std::string s;
    stringsToString(ls, s);
    return s;
}

void ConfParamSLW::storeValue()
{
    std::string s = listToString();
    if (s.compare(m_origvalue)) {
        m_cflink->set(s);
    }
}

void ConfParamSLW::loadValue()
{
    m_origvalue.clear();
    if (!m_cflink->get(m_origvalue)) {
        m_origvalue = m_strdefault;
    }
    std::vector<std::string> ls;
    stringToStrings(m_origvalue, ls);
    QStringList qls;
    for (const auto& str : ls) {
        if (m_fsencoding) {
#ifdef _WIN32
            qls.push_back(QString::fromUtf8(str.c_str()));
#else
            qls.push_back(QString::fromLocal8Bit(str.c_str()));
#endif
        } else {
            qls.push_back(QString::fromUtf8(str.c_str()));
        }
    }
    m_lb->clear();
    m_lb->insertItems(0, qls);
}

void ConfParamSLW::showInputDialog()
{
    bool ok;
    QString s = QInputDialog::getText(this, "", "", QLineEdit::Normal, "", &ok);
    if (!ok || s.isEmpty()) {
        return;
    }

    performInsert(s);
}

void ConfParamSLW::performInsert(const QString& s)
{
    QList<QListWidgetItem *> existing =
        m_lb->findItems(s, Qt::MatchFixedString | Qt::MatchCaseSensitive);
    if (!existing.empty()) {
        m_lb->setCurrentItem(existing[0]);
        return;
    }
    m_lb->insertItem(0, s);
    m_lb->sortItems();
    existing = m_lb->findItems(s, Qt::MatchFixedString | Qt::MatchCaseSensitive);
    if (existing.empty()) {
        std::cerr << "Item not found after insertion!" << "\n";
        return;
    }
    m_lb->setCurrentItem(existing[0], QItemSelectionModel::ClearAndSelect);
    
    if (m_immediate) {
        std::string nv = listToString();
        m_cflink->set(nv);
    }
}

void ConfParamSLW::deleteSelected()
{
    // We used to repeatedly go through the list and delete the first
    // found selected item (then restart from the beginning). But it
    // seems (probably depends on the qt version), that, when deleting
    // a selected item, qt will keep the selection active at the same
    // index (now containing the next item), so that we'd end up
    // deleting the whole list.
    //
    // Instead, we now build a list of indices, and delete it starting
    // from the top so as not to invalidate lower indices

    std::vector<int> idxes;
    for (int i = 0; i < m_lb->count(); i++) {
        if (m_lb->item(i)->isSelected()) {
            idxes.push_back(i);
        }
    }
    for (std::vector<int>::reverse_iterator it = idxes.rbegin();
         it != idxes.rend(); it++) {
        QListWidgetItem *item = m_lb->takeItem(*it);
        emit entryDeleted(item->text());
        delete item;
    }
    if (m_immediate) {
        std::string nv = listToString();
        m_cflink->set(nv);
    }
    if (m_lb->count()) {
        m_lb->setCurrentRow(0, QItemSelectionModel::ClearAndSelect);
    }
}

void ConfParamSLW::editSelected()
{
    for (int i = 0; i < m_lb->count(); i++) {
        if (m_lb->item(i)->isSelected()) {
            bool ok;
            QString s = QInputDialog::getText(
                this, "", "", QLineEdit::Normal, m_lb->item(i)->text(), &ok);
            if (ok && !s.isEmpty()) {
                m_lb->item(i)->setText(s);
                if (m_immediate) {
                    std::string nv = listToString();
                    m_cflink->set(nv);
                }
            }
        }
    }
}

// "Add entry" dialog for a file name list
void ConfParamDNLW::showInputDialog()
{
    QString s = myGetFileName(true);
    if (s.isEmpty()) {
        return;
    }
    performInsert(s);
}

// "Add entry" dialog for a constrained string list
void ConfParamCSLW::showInputDialog()
{
    bool ok;
    QString s = QInputDialog::getItem(this, "", "", m_sl, 0, false, &ok);
    if (!ok || s.isEmpty()) {
        return;
    }
    performInsert(s);
}


#ifdef ENABLE_XMLCONF

static QString u8s2qs(const std::string us)
{
    return QString::fromUtf8(us.c_str());
}

static const std::string& mapfind(
    const std::string& nm, const std::map<std::string, std::string>& mp)
{
    static std::string strnull;
    std::map<std::string, std::string>::const_iterator it = mp.find(nm);
    if (it == mp.end()) {
        return strnull;
    }
    return it->second;
}

static std::string looksLikeAssign(const std::string& data)
{
    //LOGDEB("looksLikeAssign. data: [" << data << "]");
    std::vector<std::string> toks;
    stringToTokens(data, toks, "\n\r\t ");
    if (toks.size() >= 2 && !toks[1].compare("=")) {
        return toks[0];
    }
    return std::string();
}

ConfTabsW *xmlToConfGUI(const std::string& xml, std::string& toptext,
                        ConfLinkFact* lnkf, QWidget *parent)
{
    //LOGDEB("xmlToConfGUI: [" << xml << "]");

    class XMLToConfGUI : public PicoXMLParser {
    public:
        XMLToConfGUI(const std::string& x, ConfLinkFact *lnkf, QWidget *parent)
            : PicoXMLParser(x), m_lnkfact(lnkf), m_parent(parent),
              m_idx(0), m_hadTitle(false), m_hadGroup(false) {
        }
        virtual ~XMLToConfGUI() {}

        virtual void startElement(const std::string& tagname,
                                  const std::map<std::string, std::string>& attrs) {
            if (!tagname.compare("var")) {
                m_curvar = mapfind("name", attrs);
                m_curvartp = mapfind("type", attrs);
                m_curvarvals = mapfind("values", attrs);
                //LOGDEB("Curvar: " << m_curvar);
                if (m_curvar.empty() || m_curvartp.empty()) {
                    throw std::runtime_error(
                        "<var> with no name attribute or no type ! nm [" +
                        m_curvar + "] tp [" + m_curvartp + "]");
                } else {
                    m_brief.clear();
                    m_descr.clear();
                }
            } else if (!tagname.compare("filetitle") ||
                       !tagname.compare("grouptitle")) {
                m_other.clear();
            }
        }

        virtual void endElement(const std::string& tagname) {
            if (!tagname.compare("var")) {
                if (!m_hadTitle) {
                    m_w = new ConfTabsW(m_parent, "Teh title", m_lnkfact);
                    m_hadTitle = true;
                }
                if (!m_hadGroup) {
                    m_idx = m_w->addPanel("Group title");
                    m_hadGroup = true;
                }
                ConfTabsW::ParamType paramtype;
                if (!m_curvartp.compare("bool")) {
                    paramtype = ConfTabsW::CFPT_BOOL;
                } else if (!m_curvartp.compare("int")) {
                    paramtype = ConfTabsW::CFPT_INT;
                } else if (!m_curvartp.compare("string")) {
                    paramtype = ConfTabsW::CFPT_STR;
                } else if (!m_curvartp.compare("cstr")) {
                    paramtype = ConfTabsW::CFPT_CSTR;
                } else if (!m_curvartp.compare("cstrl")) {
                    paramtype = ConfTabsW::CFPT_CSTRL;
                } else if (!m_curvartp.compare("fn")) {
                    paramtype = ConfTabsW::CFPT_FN;
                } else if (!m_curvartp.compare("dfn")) {
                    paramtype = ConfTabsW::CFPT_FN;
                } else if (!m_curvartp.compare("strl")) {
                    paramtype = ConfTabsW::CFPT_STRL;
                } else if (!m_curvartp.compare("dnl")) {
                    paramtype = ConfTabsW::CFPT_DNL;
                } else {
                    throw std::runtime_error("Bad type " + m_curvartp +
                                             " for " + m_curvar);
                }
                rtrimstring(m_brief, " .");
                switch (paramtype) {
                case ConfTabsW::CFPT_BOOL: {
                    int def = atoi(m_curvarvals.c_str());
                    m_w->addParam(m_idx, paramtype, u8s2qs(m_curvar),
                                  u8s2qs(m_brief), u8s2qs(m_descr), def);
                    break;
                }
                case ConfTabsW::CFPT_INT: {
                    std::vector<std::string> vals;
                    stringToTokens(m_curvarvals, vals);
                    int min = 0, max = 0, def = 0;
                    if (vals.size() >= 3) {
                        min = atoi(vals[0].c_str());
                        max = atoi(vals[1].c_str());
                        def = atoi(vals[2].c_str());
                    }
                    QStringList *sldef = 0;
                    sldef = (QStringList*)(((char*)sldef) + def);
                    m_w->addParam(m_idx, paramtype, u8s2qs(m_curvar),
                                  u8s2qs(m_brief), u8s2qs(m_descr),
                                  min, max, sldef);
                    break;
                }
                case  ConfTabsW::CFPT_CSTR:
                case ConfTabsW::CFPT_CSTRL: {
                    std::vector<std::string> cstrl;
                    stringToTokens(neutchars(m_curvarvals, "\n\r"), cstrl);
                    QStringList qstrl;
                    for (unsigned int i = 0; i < cstrl.size(); i++) {
                        qstrl.push_back(u8s2qs(cstrl[i]));
                    }
                    m_w->addParam(m_idx, paramtype, u8s2qs(m_curvar),
                                  u8s2qs(m_brief), u8s2qs(m_descr),
                                  0, 0, &qstrl);
                    break;
                }
                default:
                    m_w->addParam(m_idx, paramtype, u8s2qs(m_curvar),
                                  u8s2qs(m_brief), u8s2qs(m_descr));
                }
            } else if (!tagname.compare("filetitle")) {
                m_w = new ConfTabsW(m_parent, u8s2qs(m_other), m_lnkfact);
                m_hadTitle = true;
                m_other.clear();
            } else if (!tagname.compare("grouptitle")) {
                if (!m_hadTitle) {
                    m_w = new ConfTabsW(m_parent, "Teh title", m_lnkfact);
                    m_hadTitle = true;
                }
                // Get rid of "parameters" in the title, it's not interesting
                // and this makes our tab headers smaller.
                std::string ps{"parameters"};
                std::string::size_type pos = m_other.find(ps);
                if (pos != std::string::npos) {
                    m_other = m_other.replace(pos, ps.size(), "");
                }
                m_idx = m_w->addPanel(u8s2qs(m_other));
                m_hadGroup = true;
                m_other.clear();
            } else if (!tagname.compare("descr")) {
            } else if (!tagname.compare("brief")) {
                m_brief = neutchars(m_brief, "\n\r");
            }
        }

        virtual void characterData(const std::string& data) {
            if (!tagStack().back().compare("brief")) {
                m_brief += data;
            } else if (!tagStack().back().compare("descr")) {
                m_descr += data;
            } else if (!tagStack().back().compare("filetitle") ||
                       !tagStack().back().compare("grouptitle")) {
                // We don't want \n in there
                m_other += neutchars(data, "\n\r");
                m_other += " ";
            } else if (!tagStack().back().compare("confcomments")) {
                std::string nvarname = looksLikeAssign(data);
                if (!nvarname.empty() && nvarname.compare(m_curvar)) {
                    std::cerr << "Var assigned [" << nvarname << "] mismatch "
                        "with current variable [" << m_curvar << "]\n";
                }
                m_toptext += data;
            }
        }

        ConfTabsW *m_w;

        ConfLinkFact *m_lnkfact;
        QWidget *m_parent;
        int m_idx;
        std::string m_curvar;
        std::string m_curvartp;
        std::string m_curvarvals;
        std::string m_brief;
        std::string m_descr;
        std::string m_other;
        std::string m_toptext;
        bool m_hadTitle;
        bool m_hadGroup;
    };

    XMLToConfGUI parser(xml, lnkf, parent);
    try {
        if (!parser.parse()) {
            std::cerr << "Parse failed: " << parser.getLastErrorMessage() << "\n";
            return 0;
        }
    } catch (const std::runtime_error& e) {
        std::cerr << e.what() << "\n";
        return 0;
    }
    toptext = parser.m_toptext;
    return parser.m_w;
}

#endif /* ENABLE_XMLCONF */

} // Namespace confgui
