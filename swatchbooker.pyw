#!/usr/bin/env python
# coding: utf-8
#
#       Copyright 2008 Olivier Berten <olivier.berten@gmail.com>
#
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 3 of the License, or
#       (at your option) any later version.
#       
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#       
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.
#

from __future__ import division
import sys
import time
import tempfile
import gettext
from PyQt4.QtCore import *
from PyQt4.QtGui import *

from swatchbook import *

__version__ = "0.7"

availables_lang = {'de': u'Deutsch',
                   'fr': u'Français',
                   'pt_BR': u'Português do Brasil',
                   'ru': u'Русский'}

current_sw = False
current_sp = False
breaks = []

swatchbooker_svg = (dirpath(__file__) or ".")+"/icons/swatchbooker.svg" 

# 0: float, 1: percentage, 2: degrees
models = SortedDict()
models['Lab'] = (('L',0),('a',0),('b',0))
models['XYZ'] = (('X',0),('Y',0),('Z',0))
models['RGB'] = (('R',1),('G',1),('B',1))
models['CMY'] = (('C',1),('M',1),('Y',1))
models['HLS'] = (('H',2),('L',1),('S',1))
models['HSV'] = (('H',2),('S',1),('V',1))
models['CMYK'] = (('C',1),('M',1),('Y',1),('K',1))
models['GRAY'] = (('K',1),)
models['YIQ'] = (('Y',0),('I',0),('Q',0))

class sbTreeWidget(QTreeWidget):
	def __init__(self, parent=None):
		super(sbTreeWidget, self).__init__(parent)
		self.setHeaderHidden(True)
		self.setDragDropMode(QTreeWidget.InternalMove)
		self.setDragEnabled(True)
		self.setDropIndicatorShown(True)
		self.item = False
		self.itemParent = False

	def dropEvent(self,event):
		global current_sw
		QTreeWidget.dropEvent(self,event)
		mainWindow = self.parent().parent().parent()
		if self.itemParent and self.itemParent.childCount() == 0:
			nochild = noChild()
			self.itemParent.addChild(nochild)
			mainWindow.treeItems[nochild] = None
		if isinstance(self.item.parent(),treeItemGroup):
			if isinstance(self.item.parent().child(0),noChild):
				self.item.parent().removeChild(self.item.parent().child(0))
			if isinstance(self.item.parent().child(self.item.parent().childCount()-1),noChild):
				self.item.parent().removeChild(self.item.parent().child(self.item.parent().childCount()-1))
		swParent,swID = mainWindow.get_parent(mainWindow.treeItems[self.item])
		sw = swParent.items.pop(swID)
		if self.item.parent():
			mainWindow.treeItems[self.item.parent()].items.insert(self.item.parent().indexOfChild(self.item),swID,sw)
			mainWindow.sb.ids[swID] = (sw,mainWindow.treeItems[self.item.parent()])
		else:
			mainWindow.sb.items.insert(mainWindow.treeWidget.indexOfTopLevelItem(self.item),swID,sw)
			mainWindow.sb.ids[swID] = (sw,mainWindow.sb)
		listItems = []
		self.listItems(self.item,listItems)
		for listItem in listItems:
			mainWindow.listWidget.takeItem(mainWindow.listWidget.indexFromItem(listItem).row())
		self.setCurrentItem(self.item)
		item = self.swItemAbove(self.item)
		if item:
			index = mainWindow.listWidget.indexFromItem(mainWindow.itemList[mainWindow.treeItems[item]]).row()+1
		else:
			index = 0
		listItems.reverse()
		for listItem in listItems:
			mainWindow.listWidget.insertItem(index,listItem)
		mainWindow.listWidget.update()
		mainWindow.sw_display_tree()

	def swItemAbove(self,item):
		nitem = self.itemAbove(item)
		if isinstance(nitem,treeItemGroup):
			if nitem == item.parent() or not self.lastChild(nitem):
				nitem = self.swItemAbove(nitem)
			else:
				nitem = self.lastChild(nitem)
		elif isinstance(nitem,noChild):
			nitem = self.swItemAbove(nitem.parent())
		return nitem

	def lastChild(self,group):
		if group.childCount > 0:
			item = group.child(group.childCount()-1)
			if isinstance(item,treeItemGroup):
				item = self.lastChild(item)
			return item

	def listItems(self,item,listItems):
		mainWindow = self.parent().parent().parent()
		if isinstance(item,treeItemGroup):
			for i in range(item.childCount()):
				self.listItems(item.child(i),listItems)
		else:
			listItems.append(mainWindow.itemList[mainWindow.treeItems[item]])

	def mousePressEvent(self,event):
		QTreeWidget.mousePressEvent(self,event)
		self.item = self.itemAt(event.pos())
		if self.item:
			self.itemParent = self.item.parent()

class sbListWidget(QListWidget):
	def __init__(self, parent=None):
		super(sbListWidget, self).__init__(parent)
		self.setViewMode(QListView.IconMode)
		self.setMovement(QListView.Static)
		self.setResizeMode(QListView.Adjust)
		self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
		self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self.update()

	def update(self):
		self.zWidth = 2*self.frameWidth() + self.verticalScrollBar().size().width() + 1
		self.zHeight = 2*self.frameWidth()
		global breaks
		avail_width = self.size().width() - self.zWidth
		breaks2 = {}
		for item in breaks:
			breaks2[self.row(item)] = item
		for key in sorted(breaks2.iterkeys()):
			width = (int((avail_width-self.visualItemRect(self.item(key-1)).left())/17)-1)*17
			breaks2[key].setSizeHint(QSize(width,17))
			self.doItemsLayout()

	def resizeEvent(self,event):
		QListWidget.resizeEvent(self,event)
		self.update()

class GroupWidget(QGroupBox):
	def __init__(self, parent=None):
		super(GroupWidget, self).__init__(parent)
		
		self.parent = parent
		self.setTitle(_("Group"))

		nameLabel = QLabel(_("Name:"))
		self.swName = QLineEdit()
		self.l10nName = l10nButton()
		descriptionLabel = QLabel(_("Description:"))
		self.swDescription = QTextEdit()
		self.l10nDescription = l10nButton()
		self.l10nLicense = l10nButton()
		swInfo = QGridLayout()
		swInfo.addWidget(nameLabel, 0, 0)
		swInfo.addWidget(self.swName, 0, 1)
		swInfo.addWidget(self.l10nName, 0, 2)
		swInfo.addWidget(descriptionLabel, 1, 0, 1, 2)
		swInfo.addWidget(self.swDescription, 2, 0, 1, 2)
		swInfo.addWidget(self.l10nDescription, 2, 2, Qt.AlignTop)
		self.setLayout(swInfo)

		if hasattr(current_sw,'info'):
			if 'name' in current_sw.info:
				info = current_sw.info['name'].copy()
				if 0 in info:
					self.swName.setText(current_sw.info['name'][0])
					del info[0]
				if len(info) > 0:
					self.l10nName.setStyleSheet("l10nButton { font: bold }")
			if 'description' in current_sw.info:
				info = current_sw.info['description'].copy()
				if 0 in info:
					self.swDescription.setText(current_sw.info['description'][0])
					del info[0]
				if len(info) > 0:
					self.l10nDescription.setStyleSheet("l10nButton { font: bold }")

		# Actions
		self.connect(self.swName,
				SIGNAL("textEdited(QString)"), self.sw_edit)
		self.connect(self.swDescription,
				SIGNAL("textChanged()"), self.sw_edit)
		self.connect(self.l10nName,
				SIGNAL("pressed()"), self.sw_l10n)
		self.connect(self.l10nDescription,
				SIGNAL("pressed()"), self.sw_l10n)

	def sw_edit(self):
		global current_sw
		if self.sender() == self.swName:
			if self.swName.text() == '':
				del current_sw.info['name'][0]
				if len(current_sw.info['name']) == 0:
					del current_sw.info['name']
			else:
				if 'name' not in current_sw.info:
					current_sw.info['name'] = {}
				current_sw.info['name'][0] = unicode(self.swName.text())
			self.parent.itemTree[current_sw].update()
		if self.sender() == self.swDescription:
			if self.swDescription.toPlainText() == '':
				del current_sw.info['description'][0]
				if len(current_sw.info['description']) == 0:
					del current_sw.info['description']
			else:
				if 'description' not in current_sw.info:
					current_sw.info['description'] = {}
				current_sw.info['description'][0] = unicode(self.swDescription.toPlainText())

	def sw_l10n(self):
		if not self.sender().isChecked():
			infos = {self.l10nName: 'name', self.l10nDescription: 'description' }
			if infos[self.sender()] not in current_sw.info:
				current_sw.info[infos[self.sender()]] = {}

			l10nPopup = l10nWidget(self.sender(),current_sw.info[infos[self.sender()]],self)
			l10nPopup.show()

