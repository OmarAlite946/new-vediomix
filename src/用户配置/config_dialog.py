#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置管理器对话框
用于管理项目配置和用户配置
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTabWidget, QWidget, QTableWidget, QTableWidgetItem, 
    QHeaderView, QMessageBox, QFileDialog, QGroupBox,
    QRadioButton, QCheckBox, QComboBox, QSpinBox, QDoubleSpinBox,
    QLineEdit, QFormLayout, QDialogButtonBox, QScrollArea, QSplitter,
    QFrame, QTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QSize
from PyQt5.QtGui import QColor, QFont, QIcon

from src.用户配置.config_manager import ConfigManager
from src.utils.logger import get_logger

logger = get_logger()

class ConfigCategoryWidget(QWidget):
    """配置分类小部件，用于显示和编辑某一类配置"""
    
    def __init__(self, category_name: str, config: Dict[str, Any], parent=None):
        """
        初始化配置分类小部件
        
        Args:
            category_name: 分类名称
            config: 该分类的配置项
            parent: 父部件
        """
        super().__init__(parent)
        self.category_name = category_name
        self.config = config
        self.edited_config = config.copy()  # 用于存储编辑后的配置
        self.widgets = {}  # 存储配置项对应的UI控件
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化界面"""
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 创建表单布局，用于放置配置项
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight)
        form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form_layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
        
        # 创建每个配置项的控件
        for key, value in sorted(self.config.items()):
            widget = self._create_widget_for_value(key, value)
            if widget:
                label_text = self._format_key_to_label(key)
                form_layout.addRow(f"{label_text}:", widget)
                self.widgets[key] = widget
        
        # 添加表单布局到主布局
        main_layout.addLayout(form_layout)
        
        # 添加底部的说明文本
        info_label = QLabel(f"以上是 <b>{self.category_name}</b> 类别的所有配置项")
        info_label.setStyleSheet("color: #666666; font-size: 10px;")
        main_layout.addWidget(info_label)
        
        # 添加伸缩项，确保控件居上
        main_layout.addStretch()
    
    def _format_key_to_label(self, key: str) -> str:
        """
        将配置键名格式化为标签文本
        
        Args:
            key: 配置键名
            
        Returns:
            str: 格式化后的标签文本
        """
        # 将下划线替换为空格，并首字母大写
        words = key.split('_')
        formatted = ' '.join(word.capitalize() for word in words)
        return formatted
    
    def _create_widget_for_value(self, key: str, value: Any) -> QWidget:
        """
        根据配置值的类型创建对应的控件
        
        Args:
            key: 配置项的键
            value: 配置项的值
            
        Returns:
            QWidget: 创建的控件
        """
        if isinstance(value, bool):
            # 布尔值使用复选框
            checkbox = QCheckBox()
            checkbox.setChecked(value)
            checkbox.stateChanged.connect(lambda state, k=key: self._on_checkbox_changed(k, state))
            return checkbox
        
        elif isinstance(value, int):
            # 整数使用微调框
            spinbox = QSpinBox()
            spinbox.setRange(-999999, 999999)
            spinbox.setValue(value)
            spinbox.valueChanged.connect(lambda val, k=key: self._on_int_changed(k, val))
            return spinbox
        
        elif isinstance(value, float):
            # 浮点数使用双精度微调框
            spinbox = QDoubleSpinBox()
            spinbox.setRange(-999999.0, 999999.0)
            spinbox.setDecimals(2)
            spinbox.setValue(value)
            spinbox.valueChanged.connect(lambda val, k=key: self._on_float_changed(k, val))
            return spinbox
        
        elif isinstance(value, str):
            # 特殊情况：如果是颜色值（以#开头）
            if key.endswith('_color') and value.startswith('#'):
                combo = QComboBox()
                combo.addItems(["白色", "黑色", "红色", "绿色", "蓝色", "黄色", "自定义"])
                combo.setCurrentText("自定义")  # 默认选择自定义
                combo.setProperty("color_value", value)
                combo.currentIndexChanged.connect(lambda idx, k=key: self._on_color_changed(k, combo))
                return combo
            
            # 特殊情况：如果是位置值
            elif key.endswith('_position'):
                combo = QComboBox()
                positions = ["右上角", "左上角", "右下角", "左下角", "中心"]
                combo.addItems(positions)
                current_index = combo.findText(value) if value in positions else 0
                combo.setCurrentIndex(current_index)
                combo.currentTextChanged.connect(lambda text, k=key: self._on_text_changed(k, text))
                return combo
            
            # 特殊情况：如果是模式值
            elif key.endswith('_mode'):
                combo = QComboBox()
                modes = []
                if 'audio' in key:
                    modes = ["自动识别", "单音频模式", "多音频混合"]
                elif 'encode' in key:
                    modes = ["快速模式(不重编码)", "标准模式(重编码)"]
                else:
                    modes = [value]
                
                combo.addItems(modes)
                current_index = combo.findText(value) if value in modes else 0
                combo.setCurrentIndex(current_index)
                combo.currentTextChanged.connect(lambda text, k=key: self._on_text_changed(k, text))
                return combo
            
            # 普通字符串使用行编辑框
            else:
                lineedit = QLineEdit(value)
                lineedit.textChanged.connect(lambda text, k=key: self._on_text_changed(k, text))
                return lineedit
        
        elif isinstance(value, list):
            # 对于列表类型，使用只读文本框展示
            textedit = QTextEdit()
            textedit.setPlainText(str(value))
            textedit.setReadOnly(True)
            textedit.setMaximumHeight(80)
            return textedit
        
        elif isinstance(value, dict):
            # 对于字典类型，使用只读文本框展示
            textedit = QTextEdit()
            textedit.setPlainText(json.dumps(value, ensure_ascii=False, indent=2))
            textedit.setReadOnly(True)
            textedit.setMaximumHeight(80)
            return textedit
        
        else:
            # 对于其他类型，使用只读文本框展示
            textedit = QTextEdit()
            textedit.setPlainText(str(value))
            textedit.setReadOnly(True)
            textedit.setMaximumHeight(60)
            return textedit
    
    def _on_checkbox_changed(self, key: str, state: int):
        """复选框状态改变的处理函数"""
        self.edited_config[key] = state == Qt.Checked
    
    def _on_int_changed(self, key: str, value: int):
        """整数微调框值改变的处理函数"""
        self.edited_config[key] = value
    
    def _on_float_changed(self, key: str, value: float):
        """浮点数微调框值改变的处理函数"""
        self.edited_config[key] = value
    
    def _on_text_changed(self, key: str, text: str):
        """文本框内容改变的处理函数"""
        self.edited_config[key] = text
    
    def _on_color_changed(self, key: str, combo: QComboBox):
        """颜色下拉框选择改变的处理函数"""
        color_map = {
            "白色": "#FFFFFF",
            "黑色": "#000000",
            "红色": "#FF0000",
            "绿色": "#00FF00",
            "蓝色": "#0000FF",
            "黄色": "#FFFF00"
        }
        
        current_text = combo.currentText()
        if current_text in color_map:
            self.edited_config[key] = color_map[current_text]
        else:
            # 使用存储的自定义颜色值
            self.edited_config[key] = combo.property("color_value")
    
    def get_edited_config(self) -> Dict[str, Any]:
        """
        获取编辑后的配置
        
        Returns:
            Dict[str, Any]: 编辑后的配置
        """
        return self.edited_config

class ConfigManagerDialog(QDialog):
    """配置管理器对话框"""
    
    configSaved = pyqtSignal(dict, str)  # 信号：配置已保存，参数：配置内容和保存位置
    
    def __init__(self, parent=None):
        """
        初始化配置管理器对话框
        
        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        self.setWindowTitle("配置管理器")
        self.resize(900, 700)
        
        # 创建配置管理器
        self.config_manager = ConfigManager()
        
        # 加载用户配置
        from src.utils.user_settings import UserSettings
        self.user_settings = UserSettings()
        self.config = self.user_settings.get_all_settings()
        
        # 分类配置
        self.categorized_config = self._categorize_config(self.config)
        
        # 记录原始配置，用于检测变化
        self.original_config = self.config.copy()
        
        # 初始化界面
        self._init_ui()
    
    def _init_ui(self):
        """初始化界面"""
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 创建配置来源提示
        source_layout = QHBoxLayout()
        source_text = self._get_config_source_text()
        self.source_label = QLabel(source_text)
        self.source_label.setStyleSheet("font-weight: bold; color: #0066CC;")
        source_layout.addWidget(self.source_label)
        source_layout.addStretch()
        
        # 添加配置操作按钮
        self.btn_save_to_project = QPushButton("保存到项目配置")
        self.btn_save_to_project.setToolTip("将当前配置保存到项目目录下的config.json文件")
        self.btn_save_to_project.clicked.connect(self.save_to_project)
        source_layout.addWidget(self.btn_save_to_project)
        
        self.btn_export = QPushButton("导出配置")
        self.btn_export.setToolTip("将当前配置导出到文件")
        self.btn_export.clicked.connect(self.export_config)
        source_layout.addWidget(self.btn_export)
        
        self.btn_import = QPushButton("导入配置")
        self.btn_import.setToolTip("从文件导入配置")
        self.btn_import.clicked.connect(self.import_config)
        source_layout.addWidget(self.btn_import)
        
        main_layout.addLayout(source_layout)
        
        # 创建分类选项卡
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 为每个分类创建一个选项卡
        for category, config in self.categorized_config.items():
            # 创建一个滚动区域
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            
            # 创建分类部件，并设置到滚动区域
            category_widget = ConfigCategoryWidget(category, config)
            scroll_area.setWidget(category_widget)
            
            # 添加到选项卡
            self.tab_widget.addTab(scroll_area, category)
        
        # 创建对话框按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
    
    def _get_config_source_text(self) -> str:
        """
        获取配置来源提示文本
        
        Returns:
            str: 配置来源提示文本
        """
        source = self.config_manager.get_config_source()
        if source == "project":
            return "当前使用的是：项目配置 (优先级高，随项目版本控制)"
        elif source == "user":
            return "当前使用的是：用户配置 (个人设置，不受版本控制影响)"
        else:
            return "当前使用的是：默认配置 (未找到保存的配置)"
    
    def _categorize_config(self, config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        将配置分类
        
        Args:
            config: 原始配置
            
        Returns:
            Dict[str, Dict[str, Any]]: 分类后的配置
        """
        categories = {
            "基本设置": {},
            "视频设置": {},
            "音频设置": {},
            "水印设置": {},
            "缓存设置": {},
            "界面设置": {},
            "其他设置": {}
        }
        
        # 根据键名将配置项分类
        for key, value in config.items():
            if key.startswith(("resolution", "bitrate", "transition", "gpu", "encode")):
                categories["视频设置"][key] = value
            elif key.startswith(("voice", "bgm", "audio")):
                categories["音频设置"][key] = value
            elif key.startswith("watermark"):
                categories["水印设置"][key] = value
            elif key.startswith(("cache", "temp")):
                categories["缓存设置"][key] = value
            elif key.startswith(("window", "ui", "tab")):
                categories["界面设置"][key] = value
            elif key in ("save_dir", "import_folder", "generate_count"):
                categories["基本设置"][key] = value
            else:
                categories["其他设置"][key] = value
        
        return categories
    
    def get_edited_config(self) -> Dict[str, Any]:
        """
        获取所有编辑后的配置
        
        Returns:
            Dict[str, Any]: 编辑后的配置
        """
        edited_config = {}
        
        # 遍历所有选项卡，获取每个分类的编辑后配置
        for i in range(self.tab_widget.count()):
            scroll_area = self.tab_widget.widget(i)
            category_widget = scroll_area.widget()
            
            category_config = category_widget.get_edited_config()
            edited_config.update(category_config)
        
        return edited_config
    
    def save_to_project(self):
        """将配置保存到项目配置文件"""
        reply = QMessageBox.question(
            self, 
            "确认保存到项目配置", 
            "确定要将当前配置保存到项目配置文件吗？\n\n"
            "这将使得该配置受到版本控制，所有使用该项目的人都将使用这个配置。",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            config = self.get_edited_config()
            success = self.config_manager.save_to_project(config)
            
            if success:
                self.source_label.setText(self._get_config_source_text())
                QMessageBox.information(
                    self, 
                    "保存成功", 
                    "已成功将配置保存到项目配置文件。\n\n"
                    "现在这个配置将被所有使用该项目的人使用。"
                )
                self.configSaved.emit(config, "project")
            else:
                QMessageBox.warning(
                    self, 
                    "保存失败", 
                    "保存配置到项目文件时出错，请检查项目目录权限。"
                )
    
    def export_config(self):
        """导出配置到文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "导出配置", 
            str(Path.home() / "config.json"), 
            "JSON文件 (*.json)"
        )
        
        if file_path:
            config = self.get_edited_config()
            success = self.config_manager.export_config_to_file(config, file_path)
            
            if success:
                QMessageBox.information(
                    self, 
                    "导出成功", 
                    f"已成功导出配置到：\n{file_path}"
                )
            else:
                QMessageBox.warning(
                    self, 
                    "导出失败", 
                    "导出配置时出错，请检查文件路径权限。"
                )
    
    def import_config(self):
        """从文件导入配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "导入配置", 
            str(Path.home()), 
            "JSON文件 (*.json)"
        )
        
        if file_path:
            success, config = self.config_manager.import_config_from_file(file_path)
            
            if success:
                # 创建新对话框，显示差异并确认导入
                self._show_import_confirmation(config)
            else:
                QMessageBox.warning(
                    self, 
                    "导入失败", 
                    "从文件导入配置时出错，请检查文件格式。"
                )
    
    def _show_import_confirmation(self, imported_config: Dict[str, Any]):
        """
        显示导入确认对话框
        
        Args:
            imported_config: 导入的配置
        """
        # 获取当前配置
        current_config = self.get_edited_config()
        
        # 计算差异
        diff = self.config_manager.get_configs_difference(current_config, imported_config)
        
        # 如果没有差异，直接提示
        if not diff:
            QMessageBox.information(
                self, 
                "导入提示", 
                "导入的配置与当前配置没有差异。"
            )
            return
        
        # 创建确认对话框
        dlg = QDialog(self)
        dlg.setWindowTitle("确认导入配置")
        dlg.resize(700, 500)
        
        # 创建布局
        layout = QVBoxLayout(dlg)
        
        # 添加说明
        layout.addWidget(QLabel("以下是导入配置与当前配置的差异，请确认是否导入："))
        
        # 创建差异表格
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["配置项", "当前值", "导入值"])
        table.setRowCount(len(diff))
        
        # 设置表格属性
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        
        # 填充表格
        for row, (key, values) in enumerate(diff.items()):
            # 配置项
            key_item = QTableWidgetItem(key)
            table.setItem(row, 0, key_item)
            
            # 当前值
            current_value = values[0]
            current_item = QTableWidgetItem(str(current_value))
            table.setItem(row, 1, current_item)
            
            # 导入值
            import_value = values[1]
            import_item = QTableWidgetItem(str(import_value))
            import_item.setBackground(QColor("#E0F0FF"))  # 浅蓝色背景
            table.setItem(row, 2, import_item)
        
        layout.addWidget(table)
        
        # 添加按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dlg.accept)
        button_box.rejected.connect(dlg.reject)
        layout.addWidget(button_box)
        
        # 显示对话框
        if dlg.exec_() == QDialog.Accepted:
            # 接受导入
            self._apply_imported_config(imported_config)
    
    def _apply_imported_config(self, imported_config: Dict[str, Any]):
        """
        应用导入的配置
        
        Args:
            imported_config: 导入的配置
        """
        # 重新创建界面
        # 先清除现有选项卡
        while self.tab_widget.count() > 0:
            self.tab_widget.removeTab(0)
        
        # 更新配置
        self.config = imported_config
        self.categorized_config = self._categorize_config(self.config)
        
        # 为每个分类创建一个选项卡
        for category, config in self.categorized_config.items():
            # 创建一个滚动区域
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            
            # 创建分类部件，并设置到滚动区域
            category_widget = ConfigCategoryWidget(category, config)
            scroll_area.setWidget(category_widget)
            
            # 添加到选项卡
            self.tab_widget.addTab(scroll_area, category)
        
        QMessageBox.information(
            self, 
            "导入成功", 
            "已成功导入配置。\n\n"
            "请注意，配置尚未保存，需要点击确定按钮应用更改。"
        )
    
    def accept(self):
        """对话框接受按钮点击处理"""
        # 获取编辑后的配置
        edited_config = self.get_edited_config()
        
        # 保存到用户配置
        from src.utils.user_settings import UserSettings
        user_settings = UserSettings()
        
        # 应用所有更改
        for key, value in edited_config.items():
            user_settings.set_setting(key, value)
        
        # 保存设置
        user_settings.save_settings()
        
        # 发射信号
        self.configSaved.emit(edited_config, "user")
        
        # 关闭对话框
        super().accept()
    
    def closeEvent(self, event):
        """对话框关闭事件处理"""
        # 获取编辑后的配置
        edited_config = self.get_edited_config()
        
        # 检查是否有更改
        has_changes = edited_config != self.original_config
        
        if has_changes:
            reply = QMessageBox.question(
                self, 
                "确认关闭", 
                "配置已修改但尚未保存，是否放弃更改？",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept() 