class ColorWidget(QGroupBox):
	def __init__(self, parent=None):
		super(ColorWidget, self).__init__(parent)
		
		self.parent = parent
		self.setTitle(_("Color"))

		nameLabel = QLabel(_("Name:"))
		self.swName = QLineEdit()
		self.l10nName = l10nButton()
		descriptionLabel = QLabel(_("Description:"))
		self.swDescription = QTextEdit()
		self.l10nDescription = l10nButton()
		self.l10nLicense = l10nButton()
		self.sample = QLabel()
		self.sample.setMinimumHeight(30)
		self.swSpot = QCheckBox(_("Spot"))
		self.swValues = QTabWidget()
		self.butVal = QToolButton(self.swValues)
		self.butVal.setFixedSize(12,12)
		self.butVal.setArrowType(Qt.DownArrow)
		self.butVal.setStyleSheet("QToolButton::menu-indicator {image: none;}")
		cornLay = QVBoxLayout()
		cornLay.setContentsMargins(20,0,0,20)
		cornLay.addWidget(self.butVal)
		cornWid = QWidget()
		cornWid.setLayout(cornLay)
		cornWid.setMinimumSize(12,12)
		self.menuVal = QMenu()
		self.menuValModl = self.menuVal.addMenu(_('Add'))
		global models
		for model in models:
			self.menuValModl.addAction(model,self.addVal)
		self.delValAction = self.menuVal.addAction(_('Remove'),self.delVal)
		self.delValAction.setEnabled(False)
		self.butVal.setPopupMode(QToolButton.InstantPopup)
		self.butVal.setMenu(self.menuVal)
		self.swValues.setCornerWidget(cornWid)

		self.swExtra = QTableWidget()
		self.swExtra.setColumnCount(2)
		self.swExtra.horizontalHeader().setStretchLastSection(True)
		self.swExtra.verticalHeader().hide()
		self.swExtra.setHorizontalHeaderLabels([_("Key"),_("Value")])
		self.swExtra.setSelectionBehavior(QAbstractItemView.SelectRows)
		self.butExtra = QToolButton(self)
		self.butExtra.setFixedSize(12,12)
		self.butExtra.setArrowType(Qt.DownArrow)
		self.butExtra.setStyleSheet("QToolButton::menu-indicator {image: none;}")
		self.menuExtra = QMenu()
		self.menuExtra.addAction(_('Add'),self.addExtra)
		self.extraRemoveAction = self.menuExtra.addAction(_('Remove'),self.remExtra)
		self.butExtra.setPopupMode(QToolButton.InstantPopup)
		self.butExtra.setMenu(self.menuExtra)
		self.extraRemoveAction.setEnabled(False)

		groupBoxExtra = QGroupBox(_("Extra info"))
		boxExtra = QHBoxLayout()
		boxExtra.addWidget(self.swExtra)
		boxExtra.addWidget(self.butExtra,0,Qt.AlignTop)
		groupBoxExtra.setLayout(boxExtra)

		swInfo = QGridLayout()
		swInfo.addWidget(nameLabel, 0, 0)
		swInfo.addWidget(self.swName, 0, 1)
		swInfo.addWidget(self.l10nName, 0, 2)
		swInfo.addWidget(descriptionLabel, 1, 0, 1, 2)
		swInfo.addWidget(self.swDescription, 2, 0, 1, 2)
		swInfo.addWidget(self.l10nDescription, 2, 2, Qt.AlignTop)
		swInfo.addWidget(self.sample, 3, 0, 1, 3)
		swInfo.addWidget(self.swSpot, 4, 0, 1, 3)
		swInfo.addWidget(self.swValues, 5, 0, 1, 3)
		swInfo.addWidget(groupBoxExtra, 6, 0, 1, 3)
		self.setLayout(swInfo)

		if hasattr(current_sw,'info'):
			if 'name' in current_sw.info:
				info = current_sw.info['name'].copy()
				if 0 in info:
					self.swName.setText(current_sw.info['name'][0])
					del info[0]
				if len(info) > 0:
					self.l10nName.setStyleSheet("l10nButton { font: bold }")
			if 'description' in current_sw.info:
				info = current_sw.info['description'].copy()
				if 0 in info:
					self.swDescription.setText(current_sw.info['description'][0])
					del info[0]
				if len(info) > 0:
					self.l10nDescription.setStyleSheet("l10nButton { font: bold }")
		if hasattr(current_sw,'attr') and 'spot' in current_sw.attr:
			self.swSpot.setChecked(True)
		self.val = {}
		if hasattr(current_sw,'values') and len(current_sw.values) > 0:
			self.delValAction.setEnabled(True)
			prof_out = settings.value("DisplayProfile").toString() or False
			r,g,b = current_sw.toRGB8(prof_out)
			self.sample.setStyleSheet("QWidget { background-color: rgb("+str(r)+","+str(g)+","+str(b)+") }")
			for model in current_sw.values:
				self.add_val_tab(model,current_sw.values[model])

			self.def_current_sp()

		if hasattr(current_sw,'extra'):
			self.tExtra = []
			row = 0
			for extra in current_sw.extra:
				self.swExtra.insertRow(row)
				key = QTableWidgetItem(extra)
				if current_sw.extra[extra]:
					val = QTableWidgetItem(current_sw.extra[extra])
				else:
					val = QTableWidgetItem()
				self.swExtra.setItem(row, 0, key)
				self.swExtra.setItem(row, 1, val)
				row += 1
				self.tExtra.append([unicode(extra),unicode(current_sw.extra[extra])])
			
		# Actions
		self.connect(self.swName,
				SIGNAL("textEdited(QString)"), self.sw_edit)
		self.connect(self.swDescription,
				SIGNAL("textChanged()"), self.sw_edit)
		self.connect(self.swSpot,
				SIGNAL("stateChanged(int)"), self.sw_edit)
		self.connect(self.swValues,
				SIGNAL("currentChanged(int)"), self.def_current_sp)
		self.connect(self.swExtra,
				SIGNAL("cellChanged(int,int)"), self.sw_edit)
		self.connect(self.swExtra,
				SIGNAL("cellClicked(int,int)"), self.extra_editable)
		self.connect(self.l10nName,
				SIGNAL("pressed()"), self.sw_l10n)
		self.connect(self.l10nDescription,
				SIGNAL("pressed()"), self.sw_l10n)

	def add_val_tab(self,model,values=None):
		global current_sw
		global models
		profile = model[1]
		modell = model[0]
		swColor = QWidget()
		grid = QGridLayout()
		width = 2
		count = 0
		if modell in models:
			for elem in models[modell]:
				val = QLineEdit()
				self.val[val] = (model,count)
				self.connect(val,
						SIGNAL("textEdited(QString)"), self.sw_valedit)
				grid.addWidget(QLabel(elem[0]+":"), count, 0)
				if elem[1] == 0:
					if values:
						val.setText(str(round(values[count],2)))
					else:
						val.setText('0')
					grid.addWidget(val, count, 1)
				elif elem[1] == 1:
					width = 3
					if values:
						val.setText(str(round(values[count]*100,2)))
					else:
						val.setText('0')
					grid.addWidget(val, count, 1)
					grid.addWidget(QLabel("%"), count, 2)
				if elem[1] == 2:
					width = 3
					if values:
						val.setText(str(round(values[count]*360,2)))
					else:
						val.setText('0')
					grid.addWidget(val, count, 1)
					grid.addWidget(QLabel(u"°"), count, 2)
				count += 1
		else:
			self.val[model] = {}
			for ink in values:
				val = QLineEdit()
				self.val[val] = (model,count)
				if values:
					val.setText(str(round(values[count],2)))
				else:
					val.setText('0')
				grid.addWidget(val, count, 1)
				count += 1
				
		if modell not in ('Lab','XYZ'):
			grid.addWidget(QLabel(_("Profile")), count, 0, 1, width)
			if modell in ('RGB','HSL','HSV','YIQ','CMY'):
				modellist = 'RGB'
			else:
				modellist = modell
			profList = QComboBox()
			profList.addItems(self.getProfList(modell))
			if profile in self.parent.sb.profiles:
				profList.setCurrentIndex(self.parent.profiles[modell].index(profile)+1)
			self.connect(profList,
					SIGNAL("currentIndexChanged(int)"), self.change_profile)
			grid.addWidget(profList, count+1, 0, 1, width)
		swColor.setLayout(grid)
		
		self.swValues.addTab(swColor,modell)

	def sw_edit(self):
		global current_sw
		if self.sender() == self.swName:
			if self.swName.text() == '':
				del current_sw.info['name'][0]
				if len(current_sw.info['name']) == 0:
					del current_sw.info['name']
			else:
				if 'name' not in current_sw.info:
					current_sw.info['name'] = {}
				current_sw.info['name'][0] = unicode(self.swName.text())
			self.parent.itemTree[current_sw].update()
			self.parent.itemList[current_sw].update()
		if self.sender() == self.swDescription:
			if self.swDescription.toPlainText() == '':
				del current_sw.info['description'][0]
				if len(current_sw.info['description']) == 0:
					del current_sw.info['description']
			else:
				if 'description' not in current_sw.info:
					current_sw.info['description'] = {}
				current_sw.info['description'][0] = unicode(self.swDescription.toPlainText())
		if self.sender() == self.swSpot:
			if self.swSpot.isChecked():
				current_sw.attr.append('spot')
			else:
				current_sw.attr.remove('spot')
			self.set_preview()
		if self.sender() == self.swExtra:
			row,col = self.swExtra.currentRow(),self.swExtra.currentColumn()
			if col == 0:
				if self.tExtra[row][0] in current_sw.extra:
					del current_sw.extra[self.tExtra[row][0]]
				self.tExtra[row][0] = unicode(self.swExtra.item(row,col).text())
			else:
				self.tExtra[row][0] = unicode(self.swExtra.item(row,col).text())
				self.tExtra[row][col] = unicode(self.swExtra.item(row,col).text())
			if self.swExtra.item(row,0):
				if self.swExtra.item(row,1):
					current_sw.extra[unicode(self.swExtra.item(row,0).text())] = unicode(self.swExtra.item(row,1).text())
				else:
					current_sw.extra[unicode(self.swExtra.item(row,0).text())] = None

	def set_preview(self):
		prof_in = settings.value("DisplayProfile").toString() or False
		prof_out = settings.value("CMYKProfile").toString() or False
		if current_sw.toRGB8(prof_out):
			r,g,b = current_sw.toRGB8(prof_out)
			self.sample.setStyleSheet("QWidget { background-color: rgb("+str(r)+","+str(g)+","+str(b)+") }")
		else:
			self.sample.setStyleSheet("")
		self.parent.itemTree[current_sw].update()
		self.parent.itemList[current_sw].update()

	def sw_valedit(self):
		global models
		global current_sw
		sender = self.val[self.sender()]
		profile = sender[0][1]
		model = sender[0][0]
		if model in models:
			if models[model][sender[1]][1] == 0:
				current_sw.values[sender[0]][sender[1]] = eval(str(self.sender().text()))
			elif models[model][sender[1]][1] == 1:
				current_sw.values[sender[0]][sender[1]] = eval(str(self.sender().text()))/100
			elif models[model][sender[1]][1] == 2:
				current_sw.values[sender[0]][sender[1]] = eval(str(self.sender().text()))/360
		else:
			current_sw.values[sender[0]][sender[1]] = eval(str(self.sender().text()))
		self.set_preview()

	def def_current_sp(self):
		global current_sp
		if self.swValues.count() > 0:
			model = str(self.swValues.tabText(self.swValues.currentIndex()))
			combo = self.swValues.currentWidget().findChild(QComboBox)
			if combo and combo.currentIndex() > 0:
				current_sp = (model,self.parent.profiles[model][combo.currentIndex()-1])
			else:
				current_sp = (model,False)
		else:
			current_sp = False

	def change_profile(self):
		global current_sw
		global current_sp
		value = current_sw.values[current_sp]
		del current_sw.values[current_sp]
		self.def_current_sp()
		current_sw.values[current_sp] = value
		fields = self.swValues.currentWidget().findChildren(QLineEdit)
		for field in fields:
			self.val[field] = (current_sp,self.val[field][1])
		self.set_preview()

	def delVal(self):
		global current_sw
		global current_sp
		value = current_sw.values[current_sp]
		del current_sw.values[current_sp]
		self.swValues.removeTab(self.swValues.currentIndex())
		self.set_preview()

	def addVal(self):
		global models
		global current_sw
		model = (str(self.sender().text()),False)
		if not hasattr(self,'val'):
			self.val = {}
		current_sw.values[model] = []
		self.add_val_tab(model)
		for elem in models[model[0]]:
			current_sw.values[model].append(0)
		self.swValues.setCurrentIndex(self.swValues.count()-1)
		self.def_current_sp()
		self.delValAction.setEnabled(True)
		self.set_preview()
		
	def getProfList(self,model):
		profList = QStringList()
		profList << ''
		if model in self.parent.profiles:
			for prof in self.parent.profiles[model]:
				profList << self.parent.sb.profiles[prof].info['desc'][0]
		return profList

	def extra_editable(self):
		self.extraRemoveAction.setEnabled(True)

	def addExtra(self):
		self.swExtra.insertRow(self.swExtra.rowCount())
		if not hasattr(self,"tExtra"):
			self.tExtra = []
		self.tExtra.append([None,None])
		
	def remExtra(self):
		if self.swExtra.item(self.swExtra.currentRow(),0):
			extra = unicode(self.swExtra.item(self.swExtra.currentRow(),0).text())
			del current_sw.extra[extra]
		self.swExtra.removeRow(self.swExtra.currentRow())
		self.extraRemoveAction.setEnabled(False)

	def sw_l10n(self):
		if not self.sender().isChecked():
			infos = {self.l10nName: 'name', self.l10nDescription: 'description' }
			if infos[self.sender()] not in current_sw.info:
				current_sw.info[infos[self.sender()]] = {}

			l10nPopup = l10nWidget(self.sender(),current_sw.info[infos[self.sender()]],self)
			l10nPopup.show()

class l10nButton(QToolButton):
	def __init__(self, parent=None):
		super(l10nButton, self).__init__(parent)
		self.setCheckable(True)
		self.setText('l10n')

class l10nItem(QWidget):
	def __init__(self, lang='', text='', long=False, parent=None):
		super(l10nItem, self).__init__(parent)
		
		self.lang = lang
		self.text = text
		self.parent = parent
		
		layout = QHBoxLayout()
		layout.setContentsMargins(0,0,0,0)
		self.langEdit = QLineEdit(lang)
		self.langEdit.setFixedWidth(50)
		if long:
			self.textEdit = QTextEdit()
		else:
			self.textEdit = QLineEdit()
		self.textEdit.setText(text)
		delLoc = QPushButton('-')
		delLoc.setFixedWidth(delLoc.sizeHint().height())
		layout.addWidget(self.langEdit,0,Qt.AlignTop)
		layout.addWidget(self.textEdit,0,Qt.AlignTop)
		layout.addWidget(delLoc,0,Qt.AlignTop)
		self.setLayout(layout)

		self.connect(self.langEdit,
				SIGNAL("editingFinished()"), self.langEdited)
		self.connect(self.textEdit,
				SIGNAL("textChanged(QString)"), self.textEdited)
		self.connect(self.textEdit,
				SIGNAL("textChanged()"), self.textEdited)
		self.connect(delLoc,
				SIGNAL("clicked()"), self.delLoc)

	def langEdited(self):
		if (unicode(self.langEdit.text()) != self.lang) and (unicode(self.langEdit.text()) not in self.parent.info) and (unicode(self.langEdit.text()) > ''):
			if self.lang > '':
				del self.parent.info[self.lang]
			self.textEdited()
			self.lang = unicode(self.langEdit.text())
			self.parent.caller.setStyleSheet("l10nButton { font: bold }")
		else:
			self.langEdit.setText(self.lang)

	def textEdited(self):
		if isinstance(self.textEdit,QTextEdit):
			text = self.textEdit.toPlainText()
		else:
			text = self.textEdit.text()
		self.parent.info[unicode(self.langEdit.text())] = unicode(text)

	def delLoc(self):
		if self.langEdit.text() > '':
			del self.parent.info[unicode(self.langEdit.text())]
		self.parent.l10nList.removeWidget(self)
		self.setParent(None)
		if self.parent.l10nList.count() == 0:
			self.parent.caller.setStyleSheet("l10nButton { font: normal }")

class l10nWidget(QWidget):
	def __init__(self, caller, info, parent=None):
		super(l10nWidget, self).__init__(parent)
		self.setWindowFlags(Qt.Popup)
		
		self.caller = caller
		self.info = info
		
		list = QWidget()
		self.l10nList = QVBoxLayout()
		self.l10nList.setContentsMargins(0,0,0,0)
		list.setLayout(self.l10nList)

		addButton = QPushButton(_('Add localization'))
		scrollArea = QScrollArea()
		scrollArea.setWidget(list)
		scrollArea.setContentsMargins(0,0,0,0)
		scrollArea.setWidgetResizable(True)
		layout = QVBoxLayout()
		layout.addWidget(addButton)
		layout.addWidget(scrollArea)
		self.setLayout(layout)

		screen = QApplication.desktop().availableGeometry(caller)

		x = caller.mapToGlobal(QPoint(0,0)).x() + caller.rect().width()
		y = caller.mapToGlobal(QPoint(0,0)).y()
		sh = QSize(300,150)

		self.resize(sh)
		if y + sh.height() > screen.height():
			y = y - sh.height() + caller.rect().height()
		if x + sh.width() > screen.width():
			x = x - caller.rect().width() - sh.width()
		self.move(QPoint(x,y))

		for lang in info:
			if lang != 0:
				self.l10nList.addWidget(l10nItem(lang,info[lang],long=(self.caller in (self.parent().l10nDescription,self.parent().l10nLicense)),parent=self))

		self.connect(addButton,
				SIGNAL("clicked()"), self.addItem)

	def addItem(self):
		self.l10nList.addWidget(l10nItem(long=(self.caller in (self.parent().l10nDescription,self.parent().l10nLicense)),parent=self))
		
	def paintEvent(self, e):
		p = QPainter(self)
		frame = QStyleOptionFrame()
		frame.rect = self.rect()
		frame.palette = self.palette()
		frame.state = QStyle.State_None
		frame.lineWidth = self.style().pixelMetric(QStyle.PM_MenuPanelWidth)
		frame.midLineWidth = 0
		self.style().drawPrimitive(QStyle.PE_FrameMenu, frame, p, self)

	def hideEvent(self, e):
		self.caller.setDown(False)
		
class MainWindow(QMainWindow):
	def __init__(self, file=False, parent=None):
		super(MainWindow, self).__init__(parent)
		
		self.setWindowTitle('SwatchBooker')
		self.setWindowIcon(QIcon(swatchbooker_svg))
		
		self.filename = False
		self.codec = False

		self.sbWidget = QSplitter(Qt.Horizontal)
		# sbInfo
		nameLabel = QLabel(_("Name:"))
		self.sbName = QLineEdit()
		self.l10nName = l10nButton()
		descriptionLabel = QLabel(_("Description:"))
		self.sbDescription = QTextEdit()
		self.l10nDescription = l10nButton()
		copyrightLabel = QLabel(_("Copyright:"))
		self.copyright = QLineEdit()
		self.l10nCopyright = l10nButton()
		versionLabel = QLabel(_("Version:"))
		self.version = QLineEdit()
		licenseLabel = QLabel(_("License:"))
		self.sbLicense = QTextEdit()
		self.l10nLicense = l10nButton()
		
		groupBoxInfo1 = QGroupBox(_("Information"))
		sbInfo1 = QGridLayout()
		sbInfo1.addWidget(nameLabel, 0, 0)
		sbInfo1.addWidget(self.sbName, 0, 1)
		sbInfo1.addWidget(self.l10nName, 0, 2)
		sbInfo1.addWidget(descriptionLabel, 1, 0, 1, 2)
		sbInfo1.addWidget(self.sbDescription, 2, 0, 1, 2)
		sbInfo1.addWidget(self.l10nDescription, 2, 2, Qt.AlignTop)
		sbInfo1.addWidget(copyrightLabel, 3, 0)
		sbInfo1.addWidget(self.copyright, 3, 1)
		sbInfo1.addWidget(self.l10nCopyright, 3, 2)
		sbInfo1.addWidget(versionLabel, 4, 0)
		sbInfo1.addWidget(self.version, 4, 1, 1, 2)
		sbInfo1.addWidget(licenseLabel, 5, 0, 1, 2)
		sbInfo1.addWidget(self.sbLicense, 6, 0, 1, 2)
		sbInfo1.addWidget(self.l10nLicense, 6, 2, Qt.AlignTop)


		self.sbProfiles = QTableWidget()
		self.sbProfiles.horizontalHeader().setStretchLastSection(True)
		self.sbProfiles.verticalHeader().hide()
		self.sbProfiles.horizontalHeader().hide()
		self.sbProfiles.setColumnCount(2)
		self.sbProfiles.setColumnHidden(1,True)
		self.sbProfiles.setEditTriggers(QAbstractItemView.NoEditTriggers)
		self.butProf = QToolButton(self)
		self.butProf.setFixedSize(12,12)
		self.butProf.setArrowType(Qt.DownArrow)
		self.butProf.setStyleSheet("QToolButton::menu-indicator {image: none;}")
		self.menuProf = QMenu()
		self.menuProf.addAction(_('Add'),self.addProfile)
		self.profRemoveAction = self.menuProf.addAction(_('Remove'),self.remProfile)
		self.butProf.setPopupMode(QToolButton.InstantPopup)
		self.butProf.setMenu(self.menuProf)
		self.profRemoveAction.setEnabled(False)

		groupBoxInfo2 = QGroupBox(_("Color profiles"))
		sbInfo2 = QHBoxLayout()
		sbInfo2.addWidget(self.sbProfiles)
		sbInfo2.addWidget(self.butProf,0,Qt.AlignTop)

		sbInfo = QVBoxLayout()
		sbInfo.setContentsMargins(0,0,0,0)
		groupBoxInfo1.setLayout(sbInfo1)
		groupBoxInfo2.setLayout(sbInfo2)
		sbInfo.addWidget(groupBoxInfo1)
		sbInfo.addWidget(groupBoxInfo2)
		sbInfoWidget = QWidget()
		sbInfoWidget.setLayout(sbInfo)
		
		self.sbWidget.addWidget(sbInfoWidget)

		# sbTree
		self.treeWidget = sbTreeWidget()
		self.swnbLabel = QLabel()
		self.swEditBut = QToolButton(self)
		self.swEditBut.setMaximumSize(12,12)
		self.swEditBut.setArrowType(Qt.DownArrow)
		self.swEditBut.setStyleSheet("QToolButton::menu-indicator {image: none;}")
		self.swEditMenu = QMenu()
		self.swEditMenu.addAction(_('Add Color'),self.swAddColor)
		self.swEditMenu.addAction(_('Add Spacer'),self.swAddSpacer)
		self.swEditMenu.addAction(_('Add Break'),self.swAddBreak)
		self.swEditMenu.addAction(_('Add Group'),self.swAddGroup)
		self.deleteAction = self.swEditMenu.addAction(_('Delete'),self.swDelete)
		self.swEditBut.setPopupMode(QToolButton.InstantPopup)
		self.swEditBut.setMenu(self.swEditMenu)
		self.deleteAction.setEnabled(False)
		
		groupBoxTree = QGroupBox(_("Tree view"))
		sbTree = QGridLayout()
		sbTree.addWidget(self.treeWidget,0,0,1,2)
		sbTree.addWidget(self.swnbLabel,1,0)
		sbTree.addWidget(self.swEditBut,1,1)
		groupBoxTree.setLayout(sbTree)
		self.sbWidget.addWidget(groupBoxTree)

		# sbGrid
		self.listWidget = sbListWidget()
		colsLabel = QLabel(_("Columns:"))
		self.cols = QSpinBox()
		self.cols.setRange(0, 64)
		rowsLabel = QLabel(_("Rows:"))
		self.rows = QSpinBox()
		self.rows.setRange(0, 64)

		groupBoxGrid = QGroupBox(_("Grid view"))
		sbGrid = QVBoxLayout()
		dims = QGridLayout()
		dims.addWidget(colsLabel, 0, 0)
		dims.addWidget(self.cols, 0, 1)
		dims.addWidget(rowsLabel, 1, 0)
		dims.addWidget(self.rows, 1, 1)
		dimsWidget = QWidget()
		dimsWidget.setLayout(dims)
		sbGrid.addWidget(self.listWidget)
		sbGrid.addStretch()
		sbGrid.addWidget(dimsWidget)
		groupBoxGrid.setLayout(sbGrid)
		self.sbWidget.addWidget(groupBoxGrid)

		self.setCentralWidget(self.sbWidget)

		self.fileMenu = self.menuBar().addMenu(_("&File"))
		self.menuBar().addAction(_("Settings"), self.settings)
		self.menuBar().addAction(_("&About"), self.about)
		self.updateFileMenu()
		
		# Actions
		self.connect(self.sbName,
				SIGNAL("textEdited(QString)"), self.sb_edit)
		self.connect(self.sbDescription,
				SIGNAL("textChanged()"), self.sb_edit)
		self.connect(self.copyright,
				SIGNAL("textEdited(QString)"), self.sb_edit)
		self.connect(self.sbLicense,
				SIGNAL("textChanged()"), self.sb_edit)
		self.connect(self.version,
				SIGNAL("textEdited(QString)"), self.sb_edit)
		self.connect(self.cols,
				SIGNAL("valueChanged(int)"), self.sb_edit)
		self.connect(self.rows,
				SIGNAL("valueChanged(int)"), self.sb_edit)
		self.connect(self.treeWidget,
				SIGNAL("itemSelectionChanged()"), self.sw_display_tree)
		self.connect(self.listWidget,
				SIGNAL("itemSelectionChanged()"), self.sw_display_list)
		self.connect(self.sbProfiles,
				SIGNAL("itemSelectionChanged()"),self.prof_editable)
		self.connect(self.l10nName,
				SIGNAL("pressed()"), self.sb_l10n)
		self.connect(self.l10nDescription,
				SIGNAL("pressed()"), self.sb_l10n)
		self.connect(self.l10nCopyright,
				SIGNAL("pressed()"), self.sb_l10n)
		self.connect(self.l10nLicense,
				SIGNAL("pressed()"), self.sb_l10n)

		#Initialisation
		self.sb = SwatchBook()
		if file:
			self.loadFile(file)
		else:
			self.sb_flush()

	def sw_display_tree(self):
		global current_sw
		if self.treeWidget.selectedItems():
			treeItem = self.treeWidget.selectedItems()[0]
			current_sw = item = self.treeItems[treeItem]
			if item and not isinstance(item,Group):
				self.listWidget.setCurrentItem(self.itemList[item])
			else:
				self.listWidget.setCurrentItem(None)
			if hasattr(self,'sbSwatch'):
				self.sbSwatch.setParent(None)
			if isinstance(item,Color):
				self.sbSwatch = ColorWidget(self)
			elif isinstance(item,Group):
				self.sbSwatch = GroupWidget(self)
			if not isinstance(item, Spacer) and not isinstance(item, Break) and not isinstance(self.treeWidget.selectedItems()[0], noChild):
				self.sbWidget.addWidget(self.sbSwatch)
			if isinstance(self.treeWidget.selectedItems()[0], noChild):
				self.deleteAction.setEnabled(False)
			else:
				self.deleteAction.setEnabled(True)

	def sw_display_list(self):
		global current_sw
		if self.listWidget.selectedItems():
			listItem = self.listWidget.selectedItems()[0]
			current_sw = item = self.listItems[listItem]
			self.treeWidget.setCurrentItem(self.itemTree[item])

	def sb_edit(self):
		if self.sbName.text() > '':
			if 'name' not in self.sb.info:
				self.sb.info['name'] = {}
			self.sb.info['name'][0] = unicode(self.sbName.text())
		if self.sbDescription.toPlainText() > '':
			if 'description' not in self.sb.info:
				self.sb.info['description'] = {}
			self.sb.info['description'][0] = unicode(self.sbDescription.toPlainText())
		if self.copyright.text() > '':
			if 'copyright' not in self.sb.info:
				self.sb.info['copyright'] = {}
			self.sb.info['copyright'][0] = unicode(self.copyright.text())
		if self.sbLicense.toPlainText() > '':
			if 'license' not in self.sb.info:
				self.sb.info['license'] = {}
			self.sb.info['license'][0] = unicode(self.sbLicense.toPlainText())
		if self.version.text() > '':
			self.sb.info['version'] = unicode(self.version.text())
		if self.cols.value() > 0:
			self.sb.display['columns'] = self.cols.value()
			self.listWidget.setFixedWidth(self.sb.display['columns']*17 + self.listWidget.zWidth)
		elif self.cols.value() == 0:
			self.listWidget.setMinimumWidth(0)
			self.listWidget.setMaximumWidth(0xFFFFFF)
		if self.rows.value() > 0:
			self.sb.display['rows'] = self.rows.value()
			self.listWidget.setFixedHeight(self.sb.display['rows']*17 + self.listWidget.zHeight)
		elif self.rows.value() == 0:
			self.listWidget.setMinimumHeight(0)
			self.listWidget.setMaximumHeight(0xFFFFFF)

	def fileNew(self):
		self.sb_flush()
		self.sb = SwatchBook()

	def webOpen(self):
		dialog = webOpenDlg(self)
		if dialog.exec_():
			self.sb_flush()
			self.sb = SwatchBook(websvc=dialog.svc,webid=dialog.id)
			if 'name' in self.sb.info:
				self.sbName.setText(self.sb.info['name'][0])
			if 'description' in self.sb.info:
				self.sbDescription.setText(self.sb.info['description'][0])
			if 'copyright' in self.sb.info:
				self.copyright.setText(self.sb.info['copyright'][0])
			if 'license' in self.sb.info:
				self.sbLicense.setText(self.sb.info['license'][0])
			if 'version' in self.sb.info:
				self.version.setText(self.sb.info['version'])
			if 'columns' in self.sb.display:
				self.cols.setValue(self.sb.display['columns'])
				self.listWidget.setFixedWidth(self.sb.display['columns']*17 + self.listWidget.zWidth)
			if 'rows' in self.sb.display:
				self.rows.setValue(self.sb.display['rows'])
				self.listWidget.setFixedHeight(self.sb.display['rows']*17 + self.listWidget.zHeight)
			self.populateTree()

	def fileOpen(self):
		dir = os.path.dirname(self.filename) \
				if self.filename else "."
		import swatchbook.codecs as codecs
		filetypes = []
		for codec in codecs.reads:
			codec_exts = []
			for ext in eval('codecs.'+codec).ext:
				codec_exts.append('*.'+ext)
			codec_txt = eval('codecs.'+codec).__doc__ +' ('+" ".join(codec_exts)+')'
			filetypes.append(codec_txt)
		allexts = ["*.%s" % unicode(format).lower() \
				   for format in codecs.readexts.keys()]
		fname = unicode(QFileDialog.getOpenFileName(self,
							_("Choose file"), dir,
							(unicode(_("All supported files (%s)")) % " ".join(allexts))+";;"+(";;".join(sorted(filetypes)))+_(";;All files (*)")))
		if fname:
			self.loadFile(fname)

	def sb_flush(self):
		global breaks
		breaks = []
		self.filename = False
		self.sbName.clear()
		self.sbDescription.clear()
		self.copyright.clear()
		self.version.clear()
		self.sbLicense.clear()
		self.l10nName.setStyleSheet("l10nButton { font: normal }")
		self.l10nDescription.setStyleSheet("l10nButton { font: normal }")
		self.l10nCopyright.setStyleSheet("l10nButton { font: normal }")
		self.l10nLicense.setStyleSheet("l10nButton { font: normal }")
		self.cols.setValue(0)
		self.cols.clear()
		self.rows.setValue(0)
		self.rows.clear()
		self.treeWidget.clear()
		self.listWidget.clear()
		self.listWidget.setMinimumSize(QSize(0,0))
		self.listWidget.setMaximumSize(QSize(0xFFFFFF,0xFFFFFF))
		self.treeItems = {}
		self.itemTree = {}
		self.listItems = {}
		self.itemList = {}
		self.profiles = {}
		self.sbProfiles.clear()
		self.sbProfiles.setRowCount(0)
		self.swnb = 0
		self.swnbLabel.clear()
		self.deleteAction.setEnabled(False)
		if hasattr(self,'sbSwatch'):
			self.sbSwatch.setParent(None)
		current_sw = False
		current_sp = False
		self.updSwatchCount()

	def sb_l10n(self):
		if not self.sender().isChecked():
			infos = {self.l10nName: 'name', self.l10nDescription: 'description', self.l10nCopyright: 'copyright', self.l10nLicense: 'license' }
			if infos[self.sender()] not in self.sb.info:
				self.sb.info[infos[self.sender()]] = {}

			l10nPopup = l10nWidget(self.sender(),self.sb.info[infos[self.sender()]],self)
			l10nPopup.show()

	def loadFile(self, fname=None):
		if fname:
			self.sb_flush()
			self.updateFileMenu(fname)
			self.sb = SwatchBook(fname)
			self.filename = fname
			if 'name' in self.sb.info:
				info = self.sb.info['name'].copy()
				if 0 in info:
					self.sbName.setText(self.sb.info['name'][0])
					del info[0]
				if len(info) > 0:
					self.l10nName.setStyleSheet("l10nButton { font: bold }")
			if 'description' in self.sb.info:
				info = self.sb.info['description'].copy()
				if 0 in info:
					self.sbDescription.setText(self.sb.info['description'][0])
					del info[0]
				if len(info) > 0:
					self.l10nDescription.setStyleSheet("l10nButton { font: bold }")
			if 'copyright' in self.sb.info:
				info = self.sb.info['copyright'].copy()
				if 0 in info:
					self.copyright.setText(self.sb.info['copyright'][0])
					del info[0]
				if len(info) > 0:
					self.l10nCopyright.setStyleSheet("l10nButton { font: bold }")
			if 'license' in self.sb.info:
				info = self.sb.info['license'].copy()
				if 0 in info:
					self.sbLicense.setText(self.sb.info['license'][0])
					del info[0]
				if len(info) > 0:
					self.l10nLicense.setStyleSheet("l10nButton { font: bold }")
			if 'version' in self.sb.info:
				self.version.setText(self.sb.info['version'])
			if 'columns' in self.sb.display:
				self.cols.setValue(self.sb.display['columns'])
				self.listWidget.setFixedWidth(self.sb.display['columns']*17 + self.listWidget.zWidth)
			if 'rows' in self.sb.display:
				self.rows.setValue(self.sb.display['rows'])
				self.listWidget.setFixedHeight(self.sb.display['rows']*17 + self.listWidget.zHeight)
			self.sbProfiles.setRowCount(len(self.sb.profiles))
			row = 0
			for prof in self.sb.profiles:
				profItemID = QTableWidgetItem(prof)
				profItemTitle = QTableWidgetItem(self.sb.profiles[prof].info['desc'][0])
				cprt = self.sb.profiles[prof].info['cprt']
				if 0 in cprt:
					profItemTitle.setToolTip(cprt[0])
				elif 'en_US' in cprt:
					profItemTitle.setToolTip(cprt['en_US'])
				self.sbProfiles.setItem(row, 0, profItemTitle)
				self.sbProfiles.setItem(row, 1, profItemID)
				space = self.sb.profiles[prof].info['space'].strip()
				if space in self.profiles:
					self.profiles[space].append(prof)
				else:
					self.profiles[space] = [prof]
				row += 1
			self.populateTree()

	def fileSave(self,codec):
		if self.filename:
			self.sb.write(codec,self.filename)
		else:
			self.fileSaveAs()

	def fileSaveAs(self):
		import swatchbook.codecs as codecs
		filetypes = {}
		for codec in codecs.writes:
			codec_exts = []
			for ext in eval('codecs.'+codec).ext:
				codec_exts.append('*.'+ext)
			codec_txt = eval('codecs.'+codec).__doc__ +' ('+" ".join(codec_exts)+')'
			filetypes[codec_txt] = (codec,eval('codecs.'+codec).ext[0])
		fname = self.filename or "."
		filetype = QString()
		fname = unicode(QFileDialog.getSaveFileName(self,
						_("Save file"), fname,
						";;".join(filetypes.keys()),filetype))
		if fname:
			if len(fname.rsplit(".",1)) == 1 or (len(fname.rsplit(".",1)) > 1 and fname.rsplit(".",1)[1] != filetypes[unicode(filetype)][1]):
				fname += "."+filetypes[unicode(filetype)][1]
			self.filename = fname
			self.fileSave(filetypes[unicode(filetype)][0])
			self.updateFileMenu(fname)

	def populateTree(self):
		self.fillTree(self.sb.items)
		self.treeWidget.resizeColumnToContents(0)
		self.treeWidget.resizeColumnToContents(1)
		self.updSwatchCount()

	def fillTree(self,items,group = False):
		for item in items.values():
			if group:
				parent = group
			else:
				parent = self.treeWidget
			if isinstance(item,Group):
				treeItem = treeItemGroup(item,parent)
				if len(item.items) > 0:
					self.fillTree(item.items,treeItem)
				else:
					nochild = noChild()
					treeItem.addChild(nochild)
					self.treeItems[nochild] = None
			elif isinstance(item,Spacer):
				treeItem = treeItemSpacer(parent)
				listItem = listItemSpacer(self.listWidget)
				self.listItems[listItem] = item
				self.itemList[item] = listItem
			elif isinstance(item,Break):
				treeItem = treeItemBreak(parent)
				listItem = listItemBreak(self.listWidget)
				self.listItems[listItem] = item
				self.itemList[item] = listItem
			else:
				treeItem = treeItemColor(item,parent)
				listItem = listItemColor(item,self.listWidget)
				self.listItems[listItem] = item
				self.itemList[item] = listItem
			self.treeItems[treeItem] = item
			self.itemTree[item] = treeItem
			if group:
				self.treeWidget.expandItem(parent)
			if item.__class__.__name__ not in ('Group', 'Spacer', 'Break'):
				self.swnb += 1
		self.listWidget.update()

	@staticmethod
	def colorswatch(swatch):
		if swatch and swatch.toRGB8():
			prof_out = settings.value("DisplayProfile").toString() or False
			r,g,b = swatch.toRGB8(prof_out)
			pix = QPixmap(16,16)
			pix.fill(Qt.transparent)
			paint = QPainter()
			paint.begin(pix)
			paint.setBrush(QColor(r,g,b))
			if 'spot' in swatch.attr:
				paint.drawEllipse(0, 0, 15, 15)
			else:
				paint.drawRect(0, 0, 15, 15)
			paint.end()
			icon = QIcon(pix)
			paint.begin(pix)
			paint.setPen(QColor(255,255,255))
			if 'spot' in swatch.attr:
				paint.drawEllipse(0, 0, 15, 15)
			else:
				paint.drawRect(0, 0, 15, 15)
			paint.setPen(Qt.DotLine)
			if 'spot' in swatch.attr:
				paint.drawEllipse(0, 0, 15, 15)
			else:
				paint.drawRect(0, 0, 15, 15)
			paint.end()
			icon.addPixmap(pix,QIcon.Selected)
			return icon

	@staticmethod
	def emptyswatch():
		pix = QPixmap(16,16)
		pix.fill(Qt.transparent)
		paint = QPainter()
		paint.begin(pix)
		paint.setPen(QPen(QColor(218,218,218),3.0))
		paint.drawLine(QLine(3, 3, 12, 12))
		paint.drawLine(QLine(12, 3, 3, 12))
		paint.end()
		icon = QIcon(pix)
		paint.begin(pix)
		paint.setPen(QColor(255,255,255))
		paint.drawRect(0, 0, 15, 15)
		paint.setPen(Qt.DotLine)
		paint.drawRect(0, 0, 15, 15)
		paint.end()
		icon.addPixmap(pix,QIcon.Selected)
		return icon

	def about(self):
		QMessageBox.about(self, _("About SwatchBooker"),
                """<b>SwatchBooker</b> %s
                <p>&copy; 2008 Olivier Berten
                <p>Qt %s - PyQt %s""" % (
                __version__, QT_VERSION_STR, PYQT_VERSION_STR))

	def settings(self):
		dialog = SettingsDlg(self)
		if dialog.exec_():
			if dialog.returnDisProf():
				settings.setValue("DisplayProfile",QVariant(dialog.returnDisProf()))
			else:
				settings.remove("DisplayProfile")
			if dialog.returnCMYKProf():
				settings.setValue("CMYKProfile",QVariant(dialog.returnCMYKProf()))
			else:
				settings.remove("CMYKProfile")
			settings.setValue("MaxRecentFiles",QVariant(dialog.RecFilesSpin.value()))
			if dialog.lang:
				settings.setValue("Language",dialog.lang)
			else:
				settings.remove("Language")
			self.updateFileMenu()

	def swDelete(self):
		global current_sw
		sw_tbd = current_sw
		current_sw = False
		if hasattr(self,'sbSwatch'):
			self.sbSwatch.setParent(None)
		self.deleteAction.setEnabled(False)
		tbd = self.get_parent(sw_tbd)
		if isinstance(sw_tbd, Group):
			self.del_group_from_list(tbd[0],tbd[1])
		else:
			if isinstance(sw_tbd, Break):
				global breaks
				breaks.remove(self.itemList[sw_tbd])
			self.listWidget.takeItem(self.listWidget.row(self.itemList[sw_tbd]))
			del self.itemList[sw_tbd]
			self.swnb -= 1
		del tbd[0].items[tbd[1]]
		del self.sb.ids[tbd[1]]
		if self.itemTree[sw_tbd].parent() == None:
			self.treeWidget.takeTopLevelItem(self.treeWidget.indexOfTopLevelItem(self.itemTree[sw_tbd]))
		else:
			tParent = self.itemTree[sw_tbd].parent()
			tParent.takeChild(self.itemTree[sw_tbd].parent().indexOfChild(self.itemTree[sw_tbd]))
			if tParent.childCount() == 0:
				nochild = noChild()
				tParent.addChild(nochild)
				self.treeItems[nochild] = None
		del self.itemTree[sw_tbd]
		self.updSwatchCount()
		self.listWidget.update()
	
	def del_group_from_list(self,parent,group):
		for sw in parent.items[group].items:
			if isinstance(parent.items[group].items[sw], Group):
				self.del_group_from_list(parent.items[group],sw)
			else:
				self.listWidget.takeItem(self.listWidget.row(self.itemList[parent.items[group].items[sw]]))
				del self.itemList[parent.items[group].items[sw]]
				if parent.items[group].items[sw].__class__.__name__ not in ('Group','Spacer','Break'):
					self.swnb -= 1
			del self.sb.ids[sw]
	
	def get_parent(self,value):
		for item in self.sb.ids:
			if self.sb.ids[item][0] == value:
				return (self.sb.ids[item][1],item)
		return False

	def listitemforadd(self,treeItem):
		item = self.treeItems[treeItem]
		if isinstance(treeItem,noChild):
			treeItem = treeItem.parent()
			if treeItem.parent() == None:
				index = self.treeWidget.indexOfTopLevelItem(treeItem)
				if index > 0:
					return self.treeWidget.topLevelItem(index-1)
				else:
					return False
			else:
				index = treeItem.parent().indexOfChild(treeItem)
				return treeItem.parent().child(index-1)
		elif isinstance(item,Group):
			if len(item.items) > 0:
				return treeItem.child(treeItem.childCount()-1)
			else:
				if treeItem.parent() == None:
					index = self.treeWidget.indexOfTopLevelItem(treeItem)
					if index > 0:
						return self.treeWidget.topLevelItem(index-1)
					else:
						return False
				else:
					index = treeItem.parent().indexOfChild(treeItem)
					return treeItem.parent().child(index-1)
		else:
			return treeItem

	def swAddColor(self):
		global current_sw
		item = Color(self.sb)
		key = 'col'+str(int(time.mktime(time.gmtime())))
		if key in self.sb.ids:
			#sys.stderr.write('duplicate id ['+key+']\n')
			key = key+str(item)
		listItem = listItemColor(item)
		self.listItems[listItem] = item
		self.itemList[item] = listItem
		treeItem = treeItemColor(item)
		self.treeItems[treeItem] = item
		self.itemTree[item] = treeItem
		if self.treeWidget.selectedItems():
			selTItem = self.treeWidget.selectedItems()[0]
			if not isinstance(selTItem,noChild):
				selItem = self.get_parent(current_sw)
				index = selItem[0].items.values().index(current_sw)
				selItem[0].items.insert(index+1,key,item)
				self.sb.ids[key] = (item,selItem[0])
			else:
				selItem = self.treeItems[selTItem.parent()]
				selItem.items.insert(0,key,item)
				self.sb.ids[key] = (item,selItem)
			if selTItem.parent() == None:
				tIndex = self.treeWidget.indexOfTopLevelItem(selTItem)
				self.treeWidget.insertTopLevelItem(tIndex+1, treeItem)
			else:
				tIndex = selTItem.parent().indexOfChild(selTItem)
				selTItem.parent().insertChild(tIndex+1,treeItem)
				if isinstance(selTItem,noChild):
					current_sw = self.treeItems[selTItem.parent()]
			if not isinstance(current_sw,Group):
				selLItem = self.listWidget.selectedItems()[0]
			else:
				nitem = selTItem
				while nitem and (isinstance(self.treeItems[nitem],Group) or isinstance(nitem,noChild)):
					nitem = self.listitemforadd(nitem)
				if nitem and self.treeItems[nitem]:
					selLItem = self.itemList[self.treeItems[nitem]]
				else:
					selLItem = False
			if selLItem:
				lIndex = self.listWidget.indexFromItem(selLItem).row()
				self.listWidget.insertItem(lIndex+1,self.itemList[item])
			else:
				self.listWidget.addItem(self.itemList[item])
			if isinstance(selTItem,noChild):
				selTItem.parent().takeChild(0)
		else:
			self.sb.items[key] = item
			self.sb.ids[key] = (item,self.sb)
			self.treeWidget.addTopLevelItem(self.itemTree[item])
			self.listWidget.addItem(self.itemList[item])
		self.treeWidget.setCurrentItem(self.itemTree[item])
		self.swnb += 1
		self.updSwatchCount()
		self.listWidget.update()
		current_sw = item

	def swAddGroup(self):
		global current_sw
		item = Group()
		key = 'gr'+str(int(time.mktime(time.gmtime())))
		if key in self.sb.ids:
			#sys.stderr.write('duplicate id ['+key+']\n')
			key = key+str(item)
		treeItem = treeItemGroup(item)
		nochild = noChild()
		treeItem.addChild(nochild)
		self.treeItems[nochild] = None
		self.treeItems[treeItem] = item
		self.itemTree[item] = treeItem
		if self.treeWidget.selectedItems():
			selTItem = self.treeWidget.selectedItems()[0]
			if not isinstance(selTItem,noChild):
				selItem = self.get_parent(current_sw)
				index = selItem[0].items.values().index(current_sw)
				selItem[0].items.insert(index+1,key,item)
				self.sb.ids[key] = (item,selItem[0])
			else:
				selItem = self.treeItems[selTItem.parent()]
				selItem.items.insert(0,key,item)
				self.sb.ids[key] = (item,selItem)
			if selTItem.parent() == None:
				tIndex = self.treeWidget.indexOfTopLevelItem(selTItem)
				self.treeWidget.insertTopLevelItem(tIndex+1, treeItem)
			else:
				tIndex = selTItem.parent().indexOfChild(selTItem)
				selTItem.parent().insertChild(tIndex+1,treeItem)
			if isinstance(selTItem,noChild):
				selTItem.parent().takeChild(0)
		else:
			self.sb.items[key] = item
			self.sb.ids[key] = (item,self.sb)
			self.treeWidget.addTopLevelItem(self.itemTree[item])
		self.treeWidget.setCurrentItem(self.itemTree[item])
		self.listWidget.update()
		current_sw = item

	def swAddBreak(self):
		global current_sw
		item = Break()
		key = 'br'+str(int(time.mktime(time.gmtime())))
		if key in self.sb.ids:
			#sys.stderr.write('duplicate id ['+key+']\n')
			key = key+str(item)
		listItem = listItemBreak()
		self.listItems[listItem] = item
		self.itemList[item] = listItem
		treeItem = treeItemBreak()
		self.treeItems[treeItem] = item
		self.itemTree[item] = treeItem
		if self.treeWidget.selectedItems():
			selTItem = self.treeWidget.selectedItems()[0]
			if not isinstance(selTItem,noChild):
				selItem = self.get_parent(current_sw)
				index = selItem[0].items.values().index(current_sw)
				selItem[0].items.insert(index+1,key,item)
				self.sb.ids[key] = (item,selItem[0])
			else:
				selItem = self.treeItems[selTItem.parent()]
				selItem.items.insert(0,key,item)
				self.sb.ids[key] = (item,selItem)
			if selTItem.parent() == None:
				tIndex = self.treeWidget.indexOfTopLevelItem(selTItem)
				self.treeWidget.insertTopLevelItem(tIndex+1, treeItem)
			else:
				tIndex = selTItem.parent().indexOfChild(selTItem)
				selTItem.parent().insertChild(tIndex+1,treeItem)
				if isinstance(selTItem,noChild):
					current_sw = self.treeItems[selTItem.parent()]
			if not isinstance(current_sw,Group):
				selLItem = self.listWidget.selectedItems()[0]
			else:
				nitem = selTItem
				while nitem and (isinstance(self.treeItems[nitem],Group) or isinstance(nitem,noChild)):
					nitem = self.listitemforadd(nitem)
				if nitem and self.treeItems[nitem]:
					selLItem = self.itemList[self.treeItems[nitem]]
				else:
					selLItem = False
			if selLItem:
				lIndex = self.listWidget.indexFromItem(selLItem).row()
				self.listWidget.insertItem(lIndex+1,self.itemList[item])
			else:
				self.listWidget.addItem(self.itemList[item])
			if isinstance(selTItem,noChild):
				selTItem.parent().takeChild(0)
		else:
			self.sb.items[key] = item
			self.sb.ids[key] = (item,self.sb)
			self.treeWidget.addTopLevelItem(self.itemTree[item])
			self.listWidget.addItem(self.itemList[item])
		self.treeWidget.setCurrentItem(self.itemTree[item])
		self.listWidget.update()

	def swAddSpacer(self):
		global current_sw
		item = Spacer()
		key = 'sp'+str(int(time.mktime(time.gmtime())))
		if key in self.sb.ids:
			#sys.stderr.write('duplicate id ['+key+']\n')
			key = key+str(item)
		listItem = listItemSpacer()
		self.listItems[listItem] = item
		self.itemList[item] = listItem
		treeItem = treeItemSpacer()
		self.treeItems[treeItem] = item
		self.itemTree[item] = treeItem
		if self.treeWidget.selectedItems():
			selTItem = self.treeWidget.selectedItems()[0]
			if not isinstance(selTItem,noChild):
				selItem = self.get_parent(current_sw)
				index = selItem[0].items.values().index(current_sw)
				selItem[0].items.insert(index+1,key,item)
				self.sb.ids[key] = (item,selItem[0])
			else:
				selItem = self.treeItems[selTItem.parent()]
				selItem.items.insert(0,key,item)
				self.sb.ids[key] = (item,selItem)
			if selTItem.parent() == None:
				tIndex = self.treeWidget.indexOfTopLevelItem(selTItem)
				self.treeWidget.insertTopLevelItem(tIndex+1, treeItem)
			else:
				tIndex = selTItem.parent().indexOfChild(selTItem)
				selTItem.parent().insertChild(tIndex+1,treeItem)
				if isinstance(selTItem,noChild):
					current_sw = self.treeItems[selTItem.parent()]
			if not isinstance(current_sw,Group):
				selLItem = self.listWidget.selectedItems()[0]
			else:
				nitem = selTItem
				while nitem and (isinstance(self.treeItems[nitem],Group) or isinstance(nitem,noChild)):
					nitem = self.listitemforadd(nitem)
				if nitem and self.treeItems[nitem]:
					selLItem = self.itemList[self.treeItems[nitem]]
				else:
					selLItem = False
			if selLItem:
				lIndex = self.listWidget.indexFromItem(selLItem).row()
				self.listWidget.insertItem(lIndex+1,self.itemList[item])
			else:
				self.listWidget.addItem(self.itemList[item])
			if isinstance(selTItem,noChild):
				selTItem.parent().takeChild(0)
		else:
			self.sb.items[key] = item
			self.sb.ids[key] = (item,self.sb)
			self.treeWidget.addTopLevelItem(self.itemTree[item])
			self.listWidget.addItem(self.itemList[item])
		self.treeWidget.setCurrentItem(self.itemTree[item])
		self.listWidget.update()

	def updSwatchCount(self):
		self.swnbLabel.setText(n_('%s swatch','%s swatches',self.swnb) % self.swnb)

	def prof_editable(self):
		if self.sbProfiles.isItemSelected(self.sbProfiles.currentItem()):
			self.profRemoveAction.setEnabled(True)

	def addProfile(self):
		fname = unicode(QFileDialog.getOpenFileName(self,
							_("Choose file"), ".",
							(_("ICC profiles (*.icc *.icm)"))))
		if fname:
			# the next 6 lines are a workaround for the unability of lcms to deal with unicode file names
			fi = open(fname, 'rb')
			uri = tempfile.mkstemp()[1]
			fo = open(uri,'wb')
			fo.write(fi.read())
			fi.close()
			fo.close()
			import swatchbook.icc as icc
			profile = icc.ICCprofile(uri)
			#TODO: check if exists
			id = os.path.basename(fname)
			self.sb.profiles[id] = profile
			profItemID = QTableWidgetItem(id)
			profItemTitle = QTableWidgetItem(profile.info['desc'][0])
			cprt = profile.info['cprt']
			if 0 in cprt:
				profItemTitle.setToolTip(cprt[0])
			elif 'en_US' in cprt:
				profItemTitle.setToolTip(cprt['en_US'])
			row = self.sbProfiles.rowCount()
			self.sbProfiles.setRowCount(row+1)
			self.sbProfiles.setItem(row, 0, profItemTitle)
			self.sbProfiles.setItem(row, 1, profItemID)
			space = profile.info['space'].strip()
			if space in self.profiles:
				self.profiles[space].append(id)
			else:
				self.profiles[space] = [id]

	def remProfile(self):
		profid = unicode(self.sbProfiles.item(self.sbProfiles.currentItem().row(),1).text())
		self.sbProfiles.removeRow(self.sbProfiles.currentItem().row())
		self.profiles[self.sb.profiles[profid].info['space'].strip()].remove(profid)
		del self.sb.profiles[profid]
		self.profRemoveAction.setEnabled(False)
		# TODO remove profile from color values

	def updateFileMenu(self,fname=False):
		if not settings.contains("MaxRecentFiles"):
			settings.setValue("MaxRecentFiles",QVariant(6))
		files = settings.value("recentFileList").toStringList()
		for file in files:
			if not QFile.exists(file):
				files.removeAll(file)
		
		if fname:
			files.removeAll(fname)
			files.prepend(fname)
			while files.count() > settings.value("MaxRecentFiles").toInt()[0]:
				files.removeAt(files.count()-1)

		settings.setValue("recentFileList", QVariant(files))

		numRecentFiles = min(files.count(), settings.value("MaxRecentFiles").toInt()[0])

		recentFileActs = []
		
		for h in range(settings.value("MaxRecentFiles").toInt()[0]):
			recentFileActs.append(QAction(self))
			recentFileActs[h].setVisible(False)
			self.connect(recentFileActs[h], SIGNAL("triggered()"),
						 self.openRecentFile)

		for i in range(numRecentFiles):
			text = QString("&%1 %2").arg(i+1).arg(self.strippedName(files[i]))
			recentFileActs[i].setText(text)
			recentFileActs[i].setData(QVariant(files[i]))
			recentFileActs[i].setVisible(True)
			
		for j in range(numRecentFiles, settings.value("MaxRecentFiles").toInt()[0]):
			recentFileActs[j].setVisible(False)

		self.fileMenu.clear()
		self.fileMenu.addAction(_("&New"), self.fileNew, QKeySequence.New)
		self.fileMenu.addAction(_("&Open"), self.fileOpen, QKeySequence.Open)
		self.fileMenu.addAction(_("Open from web"), self.webOpen)
		self.fileMenu.addAction(_("&Save As..."), self.fileSaveAs, QKeySequence.Save)
		self.fileMenu.addSeparator()
		for k in range(settings.value("MaxRecentFiles").toInt()[0]):
			self.fileMenu.addAction(recentFileActs[k])

	def strippedName(self, fullFileName):
		return QFileInfo(fullFileName).fileName()

	def openRecentFile(self):
		action = self.sender()
		if action:
			self.loadFile(unicode(action.data().toString()))

class noChild(QTreeWidgetItem):
	def __init__(self, parent=None):
		super(noChild, self).__init__(parent)

		font = QFont()
		font.setItalic(True)
		self.setText(0,_('empty'))
		self.setFont(0,font)
		self.setTextColor(0,QColor(128,128,128))
		self.setFlags(self.flags() & ~(Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled))

class treeItemColor(QTreeWidgetItem):
	def __init__(self, item, parent=None):
		super(treeItemColor, self).__init__(parent)
		self.item = item
		self.update()
		self.setFlags(self.flags() & ~(Qt.ItemIsDropEnabled))

	def update(self):
		if self.item and 'name' in self.item.info and 0 in self.item.info['name']:
			self.setText(0,QString(self.item.info['name'][0]))
		else:
			self.setText(0,QString())
		self.setIcon(0,MainWindow.colorswatch(self.item) or MainWindow.emptyswatch())

class listItemColor(QListWidgetItem):
	def __init__(self, item, parent=None):
		super(listItemColor, self).__init__(parent)
		self.item = item
		self.setSizeHint(QSize(17,17))
		self.update()

	def update(self):
		if self.item and 'name' in self.item.info and 0 in self.item.info['name']:
			self.setToolTip(self.item.info['name'][0])
		else:
			self.setToolTip(QString())
		self.setIcon(MainWindow.colorswatch(self.item) or MainWindow.emptyswatch())

class treeItemGroup(QTreeWidgetItem):
	def __init__(self, item, parent=None):
		super(treeItemGroup, self).__init__(parent)
		self.item = item
		self.update()

	def update(self):
		if self.item and 'name' in self.item.info and 0 in self.item.info['name']:
			self.setText(0,QString(self.item.info['name'][0]))
		else:
			self.setText(0,QString())

	def childCount(self):
		if isinstance(self.child(0),noChild):
			return 0
		else:
			return QTreeWidgetItem.childCount(self)

class treeItemSpacer(QTreeWidgetItem):
	def __init__(self, parent=None):
		super(treeItemSpacer, self).__init__(parent)

		font = QFont()
		font.setItalic(True)
		self.setText(0,QString('<spacer>'))
		self.setFont(0,font)
		self.setTextColor(0,QColor(128,128,128))
		self.setFlags(self.flags() & ~(Qt.ItemIsDropEnabled))

class listItemSpacer(QListWidgetItem):
	def __init__(self, parent=None):
		super(listItemSpacer, self).__init__(parent)

		pix = QPixmap(1,1)
		pix.fill(Qt.transparent)
		self.setIcon(QIcon(pix))
		self.setSizeHint(QSize(17,17))
		self.setFlags(self.flags() & ~(Qt.ItemIsSelectable))

class treeItemBreak(QTreeWidgetItem):
	def __init__(self, parent=None):
		super(treeItemBreak, self).__init__(parent)

		font = QFont()
		font.setItalic(True)
		self.setText(0,QString('<break>'))
		self.setFont(0,font)
		self.setTextColor(0,QColor(128,128,128))
		self.setFlags(self.flags() & ~(Qt.ItemIsDropEnabled))

class listItemBreak(QListWidgetItem):
	def __init__(self, parent=None):
		super(listItemBreak, self).__init__(parent)

		global breaks
		breaks.append(self)
		pix = QPixmap(1,1)
		pix.fill(Qt.transparent)
		self.setIcon(QIcon(pix))
		self.setSizeHint(QSize(0,17))
		self.setFlags(self.flags() & ~(Qt.ItemIsSelectable))

class SettingsDlg(QDialog):
	def __init__(self, parent=None):
		super(SettingsDlg, self).__init__(parent)
		
		buttonBox = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)

		self.sRGB = QCheckBox("sRGB")
		self.RGBfileLabel = QLabel()
		self.RGBfileLabel.setFrameStyle(QFrame.StyledPanel|QFrame.Sunken)
		self.RGBfileButton = QPushButton(_("Choose file"))

		RGBfileLayout = QHBoxLayout()
		RGBfileLayout.addWidget(self.RGBfileLabel, 1)
		RGBfileLayout.addWidget(self.RGBfileButton)
		
		gDisProf = QGroupBox(_("Display Profile"))
		disprof = QVBoxLayout()
		disprof.addWidget(self.sRGB)
		disprof.addLayout(RGBfileLayout)
		gDisProf.setLayout(disprof)

		self.Fogra27L = QCheckBox("Fogra27L")
		self.CMYKfileLabel = QLabel()
		self.CMYKfileLabel.setFrameStyle(QFrame.StyledPanel|QFrame.Sunken)
		self.CMYKfileButton = QPushButton(_("Choose file"))

		CMYKfileLayout = QHBoxLayout()
		CMYKfileLayout.addWidget(self.CMYKfileLabel, 1)
		CMYKfileLayout.addWidget(self.CMYKfileButton)

		gCMYKProf = QGroupBox(_("Default CMYK Profile"))
		CMYKprof = QVBoxLayout()
		CMYKprof.addWidget(self.Fogra27L)
		CMYKprof.addLayout(CMYKfileLayout)
		gCMYKProf.setLayout(CMYKprof)

		self.RecFilesSpin = QSpinBox()
		self.RecFilesSpin.setRange(0, 12)

		gRecFiles = QGroupBox(_("Recent files"))
		RecFiles = QHBoxLayout()
		RecFiles.addWidget(QLabel(_("Number of files displayed:")))
		RecFiles.addWidget(self.RecFilesSpin)
		gRecFiles.setLayout(RecFiles)

		self.LangCombo = QComboBox()
		self.LangCombo.addItem(_('(default)'))
		for lang in sorted(availables_lang):
			self.LangCombo.addItem(availables_lang[lang],QVariant(lang))

		gLang = QGroupBox(_("Application language"))
		Lang = QHBoxLayout()
		Lang.addWidget(self.LangCombo)
		gLang.setLayout(Lang)

		sett = QVBoxLayout()
		sett.addWidget(gDisProf)
		sett.addWidget(gCMYKProf)
		sett.addWidget(gRecFiles)
		sett.addWidget(gLang)
		sett.addWidget(buttonBox)
		self.setLayout(sett)

		if settings.contains("DisplayProfile"):
			self.RGBfname = settings.value("DisplayProfile").toString()
			self.RGBfileLabel.setText(self.RGBfname)
		else:
			self.sRGB.setCheckState(Qt.Checked)
			self.RGBfileButton.setEnabled(False)
		if settings.contains("CMYKProfile"):
			self.CMYKfname = settings.value("CMYKProfile").toString()
			self.CMYKfileLabel.setText(self.CMYKfname)
		else:
			self.Fogra27L.setCheckState(Qt.Checked)
			self.CMYKfileButton.setEnabled(False)
		self.RecFilesSpin.setValue(settings.value("MaxRecentFiles").toInt()[0])
		self.lang = False
		if settings.contains("Language"):
			self.lang = settings.value("Language")
			self.LangCombo.setCurrentIndex(self.LangCombo.findData(self.lang))

		self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
		self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
		self.connect(self.sRGB, SIGNAL("stateChanged (int)"), self.actProfile)
		self.connect(self.RGBfileButton, SIGNAL("clicked()"), self.setRGBFile)
		self.connect(self.Fogra27L, SIGNAL("stateChanged (int)"), self.actProfile)
		self.connect(self.CMYKfileButton, SIGNAL("clicked()"), self.setCMYKFile)
		self.connect(self.LangCombo, SIGNAL("currentIndexChanged(int)"), self.setLang)
		self.setWindowTitle(_("Settings"))

	def accept(self):
		if self.sRGB.checkState() == 0 and not hasattr(self,'RGBfname'):
			msgBox = QMessageBox(self)
			msgBox.setWindowTitle(_('Error'))
			msgBox.setIcon(QMessageBox.Critical)
			msgBox.setText(_("You must choose either sRGB or a file"))
			msgBox.exec_()
		elif self.Fogra27L.checkState() == 0 and not hasattr(self,'CMYKfname'):
			msgBox = QMessageBox(self)
			msgBox.setWindowTitle(_('Error'))
			msgBox.setIcon(QMessageBox.Critical)
			msgBox.setText(_("You must choose either Fogra27L or a file"))
			msgBox.exec_()
		else:
			QDialog.accept(self)

	def returnDisProf(self):
		if hasattr(self,'RGBfname'):
			return self.RGBfname

	def returnCMYKProf(self):
		if hasattr(self,'CMYKfname'):
			return self.CMYKfname

	def actProfile(self):
		if self.sRGB.checkState() == 2:
			if hasattr(self,'RGBfname'):
				del self.RGBfname
			self.RGBfileLabel.setText("")
			self.RGBfileButton.setEnabled(False)
		else:
			self.RGBfileButton.setEnabled(True)
		if self.Fogra27L.checkState() == 2:
			if hasattr(self,'CMYKfname'):
				del self.CMYKfname
			self.CMYKfileLabel.setText("")
			self.CMYKfileButton.setEnabled(False)
		else:
			self.CMYKfileButton.setEnabled(True)

	def setRGBFile(self):
		fname = QFileDialog.getOpenFileName(self, _("Choose file"), QDir.homePath(),_("ICC profiles (*.icc *.icm)"))
		if fname:
			import swatchbook.icc as icc
			profile = icc.ICCprofile(fname)
			if profile.info['class'] == "mntr" and profile.info['space'] == 'RGB ':
				self.RGBfname = fname
				self.RGBfileLabel.setText(self.RGBfname)
			else:
				msgBox = QMessageBox(self)
				msgBox.setWindowTitle(_('Error'))
				msgBox.setIcon(QMessageBox.Critical)
				msgBox.setText(_("This isn't a RGB monitor profile"))
				msgBox.exec_()
		
	def setCMYKFile(self):
		fname = QFileDialog.getOpenFileName(self, _("Choose file"), QDir.homePath(),_("ICC profiles (*.icc *.icm)"))
		if fname:
			import swatchbook.icc as icc
			profile = icc.ICCprofile(fname)
			if profile.info['space'] == 'CMYK':
				self.CMYKfname = fname
				self.CMYKfileLabel.setText(self.CMYKfname)
			else:
				msgBox = QMessageBox(self)
				msgBox.setWindowTitle('Error')
				msgBox.setIcon(QMessageBox.Critical)
				msgBox.setText(_("This isn't a CMYK profile"))
				msgBox.exec_()
		
	def setLang(self,index):
		if self.sender().itemData(index).toString() > '':
			self.lang = self.sender().itemData(index)
		else:
			self.lang = False

class webOpenDlg(QDialog):
	def __init__(self, parent=None):
		super(webOpenDlg, self).__init__(parent)
		import swatchbook.websvc as websvc
		self.svc = False
		self.id = False

		self.tabWidget = QTabWidget()
		self.webWidgets = {}
		for svc in websvc.list:
			current_svc = eval('websvc.'+svc+'()')
			if current_svc.type == 'list':
				webWidget = QTreeWidget()
				webWidget.setHeaderHidden(True)
				webWidget.setColumnHidden(1,True)
				self.webWidgets[webWidget] = [svc,False]
				self.connect(webWidget,
						SIGNAL("itemSelectionChanged()"), self.activate)
				self.connect(webWidget,
						SIGNAL("itemExpanded(QTreeWidgetItem *)"), self.nextLevel)
			if(QFile.exists('swatchbook/websvc/'+svc+'.png')):
				self.tabWidget.addTab(webWidget,QIcon('swatchbook/websvc/'+svc+'.png'),websvc.list[svc])
			else:
				tabWidget.addTab(webWidget,websvc.list[svc])
		self.changeTab()
		buttonBox = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)

		webl = QVBoxLayout()
		webl.addWidget(self.tabWidget)
		webl.addWidget(buttonBox)
		self.setLayout(webl)

		self.setWindowTitle(_("Open from web"))
		self.connect(self.tabWidget,
				SIGNAL("currentChanged(int)"), self.changeTab)
		self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
		self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))

	def activate(self):
		if self.sender().selectedItems():
			treeItem = self.sender().selectedItems()[0]
			self.svc = unicode(self.webWidgets[self.tabWidget.currentWidget()][0])
			self.id = unicode(treeItem.text(1))

	def changeTab(self):
		self.svc = False
		self.id = False
		import swatchbook.websvc as websvc
		svc,activated = self.webWidgets[self.tabWidget.currentWidget()]
		if not activated:
			current_svc = eval('websvc.'+svc+'()')
			root = current_svc.level0()
			for item in root:
				itemtext = QStringList()
				itemtext << root[item] << item
				titem = QTreeWidgetItem(self.tabWidget.currentWidget(),itemtext)
				if current_svc.nbLevels > 1:
					titem.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
					titem.setFlags(titem.flags() & ~(Qt.ItemIsSelectable))
			self.webWidgets[self.tabWidget.currentWidget()][1] = True

	def nextLevel(self,treeItem):
		if treeItem.childCount() == 0:
			import swatchbook.websvc as websvc
			svc = self.webWidgets[self.tabWidget.currentWidget()][0]
			current_svc = eval('websvc.'+svc+'()')
			level = 1
			parent = treeItem.parent()
			while parent:
				parent = parent.parent()
				level += 1
			llist = eval('current_svc.level'+str(level))(unicode(treeItem.text(1)))
			for item in llist:
				itemtext = QStringList()
				itemtext << llist[item] << item
				titem = QTreeWidgetItem(treeItem,itemtext)
				if current_svc.nbLevels > level+1:
					titem.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
					titem.setFlags(titem.flags() & ~(Qt.ItemIsSelectable))
					

if __name__ == "__main__":
	app = QApplication(sys.argv)
	app.setOrganizationName("Selapa")
	app.setOrganizationDomain("selapa.net")
	app.setApplicationName("SwatchBooker")
	settings = QSettings()

	locale = settings.value("Language").toString() or QLocale.system().name()
	# translation of the app
	try:
		lang = gettext.translation('swatchbooker', 'locale', languages=[str(locale)])
		lang.install()
		def _(msgid):
			return lang.gettext(msgid).decode('utf-8')

		def n_(msgid0,msgid1,n):
			return lang.ngettext(msgid0,msgid1,n).decode('utf-8')
	except IOError:
		def _(msgid):
			return gettext.gettext(msgid).decode('utf-8')

		def n_(msgid0,msgid1,n):
			return gettext.ngettext(msgid0,msgid1,n).decode('utf-8')

	# translation of the built-in dialogs
	qtTranslator = QTranslator()
	if qtTranslator.load("qt_" + locale, QLibraryInfo.location(QLibraryInfo.TranslationsPath)):
		app.installTranslator(qtTranslator)

	if len(sys.argv) > 1:
		form = MainWindow(sys.argv[1])
	else:
		form = MainWindow()
	form.show()
	form.listWidget.update()

	if app.style().metaObject().className() == "QGtkStyle":
		app.setStyle(QStyleFactory.create("Cleanlooks"))
	app.exec_()
