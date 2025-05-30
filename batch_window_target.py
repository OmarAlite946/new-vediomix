#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
澶氭ā鏉挎壒閲忓鐞嗙獥鍙?"""

import os
import sys
import time
import json
import logging
import threading
import gc
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QProgressBar, QApplication,
    QTabWidget, QCheckBox, QMessageBox, QStatusBar,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMenu, QAction, QToolButton, QFrame, QSplitter, QInputDialog
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, pyqtSlot, QSize, QMetaObject, Q_ARG,
    QTimer
)
from PyQt5.QtGui import QIcon, QFont, QColor

from src.ui.main_window import MainWindow
from src.utils.logger import get_logger
from src.utils.template_state import TemplateState

logger = get_logger()

class BatchWindow(QMainWindow):
    """鎵归噺澶勭悊澶氫釜妯℃澘鐨勪富绐楀彛"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("瑙嗛妯℃澘鎵归噺澶勭悊宸ュ叿")
        self.resize(1200, 800)
        
        # 鍒濆鍖栫姸鎬佸彉閲?        self.tabs = []  # 瀛樺偍鎵撳紑鐨勬爣绛鹃〉
        self.current_processing_tab = None  # 褰撳墠姝ｅ湪澶勭悊鐨勬爣绛鹃〉
        self.is_processing = False  # 鏄惁姝ｅ湪澶勭悊
        self.processing_thread = None  # 澶勭悊绾跨▼
        self.processing_queue = []  # 澶勭悊闃熷垪
        
        # 缁熻淇℃伅
        self.batch_start_time = None  # 鎵瑰鐞嗗紑濮嬫椂闂?        self.total_processed_count = 0  # 鎬诲鐞嗚棰戞暟
        self.total_process_time = 0  # 鎬诲鐞嗘椂闂?绉?
        
        # 鍒濆鍖栨ā鏉跨姸鎬佺鐞?        self.template_state = TemplateState()
        
        # 鍒濆鍖栫晫闈?        self._init_ui()
        
        # 鍒濆鍖栫姸鎬佹爮
        self._init_statusbar()
        
        # 璁剧疆鍏ㄥ眬瀵硅瘽妗嗚繃婊ゅ櫒
        self._setup_dialog_filter()
        
        # 鍔犺浇涔嬪墠淇濆瓨鐨勬ā鏉?        self._load_saved_templates()
        
        # 濡傛灉娌℃湁鍔犺浇鍒板凡淇濆瓨鐨勬ā鏉匡紝娣诲姞涓€涓垵濮嬫爣绛鹃〉
        if len(self.tabs) == 0:
            self._add_new_tab()
        
        # 鍒涘缓瀹氭椂鍣ㄧ敤浜庡埛鏂癠I
        self.ui_refresh_timer = QTimer(self)
        self.ui_refresh_timer.timeout.connect(self._periodic_ui_refresh)
        self.ui_refresh_timer.start(5000)  # 姣?绉掑埛鏂颁竴娆I
        
        logger.info("鎵归噺澶勭悊绐楀彛鍒濆鍖栧畬鎴?)
    
    def _periodic_ui_refresh(self):
        """瀹氭湡鍒锋柊UI鐘舵€?""
        try:
            # 濡傛灉褰撳墠姝ｅ湪澶勭悊浠诲姟锛屽垯涓嶅埛鏂癠I
            if self.is_processing:
                return
                
            # 妫€鏌ユ槸鍚︽湁鏍囩椤甸渶瑕佸埛鏂?            for tab in self.tabs:
                if "window" in tab and tab["window"] and tab["window"].isVisible():
                    try:
                        # 纭繚鏍囩椤靛唴瀹瑰彲瑙?                        tab["window"].update()
                    except Exception as e:
                        logger.debug(f"瀹氭湡鍒锋柊鏍囩椤?'{tab['name']}' 鏃跺嚭閿? {str(e)}")
            
            # 鍒锋柊鏁翠釜绐楀彛
            self.update()
            
            # 鏇存柊浠诲姟琛ㄦ牸
            self._update_tasks_table()
            
            logger.debug("瀹屾垚瀹氭湡UI鍒锋柊")
        except Exception as e:
            logger.error(f"瀹氭湡鍒锋柊UI鏃跺嚭閿? {str(e)}")
    
    def _load_saved_templates(self):
        """鍔犺浇淇濆瓨鐨勬ā鏉挎爣绛鹃〉鐘舵€?""
        saved_tabs = self.template_state.load_template_tabs()
        if not saved_tabs:
            return
        
        logger.info(f"寮€濮嬪姞杞?{len(saved_tabs)} 涓繚瀛樼殑妯℃澘鏍囩椤?)
        
        # 纭繚鎸夌収涔嬪墠淇濆瓨鐨勭储寮曞姞杞芥爣绛鹃〉
        for tab_info in saved_tabs:
            try:
                tab_name = tab_info.get("name", "")
                tab_index = tab_info.get("tab_index", -1)
                logger.info(f"鍔犺浇妯℃澘: {tab_name}, 绱㈠紩: {tab_index}")
                self._add_template_from_info(tab_info)
            except Exception as e:
                logger.error(f"鍔犺浇妯℃澘 {tab_info.get('name', '鏈煡')} 鏃跺嚭閿? {str(e)}")
        
        # 鏇存柊浠诲姟琛ㄦ牸
        self._update_tasks_table()
        
        # 涓烘墍鏈夋爣绛鹃〉閲嶆柊璁剧疆姝ｇ‘鐨勭储寮?        for i, tab in enumerate(self.tabs):
            tab["tab_index"] = i
        
        # 鏈€鍚庡啀淇濆瓨涓€娆′互纭繚绱㈠紩姝ｇ‘
        self._save_template_state()
        
        logger.info(f"宸插畬鎴?{len(self.tabs)} 涓ā鏉挎爣绛鹃〉鐨勫姞杞?)
        
    def _add_template_from_info(self, tab_info):
        """浠庝繚瀛樼殑淇℃伅涓坊鍔犳ā鏉挎爣绛鹃〉"""
        name = tab_info.get("name", "")
        file_path = tab_info.get("file_path", "")
        folder_path = tab_info.get("folder_path", "")
        tab_index = tab_info.get("tab_index", -1)  # 鑾峰彇鏍囩椤电储寮?        instance_id = tab_info.get("instance_id", f"tab_restored_{time.time()}_{tab_index}")  # 鑾峰彇瀹炰緥ID鎴栫敓鎴愭柊ID
        
        if not name:
            return False
        
        logger.info(f"姝ｅ湪娣诲姞妯℃澘: {name}, 鏂囦欢璺緞: {file_path}, 鏂囦欢澶? {folder_path}, 瀹炰緥ID: {instance_id}")
        
        # 鍒涘缓鏂扮殑MainWindow瀹炰緥锛屼娇鐢ㄤ繚瀛樼殑瀹炰緥ID鎴栨柊鐢熸垚鐨処D
        main_window = MainWindow(instance_id=instance_id)
        
        # 淇濆瓨鍘熷鐨刼n_compose_completed鏂规硶
        original_completed_func = main_window.on_compose_completed
        
        # 瑕嗙洊鍘熸柟娉曪紝鎵归噺妯″紡涓嬩笉鏄剧ず鎻愮ず瀵硅瘽妗?        def batch_on_completed(success=True, count=0, output_dir="", total_time=""):
            # 璋冪敤鍘熸柟娉曚絾涓嶆樉绀篗essageBox
            try:
                # 涓存椂鏇挎崲QMessageBox.information鏂规硶
                original_info = QMessageBox.information
                QMessageBox.information = lambda *args, **kwargs: None
                
                # 璋冪敤鍘熸柟娉?                original_completed_func(success, count, output_dir, total_time)
                
                # 鎭㈠鍘熸柟娉?                QMessageBox.information = original_info
                
                # 璁剧疆瀹屾垚鏍囧織
                main_window.compose_completed = True
                logger.info(f"妯℃澘 {name} 澶勭悊宸插畬鎴愶紝璁剧疆瀹屾垚鏍囧織")
                
                # 鏇存柊杩涘害鏃堕棿鎴?                main_window.last_progress_update = time.time()
                
                # 璁板綍褰撳墠澶勭悊鍣ㄥ拰绾跨▼鐘舵€?                has_processor = hasattr(main_window, "processor") and main_window.processor is not None
                has_thread = hasattr(main_window, "processing_thread") and main_window.processing_thread is not None
                logger.debug(f"瀹屾垚鍥炶皟鏃剁姸鎬侊細澶勭悊鍣?{has_processor}锛岀嚎绋?{has_thread}")
                
                # 濡傛灉澶勭悊鎴愬姛锛屽皾璇曡褰曡緭鍑烘枃浠朵俊鎭?                if success and count > 0:
                    logger.info(f"鎴愬姛鍚堟垚 {count} 涓棰戯紝淇濆瓨鍒? {output_dir}锛岀敤鏃? {total_time}")
            except Exception as e:
                logger.error(f"鎵瑰鐞嗘ā寮忎笅澶勭悊瀹屾垚鍥炶皟鍑洪敊: {str(e)}")
                error_detail = traceback.format_exc()
                logger.error(f"璇︾粏閿欒淇℃伅: {error_detail}")
                # 纭繚鍗充娇鍑洪敊锛屼篃璁剧疆瀹屾垚鏍囧織
                main_window.compose_completed = True
                main_window.last_progress_update = time.time()
        
        # 瑕嗙洊鏂规硶
        main_window.on_compose_completed = batch_on_completed
        
        # 纭繚杩欎釜鏍囩椤垫嫢鏈夎嚜宸辩嫭绔嬬殑鐢ㄦ埛璁剧疆
        if hasattr(main_window, "user_settings") and main_window.user_settings:
            # 浣跨敤淇濆瓨鐨勫疄渚婭D
            main_window.user_settings.instance_id = instance_id
            logger.debug(f"涓烘ā鏉?{name} 璁剧疆鐙珛鐨勭敤鎴疯缃疄渚婭D: {instance_id}")
        
        # 娣诲姞鏍囩椤靛埌鐣岄潰
        tab_index = self.tab_widget.addTab(main_window, name)
        
        # 璁板綍鏍囩椤典俊鎭?        tab_info = {
            "name": name,
            "window": main_window,
            "status": "鍑嗗灏辩华",
            "last_process_time": None,
            "file_path": file_path,
            "folder_path": folder_path,
            "tab_index": tab_index,  # 淇濆瓨鏍囩椤电储寮?            "instance_id": instance_id  # 淇濆瓨瀹炰緥ID
        }
        
        # 灏嗘爣绛鹃〉娣诲姞鍒版爣绛惧垪琛?        self.tabs.append(tab_info)
        
        # 娉ㄦ剰锛氭枃浠跺す璺緞闇€瑕佸湪鍔犺浇閰嶇疆鏂囦欢涔嬪悗璁剧疆锛屼互閬垮厤琚鐩?        # 濡傛灉鏈夐厤缃枃浠惰矾寰勶紝灏濊瘯鍔犺浇
        if file_path and os.path.exists(file_path):
            try:
                main_window.load_config(file_path)
                logger.info(f"宸插姞杞芥ā鏉块厤缃枃浠? {file_path}")
            except Exception as e:
                logger.error(f"鍔犺浇妯℃澘閰嶇疆鏂囦欢澶辫触: {str(e)}")
        
        # 濡傛灉鏈夋枃浠跺す璺緞锛屽皾璇曡缃?- 杩欎竴姝ヨ纭繚鍦ㄦ渶鍚庤繘琛岋紝閬垮厤琚叾浠栬缃鐩?        if folder_path and os.path.exists(folder_path):
            try:
                # 璁剧疆杈撳叆鏂囦欢澶硅矾寰?                main_window.input_folder_path.setText(folder_path)
                
                # 璁剧疆鐢ㄦ埛璁剧疆涓殑import_folder锛岀‘淇濈嫭绔嬫€?                if hasattr(main_window, "user_settings"):
                    main_window.user_settings.set_setting("import_folder", folder_path)
                
                # 瑙﹀彂閫夋嫨鏂囦欢澶瑰姩浣滐紝浠ュ姞杞芥枃浠跺垪琛?                main_window.on_select_folder()
                
                # 鍐嶆纭鏂囦欢澶硅矾寰勫凡姝ｇ‘璁剧疆
                current_path = main_window.input_folder_path.text().strip()
                if current_path != folder_path:
                    logger.warning(f"鏂囦欢澶硅矾寰勮缃彲鑳戒笉姝ｇ‘锛屾湡鏈? {folder_path}, 瀹為檯: {current_path}")
                    # 鍐嶆灏濊瘯璁剧疆
                    main_window.input_folder_path.setText(folder_path)
                
                logger.info(f"宸茶缃ā鏉胯緭鍏ユ枃浠跺す: {folder_path}")
            except Exception as e:
                logger.error(f"璁剧疆妯℃澘杈撳叆鏂囦欢澶瑰け璐? {str(e)}")
                logger.error(traceback.format_exc())
        
        logger.info(f"宸叉坊鍔犳ā鏉挎爣绛鹃〉: {name}, 绱㈠紩: {tab_index}, 瀹炰緥ID: {instance_id}")
        return True
        
    def _init_ui(self):
        """鍒濆鍖朥I鐣岄潰"""
        # 鍒涘缓涓ぎ閮ㄤ欢
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 涓诲竷灞€
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 鍒涘缓鍒嗗壊鍣?        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter)
        
        # 鍒涘缓鏍囩椤靛尯鍩?        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)  # 鍏佽鍏抽棴鏍囩
        self.tab_widget.tabCloseRequested.connect(self._on_tab_close)
        
        # 鍚敤鍙屽嚮缂栬緫鏍囩鍔熻兘
        self.tab_widget.tabBarDoubleClicked.connect(self._on_tab_double_clicked)
        
        # 鍒涘缓"娣诲姞"鎸夐挳浣滀负鏈€鍚庝竴涓爣绛?        self.tab_widget.setTabPosition(QTabWidget.North)
        add_tab_button = QToolButton(self)
        add_tab_button.setText("+")
        add_tab_button.setToolTip("娣诲姞鏂版ā鏉?)
        add_tab_button.clicked.connect(self._add_new_tab)
        self.tab_widget.setCornerWidget(add_tab_button, Qt.TopRightCorner)
        
        # 鎵归噺澶勭悊鎺у埗闈㈡澘
        batch_panel = QWidget()
        batch_layout = QVBoxLayout(batch_panel)
        batch_layout.setContentsMargins(10, 10, 10, 10)
        
        # 鎵归噺澶勭悊浠诲姟鍒楄〃鏍囬
        tasks_header = QLabel("鎵归噺澶勭悊浠诲姟")
        tasks_header.setStyleSheet("font-size: 16px; font-weight: bold;")
        batch_layout.addWidget(tasks_header)
        
        # 浠诲姟琛ㄦ牸
        self.tasks_table = QTableWidget(0, 6)  # 鍒濆涓?琛岋紝6鍒?        self.tasks_table.setHorizontalHeaderLabels(["閫夋嫨", "妯℃澘鍚嶇О", "鐘舵€?, "澶勭悊鏁伴噺", "澶勭悊鏃堕棿", "鏈€鍚庡鐞嗘椂闂?])
        self.tasks_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        # 璁剧疆鍒楀
        header = self.tasks_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # 閫夋嫨妗嗗浐瀹氬搴?        header.setSectionResizeMode(1, QHeaderView.Stretch)  # 鍚嶇О鍒楄嚜閫傚簲
        header.setSectionResizeMode(2, QHeaderView.Fixed)  # 鐘舵€佸垪鍥哄畾瀹藉害
        header.setSectionResizeMode(3, QHeaderView.Fixed)  # 澶勭悊鏁伴噺鍒楀浐瀹氬搴?        header.setSectionResizeMode(4, QHeaderView.Fixed)  # 澶勭悊鏃堕棿鍒楀浐瀹氬搴?        header.setSectionResizeMode(5, QHeaderView.Fixed)  # 鏈€鍚庡鐞嗘椂闂村垪鍥哄畾瀹藉害
        
        self.tasks_table.setColumnWidth(0, 60)  # 閫夋嫨妗嗗垪瀹?        self.tasks_table.setColumnWidth(2, 80)  # 鐘舵€佸垪瀹?        self.tasks_table.setColumnWidth(3, 80)  # 澶勭悊鏁伴噺鍒楀
        self.tasks_table.setColumnWidth(4, 100)  # 澶勭悊鏃堕棿鍒楀
        self.tasks_table.setColumnWidth(5, 150)  # 鏃堕棿鍒楀
        
        batch_layout.addWidget(self.tasks_table)
        
        # 鎵归噺澶勭悊鎺у埗鎸夐挳
        batch_buttons = QHBoxLayout()
        batch_buttons.setContentsMargins(0, 0, 0, 0)
        
        # 鍏ㄩ€?鍙栨秷鍏ㄩ€?        self.btn_select_all = QPushButton("鍏ㄩ€?)
        self.btn_select_all.clicked.connect(self._on_select_all)
        
        # 娣诲姞鎵归噺鍒锋柊绱犳潗鏁伴噺鎸夐挳
        self.btn_refresh_counts = QPushButton("鎵归噺鍒锋柊绱犳潗鏁伴噺")
        self.btn_refresh_counts.setStyleSheet("""
            QPushButton {
                background-color: #5C85D6;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #4A6FB8;
            }
        """)
        self.btn_refresh_counts.clicked.connect(self._on_refresh_all_counts)
        
        # 寮€濮嬫壒閲忓鐞?        self.btn_start_batch = QPushButton("寮€濮嬫壒閲忓鐞?)
        self.btn_start_batch.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 8px 16px;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.btn_start_batch.clicked.connect(self._on_start_batch)
        
        # 鍋滄鎵归噺澶勭悊
        self.btn_stop_batch = QPushButton("鍋滄鎵归噺澶勭悊")
        self.btn_stop_batch.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 8px 16px;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        self.btn_stop_batch.setEnabled(False)
        self.btn_stop_batch.clicked.connect(self._on_stop_batch)
        
        batch_buttons.addWidget(self.btn_select_all)
        batch_buttons.addWidget(self.btn_refresh_counts)
        batch_buttons.addStretch(1)
        batch_buttons.addWidget(self.btn_start_batch)
        batch_buttons.addWidget(self.btn_stop_batch)
        
        batch_layout.addLayout(batch_buttons)
        
        # 鎵瑰鐞嗚繘搴?        progress_layout = QVBoxLayout()
        progress_layout.setContentsMargins(0, 10, 0, 0)
        
        progress_header = QHBoxLayout()
        self.label_current_task = QLabel("褰撳墠浠诲姟: 绛夊緟涓?)
        progress_header.addWidget(self.label_current_task)
        
        self.label_queue = QLabel("闃熷垪: 0/0")
        progress_header.addWidget(self.label_queue, 0, Qt.AlignRight)
        
        progress_layout.addLayout(progress_header)
        
        self.batch_progress = QProgressBar()
        self.batch_progress.setRange(0, 100)
        self.batch_progress.setValue(0)
        self.batch_progress.setTextVisible(True)
        progress_layout.addWidget(self.batch_progress)
        
        # 娣诲姞缁撴灉缁熻鍖哄煙
        statistics_layout = QHBoxLayout()
        statistics_layout.setContentsMargins(0, 10, 0, 0)
        
        self.label_total_videos = QLabel("鎬昏棰戞暟: 0")
        self.label_total_time = QLabel("鎬荤敤鏃? 0绉?)
        
        statistics_layout.addWidget(self.label_total_videos)
        statistics_layout.addStretch(1)
        statistics_layout.addWidget(self.label_total_time)
        
        progress_layout.addLayout(statistics_layout)
        
        batch_layout.addLayout(progress_layout)
        
        # 娣诲姞鏍囩椤靛尯鍩熷拰鎵归噺澶勭悊闈㈡澘鍒板垎鍓插櫒
        splitter.addWidget(self.tab_widget)
        splitter.addWidget(batch_panel)
        
        # 璁剧疆鍒嗗壊鍣ㄥ垵濮嬪ぇ灏忔瘮渚?        splitter.setSizes([600, 200])
    
    def _init_statusbar(self):
        """鍒濆鍖栫姸鎬佹爮"""
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        
        self.status_label = QLabel("灏辩华")
        self.statusBar.addWidget(self.status_label, 1)
    
    def _add_new_tab(self):
        """娣诲姞鏂扮殑鏍囩椤?""
        # 鍒涘缓鍞竴鐨勫疄渚婭D
        instance_id = f"tab_new_{time.time()}"
        logger.info(f"鍒涘缓鏂版爣绛鹃〉, 瀹炰緥ID: {instance_id}")
        
        # 鍒涘缓鏂扮殑MainWindow瀹炰緥锛屼紶鍏ュ疄渚婭D
        main_window = MainWindow(instance_id=instance_id)
        
        # 淇濆瓨鍘熷鐨刼n_compose_completed鏂规硶
        original_completed_func = main_window.on_compose_completed
        
        # 瑕嗙洊鍘熸柟娉曪紝鎵归噺妯″紡涓嬩笉鏄剧ず鎻愮ず瀵硅瘽妗?        def batch_on_completed(success=True, count=0, output_dir="", total_time=""):
            # 璋冪敤鍘熸柟娉曚絾涓嶆樉绀篗essageBox
            try:
                # 涓存椂鏇挎崲QMessageBox.information鏂规硶
                original_info = QMessageBox.information
                QMessageBox.information = lambda *args, **kwargs: None
                
                # 璋冪敤鍘熸柟娉?                original_completed_func(success, count, output_dir, total_time)
                
                # 鎭㈠鍘熸柟娉?                QMessageBox.information = original_info
                
                # 璁剧疆瀹屾垚鏍囧織
                main_window.compose_completed = True
                logger.info(f"妯℃澘 {tab_name} 澶勭悊宸插畬鎴愶紝璁剧疆瀹屾垚鏍囧織")
                
                # 鏇存柊杩涘害鏃堕棿鎴?                main_window.last_progress_update = time.time()
                
                # 璁板綍褰撳墠澶勭悊鍣ㄥ拰绾跨▼鐘舵€?                has_processor = hasattr(main_window, "processor") and main_window.processor is not None
                has_thread = hasattr(main_window, "processing_thread") and main_window.processing_thread is not None
                logger.debug(f"瀹屾垚鍥炶皟鏃剁姸鎬侊細澶勭悊鍣?{has_processor}锛岀嚎绋?{has_thread}")
                
                # 濡傛灉澶勭悊鎴愬姛锛屽皾璇曡褰曡緭鍑烘枃浠朵俊鎭?                if success and count > 0:
                    logger.info(f"鎴愬姛鍚堟垚 {count} 涓棰戯紝淇濆瓨鍒? {output_dir}锛岀敤鏃? {total_time}")
            except Exception as e:
                logger.error(f"鎵瑰鐞嗘ā寮忎笅澶勭悊瀹屾垚鍥炶皟鍑洪敊: {str(e)}")
                error_detail = traceback.format_exc()
                logger.error(f"璇︾粏閿欒淇℃伅: {error_detail}")
                # 纭繚鍗充娇鍑洪敊锛屼篃璁剧疆瀹屾垚鏍囧織
                main_window.compose_completed = True
                main_window.last_progress_update = time.time()
        
        # 瑕嗙洊鏂规硶
        main_window.on_compose_completed = batch_on_completed
        
        # 瑕嗙洊杩涘害鏇存柊鍥炶皟锛屼互纭繚杩涘害鏃堕棿鎴虫纭洿鏂?        original_update_progress = None
        if hasattr(main_window, "_do_update_progress"):
            original_update_progress = main_window._do_update_progress
            
            def batch_update_progress(message, percent):
                # 鏇存柊杩涘害鏃堕棿鎴?                main_window.last_progress_update = time.time()
                # 璋冪敤鍘熸柟娉?                if original_update_progress:
                    original_update_progress(message, percent)
                    
            # 瑕嗙洊鏂规硶    
            main_window._do_update_progress = batch_update_progress
        
        # 鍚屾牱澶勭悊閿欒鍥炶皟锛岄伩鍏嶅嚭閿欐椂寮规
        original_error_func = main_window.on_compose_error
        
        def batch_on_error(error_msg, detail=""):
            try:
                # 涓存椂鏇挎崲QMessageBox.critical鏂规硶
                original_critical = QMessageBox.critical
                QMessageBox.critical = lambda *args, **kwargs: None
                
                # 璋冪敤鍘熸柟娉?                original_error_func(error_msg, detail)
                
                # 鎭㈠鍘熸柟娉?                QMessageBox.critical = original_critical
                
                # 璁剧疆閿欒鏍囧織锛岃繖涔熻〃绀哄鐞嗗凡瀹屾垚锛屼絾鏈夐敊璇?                main_window.compose_completed = True
                main_window.compose_error = True
                main_window.last_progress_update = time.time()
                
                logger.error(f"妯℃澘 {tab_name} 澶勭悊鍑洪敊: {error_msg}")
                if detail:
                    logger.error(f"璇︾粏閿欒淇℃伅: {detail}")
            except Exception as e:
                logger.error(f"鎵瑰鐞嗘ā寮忎笅閿欒鍥炶皟鍑洪敊: {str(e)}")
                # 纭繚鍗充娇鍑洪敊锛屼篃璁剧疆瀹屾垚鏍囧織
                main_window.compose_completed = True
                main_window.compose_error = True
                main_window.last_progress_update = time.time()
        
        # 瑕嗙洊鏂规硶
        main_window.on_compose_error = batch_on_error
        
        # 鑷姩涓烘柊鐨勬爣绛鹃〉鍒涘缓缂栧彿
        tab_name = f"妯℃澘 {len(self.tabs) + 1}"
        
        # 娣诲姞鏍囩椤?        tab_index = self.tab_widget.addTab(main_window, tab_name)
        self.tab_widget.setCurrentIndex(tab_index)
        
        # 璁板綍鏍囩椤典俊鎭?        tab_info = {
            "name": tab_name,
            "window": main_window,
            "status": "鍑嗗灏辩华",
            "last_process_time": None,
            "file_path": "",
            "folder_path": "",
            "tab_index": tab_index,  # 淇濆瓨鏍囩椤电储寮?            "instance_id": instance_id  # 淇濆瓨瀹炰緥ID
        }
        
        self.tabs.append(tab_info)
        
        # 鏇存柊浠诲姟琛ㄦ牸
        self._update_tasks_table()
        
        # 濡傛灉鏄涓€涓爣绛鹃〉锛岄粯璁ら€変腑
        if len(self.tabs) == 1:
            # 鏌ユ壘琛ㄦ牸涓殑澶嶉€夋
            checkbox_container = self.tasks_table.cellWidget(0, 0)
            if checkbox_container:
                checkbox = checkbox_container.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(True)
        
        logger.info(f"宸叉坊鍔犳柊妯℃澘鏍囩椤? {tab_name}, 瀹炰緥ID: {instance_id}")
        
        # 鑷姩淇濆瓨褰撳墠妯℃澘鐘舵€?        self._save_template_state()
        
        return tab_index
    
    def _update_tasks_table(self):
        """鏇存柊浠诲姟琛ㄦ牸"""
        self.tasks_table.setRowCount(len(self.tabs))
        
        for row, tab in enumerate(self.tabs):
            # 澶嶉€夋
            checkbox = QCheckBox()
            checkbox.setChecked(True)  # 榛樿鍕鹃€?            checkbox_container = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_container)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            
            # 淇濆瓨tab_index鍒板閫夋鐨勫睘鎬т腑锛屼互渚垮湪閫夋嫨鏃舵纭搴?            checkbox.setProperty("tab_index", row)
            
            self.tasks_table.setCellWidget(row, 0, checkbox_container)
            
            # 妯℃澘鍚嶇О
            self.tasks_table.setItem(row, 1, QTableWidgetItem(tab["name"]))
            
            # 鐘舵€?            status_item = QTableWidgetItem(tab["status"])
            if tab["status"] == "瀹屾垚":
                status_item.setForeground(QColor("#4CAF50"))
            elif tab["status"] == "澶勭悊涓?:
                status_item.setForeground(QColor("#2196F3"))
            elif tab["status"] == "绛夊緟涓?:
                status_item.setForeground(QColor("#FF9800"))
            elif tab["status"] == "澶辫触":
                status_item.setForeground(QColor("#F44336"))
            self.tasks_table.setItem(row, 2, status_item)
            
            # 澶勭悊鏁伴噺
            process_count = tab.get("process_count", 0)
            self.tasks_table.setItem(row, 3, QTableWidgetItem(str(process_count)))
            
            # 澶勭悊鏃堕棿
            process_time = tab.get("process_time", "-")
            if isinstance(process_time, (int, float)) and process_time > 0:
                time_str = self._format_time(process_time)
            else:
                time_str = "-"
            self.tasks_table.setItem(row, 4, QTableWidgetItem(time_str))
            
            # 鏈€鍚庡鐞嗘椂闂?            last_time = tab.get("last_process_time", "-")
            if last_time is None:
                last_time = "-"
            self.tasks_table.setItem(row, 5, QTableWidgetItem(last_time))
        
        # 鏇存柊缁熻鍖哄煙
        self.label_total_videos.setText(f"鎬昏棰戞暟: {self.total_processed_count}")
        
        if self.total_process_time > 0:
            self.label_total_time.setText(f"鎬荤敤鏃? {self._format_time(self.total_process_time)}")
        else:
            self.label_total_time.setText("鎬荤敤鏃? -")
        
        # 濡傛灉鏈夌粺璁′俊鎭紝鍦ㄧ姸鎬佹爮鏄剧ず
        if self.total_processed_count > 0:
            self.statusBar.showMessage(f"鎬昏: 澶勭悊浜?{self.total_processed_count} 涓棰戯紝鎬昏€楁椂 {self._format_time(self.total_process_time)}")
    
    def _format_time(self, seconds):
        """灏嗙鏁版牸寮忓寲涓烘椂鍒嗙"""
        if seconds < 60:
            return f"{seconds:.1f}绉?
        elif seconds < 3600:
            minutes = int(seconds // 60)
            seconds = seconds % 60
            return f"{minutes}鍒唟seconds:.1f}绉?
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            seconds = seconds % 60
            return f"{hours}鏃秢minutes}鍒唟seconds:.1f}绉?
    
    def _on_select_all(self):
        """鍏ㄩ€夋垨鍙栨秷鍏ㄩ€?""
        # 鑾峰彇褰撳墠鏄惁鍏ㄩ€?        if self.tasks_table.rowCount() == 0:
            return
            
        # 妫€鏌ョ涓€涓閫夋鐨勭姸鎬侊紝骞舵嵁姝ゅ垏鎹㈡墍鏈夊閫夋
        first_checkbox = self.tasks_table.cellWidget(0, 0)
        if isinstance(first_checkbox, QCheckBox):
            new_state = not first_checkbox.isChecked()
            
            # 鏇存柊鎵€鏈夊閫夋
            for row in range(self.tasks_table.rowCount()):
                checkbox = self.tasks_table.cellWidget(row, 0)
                if isinstance(checkbox, QCheckBox):
                    checkbox.setChecked(new_state)
            
            # 鏇存柊鎸夐挳鏂囨湰
            self.btn_select_all.setText("鍙栨秷鍏ㄩ€? if new_state else "鍏ㄩ€?)
    
    def _on_refresh_all_counts(self):
        """鎵归噺鍒锋柊鎵€鏈夋ā鏉跨殑绱犳潗鏁伴噺"""
        if not self.tabs:
            QMessageBox.information(self, "鍒锋柊绱犳潗鏁伴噺", "娌℃湁鎵撳紑鐨勬ā鏉匡紝鏃犳硶鍒锋柊")
            return
        
        success_count = 0
        failed_tabs = []
        
        # 璁剧疆绛夊緟鍏夋爣
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.status_label.setText("姝ｅ湪鍒锋柊绱犳潗鏁伴噺...")
        
        try:
            for i, tab in enumerate(self.tabs):
                if "window" in tab and tab["window"]:
                    window = tab["window"]
                    tab_name = tab["name"]
                    
                    try:
                        # 妫€鏌ユ槸鍚︽湁_update_media_counts鏂规硶
                        if hasattr(window, "_update_media_counts") and callable(window._update_media_counts):
                            # 璋冪敤妯℃澘鐨刜update_media_counts鏂规硶
                            window._update_media_counts()
                            success_count += 1
                            logger.info(f"宸插埛鏂版ā鏉?'{tab_name}' 鐨勭礌鏉愭暟閲?)
                        else:
                            logger.warning(f"妯℃澘 '{tab_name}' 涓嶆敮鎸佸埛鏂扮礌鏉愭暟閲?)
                            failed_tabs.append(f"{tab_name} (涓嶆敮鎸佸埛鏂?")
                    except Exception as e:
                        logger.error(f"鍒锋柊妯℃澘 '{tab_name}' 绱犳潗鏁伴噺鏃跺嚭閿? {str(e)}")
                        failed_tabs.append(f"{tab_name} (閿欒: {str(e)})")
            
            # 鏇存柊瀹屾垚鍚庢樉绀虹粨鏋?            if success_count > 0:
                result_message = f"宸叉垚鍔熷埛鏂?{success_count} 涓ā鏉跨殑绱犳潗鏁伴噺"
                if failed_tabs:
                    result_message += f"\n\n浠ヤ笅妯℃澘鍒锋柊澶辫触:\n" + "\n".join(failed_tabs)
                
                QMessageBox.information(self, "鍒锋柊瀹屾垚", result_message)
                self.status_label.setText(f"宸插埛鏂?{success_count} 涓ā鏉跨殑绱犳潗鏁伴噺")
            else:
                error_message = "鎵€鏈夋ā鏉垮埛鏂板け璐?
                if failed_tabs:
                    error_message += f"\n\n璇︾粏淇℃伅:\n" + "\n".join(failed_tabs)
                
                QMessageBox.warning(self, "鍒锋柊澶辫触", error_message)
                self.status_label.setText("鍒锋柊绱犳潗鏁伴噺澶辫触")
        finally:
            # 鎭㈠鍏夋爣
            QApplication.restoreOverrideCursor()
    
    def _on_start_batch(self):
        """寮€濮嬫壒閲忓鐞?""
        # 妫€鏌ユ槸鍚︽湁閫変腑鐨勪换鍔?        selected_tasks = []
        selected_indexes = []  # 瀛樺偍瀹為檯tab绱㈠紩
        
        for row in range(self.tasks_table.rowCount()):
            checkbox_container = self.tasks_table.cellWidget(row, 0)
            if checkbox_container:
                checkbox = checkbox_container.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    # 浣跨敤瀛樺偍鍦ㄥ閫夋灞炴€т腑鐨則ab_index
                    tab_index = checkbox.property("tab_index")
                    if isinstance(tab_index, (int)):
                        selected_indexes.append(int(tab_index))
                    else:
                        # 鍏煎鏃х増鏈紝鐩存帴浣跨敤琛岀储寮?                        selected_indexes.append(row)
        
        if not selected_indexes:
            QMessageBox.warning(self, "鎵归噺澶勭悊", "璇疯嚦灏戦€夋嫨涓€涓ā鏉胯繘琛屽鐞?)
            return
            
        # 纭繚selected_indexes涓殑绱㈠紩鏈夋晥锛岃繃婊ゆ帀瓒呭嚭鑼冨洿鐨勭储寮?        valid_indexes = [idx for idx in selected_indexes if 0 <= idx < len(self.tabs)]
        if len(valid_indexes) < len(selected_indexes):
            logger.warning(f"杩囨护鎺変簡{len(selected_indexes) - len(valid_indexes)}涓棤鏁堢殑绱㈠紩")
            selected_indexes = valid_indexes
            
        if not selected_indexes:
            QMessageBox.warning(self, "鎵归噺澶勭悊", "娌℃湁鏈夋晥鐨勬ā鏉垮彲浠ュ鐞?)
            return
        
        # 纭寮€濮嬪鐞?        reply = QMessageBox.question(
            self, 
            "鎵归噺澶勭悊", 
            f"鍗冲皢寮€濮嬪鐞?{len(selected_indexes)} 涓ā鏉匡紝鏄惁缁х画锛?,
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            logger.info("鐢ㄦ埛璇锋眰鍋滄鎵归噺澶勭悊")
            
            # 鍋滄褰撳墠澶勭悊
            if self.current_processing_tab is not None:
                tab_idx = self.current_processing_tab
                if 0 <= tab_idx < len(self.tabs):
                    # 鑾峰彇MainWindow瀹炰緥骞惰皟鐢ㄥ仠姝㈡柟娉?                    main_window = self.tabs[tab_idx]["window"]
                    if main_window:
                        try:
                            logger.info(f"姝ｅ湪鍋滄褰撳墠澶勭悊浠诲姟: {self.tabs[tab_idx]['name']}")
                            main_window.on_stop_compose()
                            
                            # 寮哄埗娓呯悊璧勬簮
                            if hasattr(main_window, "processor") and main_window.processor:
                                if hasattr(main_window.processor, "clean_temp_files"):
                                    main_window.processor.clean_temp_files()
                                main_window.processor = None
                        except Exception as e:
                            logger.error(f"鍋滄澶勭悊鏃跺嚭閿? {str(e)}")
            
            # 娓呯┼闃熷垪
            previous_queue = self.processing_queue.copy() if self.processing_queue else []
            self.processing_queue = []
            
            # 鏇存柊鐣岄潰鐘舵€?            self.label_current_task.setText("褰撳墠浠诲姟: 宸插仠姝?)
            self.label_queue.setText("闃熷垪: 0/0")
            
            # 鎭㈠鐣岄潰鐘舵€?            self._reset_batch_ui()
            
            # 閲嶇疆鎵€鏈夊鐞嗕腑鎴栫瓑寰呬腑鐨勪换鍔＄姸鎬?            for i, tab in enumerate(self.tabs):
                if tab["status"] in ["澶勭悊涓?, "绛夊緟涓?]:
                    tab["status"] = "宸插仠姝?
                    
            # 璁板綍鏃ュ織
            if previous_queue:
                logger.info(f"鍋滄浜嗕互涓嬩换鍔＄储寮曠殑澶勭悊: {previous_queue}")
                
            # 鏇存柊浠诲姟琛ㄦ牸
            self._update_tasks_table()
            
            # 鎵ц鍨冨溇鍥炴敹
            gc.collect()
    
    def _process_next_task(self):
        """澶勭悊闃熷垪涓殑涓嬩竴涓换鍔?""
        # 棣栧厛妫€鏌ユ槸鍚﹁繕鍦ㄦ壒澶勭悊杩囩▼涓?        if not self.is_processing:
            logger.info("鎵瑰鐞嗗凡鍋滄锛屼笉鍐嶇户缁鐞嗛槦鍒?)
            self.statusBar.showMessage("鎵瑰鐞嗗凡鍋滄", 3000)
            return
        
        # 妫€鏌ラ槦鍒楁槸鍚︿负绌?        if not self.processing_queue:
            logger.info("鎵瑰鐞嗛槦鍒楀凡澶勭悊瀹屾垚")
            
            # 璁＄畻鎬荤殑澶勭悊鏃堕棿
            if self.batch_start_time:
                total_batch_time = time.time() - self.batch_start_time
                self.total_process_time = total_batch_time
                
                # 鏄剧ず瀹屾垚淇℃伅
                completion_message = f"鎵归噺澶勭悊瀹屾垚锛佹€昏澶勭悊浜?{self.total_processed_count} 涓棰戯紝鎬昏€楁椂 {self._format_time(total_batch_time)}"
                self.statusBar.showMessage(completion_message, 0) # 0琛ㄧず涓嶄細鑷姩娑堝け
                
                # 寮瑰嚭鎻愮ず閫氱煡
                QMessageBox.information(self, "鎵归噺澶勭悊瀹屾垚", completion_message)
            else:
                self.statusBar.showMessage("鎵归噺澶勭悊瀹屾垚锛?, 5000)
                QMessageBox.information(self, "鎵归噺澶勭悊瀹屾垚", "鎵€鏈夐€変腑鐨勬ā鏉垮鐞嗗凡瀹屾垚锛?)
                
            self._reset_batch_ui()
            # 鍙戝嚭鎻愮ず闊筹紙濡傛灉鍚敤锛?            QApplication.beep()
            return
        
        logger.info(f"澶勭悊闃熷垪涓殑涓嬩竴涓换鍔★紝褰撳墠闃熷垪闀垮害: {len(self.processing_queue)}")
        
        # 鑾峰彇涓嬩竴涓换鍔＄储寮?        next_idx = self.processing_queue[0]
        self.processing_queue.pop(0)
        
        if next_idx < 0 or next_idx >= len(self.tabs):
            logger.error(f"鏃犳晥鐨勪换鍔＄储寮? {next_idx}锛岃烦杩囨浠诲姟")
            QTimer.singleShot(100, self._process_next_task)
            return
        
        # 鑾峰彇瀵瑰簲鐨勬爣绛鹃〉淇℃伅
        tab = self.tabs[next_idx]
        self.current_processing_tab = next_idx
        
        # 璁板綍浠诲姟寮€濮嬫椂闂?        tab["start_time"] = time.time()
        
        logger.info(f"寮€濮嬪鐞嗕换鍔? {tab['name']}锛岀储寮? {next_idx}")
        
        # 鏇存柊鐘舵€?        tab["status"] = "澶勭悊涓?
        self._update_tasks_table()
        
        # 鏇存柊闃熷垪鐘舵€?- 鍙绠楀綋鍓嶆壒娆′腑琚€変腑鐨勪换鍔?        # 娉ㄦ剰锛氭澶勮绠楅€昏緫鏄鐞嗛槦鍒楃殑鎬绘暟 = 宸插畬鎴愪换鍔℃暟 + 闃熷垪涓墿浣欎换鍔℃暟 + 褰撳墠姝ｅ湪澶勭悊鐨勪换鍔?1)
        completed_tasks = sum(1 for t in self.tabs if t["status"] == "瀹屾垚")
        total_selected_tasks = completed_tasks + len(self.processing_queue) + 1  # 宸插畬鎴愮殑浠诲姟 + 闃熷垪涓墿浣欑殑浠诲姟 + 褰撳墠姝ｅ湪澶勭悊鐨勪换鍔?        
        self.label_queue.setText(f"闃熷垪: {completed_tasks}/{total_selected_tasks}")
        
        # 鏇存柊褰撳墠浠诲姟鏍囩
        self.label_current_task.setText(f"褰撳墠浠诲姟: {tab['name']}")
        
        # 鑾峰彇鏍囩椤电殑涓荤獥鍙ｅ疄渚?        window = tab.get("window")
        if not window:
            logger.error(f"鏍囩椤?{next_idx} 鐨勭獥鍙ｅ疄渚嬩负绌猴紝璺宠繃姝や换鍔?)
            self.current_processing_tab = None
            tab["status"] = "澶辫触"
            self._update_tasks_table()
            QTimer.singleShot(100, self._process_next_task)
            return
        
        # 鏇存柊杩涘害鏉?- 浣跨敤瀹為檯瀹屾垚姣斾緥
        if total_selected_tasks > 0:
            progress_percentage = (completed_tasks / total_selected_tasks) * 100
            self.batch_progress.setValue(int(progress_percentage))
        
        # 鏄剧ず褰撳墠澶勭悊鐨勪换鍔′俊鎭?        self.statusBar.showMessage(f"姝ｅ湪澶勭悊: {tab['name']}")
        
        # 纭繚UI鏇存柊
        QApplication.processEvents()
        
        try:
            # 璁剧疆涓€涓鏌ュ畬鎴愮姸鎬佺殑瀹氭椂鍣ㄥ嚱鏁?            def check_completion():
                try:
                    if not self.is_processing:
                        logger.info("鎵瑰鐞嗗凡鍋滄锛屼笉鍐嶆鏌ヤ换鍔″畬鎴愮姸鎬?)
                        return
                    
                    # 娣诲姞鏇磋缁嗙殑鏃ュ織锛屽府鍔╄瘖鏂棶棰?                    logger.debug(f"妫€鏌ヤ换鍔?{tab['name']} 瀹屾垚鐘舵€?")
                    
                    # 妫€鏌ョ嚎绋嬬姸鎬?                    thread_exists = hasattr(window, "processing_thread")
                    thread_running = thread_exists and window.processing_thread is not None
                    thread_alive = thread_running and (
                        hasattr(window.processing_thread, "is_alive") and 
                        window.processing_thread.is_alive()
                    )
                    
                    # 妫€鏌ュ畬鎴愭爣蹇楃姸鎬?                    has_completion_attr = hasattr(window, "compose_completed")
                    completion_flag = has_completion_attr and window.compose_completed
                    
                    # 璁板綍璇︾粏鐘舵€佹棩蹇?                    logger.debug(f"  - 绾跨▼鐘舵€? 瀛樺湪={thread_exists}, 杩愯涓?{thread_running}, 娲昏穬={thread_alive}")
                    logger.debug(f"  - 瀹屾垚鏍囧織: 瀛樺湪={has_completion_attr}, 宸茶缃?{completion_flag}")
                    
                    # 妫€鏌ユ槸鍚︽湁鏂囦欢姝ｅ湪鐢熸垚
                    is_generating_files = False
                    if hasattr(window, "processor") and window.processor:
                        is_generating_files = True
                    
                    # 妫€鏌ユ槸鍚﹀畬鎴愮殑鏉′欢锛?.绾跨▼涓嶅瓨鍦ㄦ垨宸茬粨鏉?2.鏈変笓闂ㄧ殑瀹屾垚鏍囧織
                    thread_completed = not thread_running or (thread_running and not thread_alive)
                    has_completion_flag = completion_flag
                    
                    # 娣诲姞澶勭悊鍣ㄦ鏌?- 濡傛灉澶勭悊鍣ㄥ凡琚竻绌猴紝涔熻涓哄畬鎴?                    processor_cleared = not hasattr(window, "processor") or window.processor is None
                    logger.debug(f"  - 澶勭悊鍣ㄧ姸鎬? 宸叉竻闄?{processor_cleared}, 姝ｅ湪鐢熸垚鏂囦欢={is_generating_files}")
                    
                    if thread_completed or has_completion_flag or processor_cleared:
                        # 澶勭悊宸插畬鎴愶紝鏇存柊鐘舵€?                        logger.info(f"妫€娴嬪埌浠诲姟 {tab['name']} 宸插畬鎴愶紝鏇存柊鐘舵€?)
                        
                        # 璁板綍缁撴潫鏃堕棿鍜屽鐞嗘椂闂?                        end_time = time.time()
                        if tab.get("start_time"):
                            process_time = end_time - tab["start_time"]
                            tab["process_time"] = process_time
                        
                        # 鑾峰彇澶勭悊鏁伴噺
                        process_count = 0
                        if hasattr(window, "last_compose_count"):
                            process_count = window.last_compose_count
                        tab["process_count"] = process_count
                        
                        # 鏇存柊鎬昏鏁版嵁
                        self.total_processed_count += process_count
                        if tab.get("process_time"):
                            self.total_process_time += tab["process_time"]
                        
                        # 鏇存柊鐘舵€?                        tab["status"] = "瀹屾垚"
                        tab["last_process_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        self._update_tasks_table()
                        self.current_processing_tab = None
                        
                        # 鏇存柊杩涘害淇℃伅 - 浣跨敤褰撳墠鎵规涓閫変腑鐨勪换鍔¤繘琛岃绠?                        # 娉ㄦ剰锛氭澶勫綋鍓嶄换鍔″凡琚爣璁颁负"瀹屾垚"锛屽洜姝よ绠楅€昏緫鏄?鎬绘暟 = 宸插畬鎴愪换鍔℃暟(鍖呭惈褰撳墠浠诲姟) + 闃熷垪涓墿浣欎换鍔℃暟
                        completed_tasks = sum(1 for t in self.tabs if t["status"] == "瀹屾垚")
                        total_selected_tasks = completed_tasks + len(self.processing_queue)  # 宸插畬鎴愮殑浠诲姟 + 闃熷垪涓墿浣欑殑浠诲姟
                        
                        self.label_queue.setText(f"闃熷垪: {completed_tasks}/{total_selected_tasks}")
                        
                        if total_selected_tasks > 0:
                            progress_percentage = (completed_tasks / total_selected_tasks) * 100
                            self.batch_progress.setValue(int(progress_percentage))
                        
                        # 纭繚璧勬簮琚竻鐞?                        try:
                            if hasattr(window, "processor") and window.processor:
                                if hasattr(window.processor, "stop_processing"):
                                    window.processor.stop_processing()
                                window.processor = None
                            if hasattr(window, "processing_thread") and window.processing_thread:
                                window.processing_thread = None
                        except Exception as e:
                            logger.error(f"娓呯悊璧勬簮鏃跺嚭閿? {str(e)}")
                        
                        # 澶勭悊瀹屾垚鍚庯紝绔嬪嵆鍚姩涓嬩竴涓换鍔?                        logger.info(f"鏍囩椤?{next_idx} 澶勭悊瀹屾垚锛屽噯澶囧鐞嗕笅涓€涓换鍔?)
                        
                        # 浣跨敤鐭椂闂村欢杩熻皟鐢ㄤ笅涓€涓换鍔★紝纭繚UI鏈夋椂闂存洿鏂?                        QTimer.singleShot(500, self._process_next_task)
                    else:
                        # 濡傛灉绾跨▼浠嶅湪杩愯锛屽啀娆℃鏌?                        # 涓轰簡閬垮厤鍗′綇锛屾垜浠篃妫€鏌ヤ竴涓嬫槸鍚︾嚎绋嬬‘瀹炲湪宸ヤ綔
                        if hasattr(window, "last_progress_update"):
                            current_time = time.time()
                            time_since_update = current_time - window.last_progress_update
                            logger.debug(f"  - 涓婃杩涘害鏇存柊: {time_since_update:.1f}绉掑墠")
                            
                            # 澧炲姞瓒呮椂鏃堕棿鍒?0绉掞紝瑙嗛澶勭悊鍙兘闇€瑕佹洿闀挎椂闂?                            if time_since_update > 30:  # 濡傛灉30绉掓病鏈夎繘搴︽洿鏂?                                logger.warning(f"浠诲姟 {tab['name']} 浼间箮宸插崱浣?(>30绉掓棤杩涘害鏇存柊)锛屽皾璇曢噸鍚鐞嗘祦绋?)
                                
                                # 灏濊瘯鐩存帴璋冪敤澶勭悊杩囩▼鏉ユ仮澶?                                try:
                                    # 妫€鏌ユ槸鍚︽湁杩涘害鏍囩
                                    if hasattr(window, "label_progress"):
                                        progress_text = window.label_progress.text()
                                        logger.debug(f"  - 褰撳墠杩涘害鏍囩: {progress_text}")
                                    
                                    # 濡傛灉澶勭悊鍣ㄥ瓨鍦紝灏濊瘯寮哄埗鏇存柊杩涘害鏉ヨЕ鍙戣繘搴︽娴?                                    if hasattr(window, "processor") and window.processor:
                                        if hasattr(window.processor, "report_progress"):
                                            window.processor.report_progress("鎵瑰鐞嗘ā寮忎腑閲嶆柊瑙﹀彂杩涘害鏇存柊", 50.0)
                                            window.last_progress_update = time.time()
                                            logger.info("宸查噸鏂拌Е鍙戣繘搴︽洿鏂?)
                                            QTimer.singleShot(500, check_completion)
                                            return
                                        
                                    # 濡傛灉鏃犳硶鎭㈠澶勭悊娴佺▼锛屽垯鏀惧純褰撳墠浠诲姟锛岀户缁笅涓€涓?                                    logger.warning(f"鏃犳硶鎭㈠浠诲姟 {tab['name']} 鐨勫鐞嗘祦绋嬶紝鏀惧純褰撳墠浠诲姟")
                                    tab["status"] = "澶辫触(瓒呮椂)"
                                    self._update_tasks_table()
                                    self.current_processing_tab = None
                                    
                                    # 灏濊瘯鍋滄褰撳墠浠诲姟
                                    window.on_stop_compose()
                                    
                                    # 寤惰繜涓€涓嬪啀澶勭悊涓嬩竴涓换鍔?                                    QTimer.singleShot(1000, self._process_next_task)
                                    return
                                except Exception as e:
                                    logger.error(f"灏濊瘯鎭㈠澶勭悊娴佺▼鏃跺嚭閿? {str(e)}")
                                    error_detail = traceback.format_exc()
                                    logger.error(f"璇︾粏閿欒淇℃伅: {error_detail}")
                                    
                                    # 鍋滄褰撳墠浠诲姟锛岀户缁笅涓€涓换鍔?                                    tab["status"] = "澶辫触(澶勭悊閿欒)"
                                    self._update_tasks_table()
                                    self.current_processing_tab = None
                                    window.on_stop_compose()
                                    QTimer.singleShot(1000, self._process_next_task)
                                    return
                        
                        # 鏇村揩鍦版鏌ョ姸鎬?- 1绉掓鏌ヤ竴娆?                        QTimer.singleShot(1000, check_completion)
                except Exception as e:
                    logger.error(f"妫€鏌ヤ换鍔″畬鎴愮姸鎬佹椂鍑洪敊: {str(e)}")
                    error_detail = traceback.format_exc()
                    logger.error(f"璇︾粏閿欒淇℃伅: {error_detail}")
                    
                    # 鍑洪敊鍚庝篃瑕佺户缁笅涓€涓换鍔?                    tab["status"] = "澶辫触"
                    self._update_tasks_table()
                    self.current_processing_tab = None
                    QTimer.singleShot(500, self._process_next_task)
            
            # 鍦ㄥ惎鍔ㄥ墠锛岀‘淇濈獥鍙ｅ凡缁忓垵濮嬪寲瀹屾垚
            if hasattr(window, "last_progress_update"):
                window.last_progress_update = time.time()
            else:
                # 濡傛灉娌℃湁杩欎釜灞炴€э紝娣诲姞涓€涓?                window.last_progress_update = time.time()
            
            # 閲嶇疆澶勭悊鐘舵€佹爣蹇?            window.compose_completed = False
            window.compose_error = False
            logger.info(f"寮€濮嬪鐞嗘爣绛鹃〉 {next_idx}: {tab['name']}")
            
            # 纭繚鏍囩椤靛浜庡彲瑙佺姸鎬侊紝鍒囨崲鍒扮浉搴旀爣绛?            self.tab_widget.setCurrentIndex(next_idx)
            QApplication.processEvents()  # 纭繚UI鏇存柊
            
            # 鍚姩鍚堟垚
            try:
                # 灏濊瘯瑙﹀彂鍏抽敭UI浜嬩欢锛岀‘淇濆疄闄呯偣鍑绘寜閽€屼笉鍙槸璋冪敤鍚庡彴鍑芥暟
                if hasattr(window, "btn_start_compose") and window.btn_start_compose:
                    window.btn_start_compose.click()
                    logger.info(f"閫氳繃鐐瑰嚮鎸夐挳鍚姩鍚堟垚: {tab['name']}")
                else:
                    # 濡傛灉鏃犳硶鎵惧埌鎸夐挳锛岀洿鎺ヨ皟鐢ㄦ柟娉?                    window.on_start_compose()
                    logger.info(f"閫氳繃璋冪敤鏂规硶鍚姩鍚堟垚: {tab['name']}")
            except Exception as e:
                logger.error(f"鍚姩鍚堟垚杩囩▼鏃跺嚭閿? {str(e)}")
                error_detail = traceback.format_exc()
                logger.error(f"璇︾粏閿欒淇℃伅: {error_detail}")
                
                # 灏濊瘯涓€娆＄洿鎺ユ柟娉曡皟鐢?                try:
                    window.on_start_compose()
                    logger.info("浣跨敤澶囩敤鏂规硶鍚姩鍚堟垚")
                except Exception as e2:
                    logger.error(f"澶囩敤鍚姩鏂规硶涔熷け璐? {str(e2)}")
                    # 澶辫触鍚庣户缁笅涓€涓换鍔?                    tab["status"] = "澶辫触(鏃犳硶鍚姩)"
                    self._update_tasks_table()
                    self.current_processing_tab = None
                    QTimer.singleShot(500, self._process_next_task)
                    return
            
            # 鍚姩妫€鏌ュ畬鎴愮姸鎬佺殑瀹氭椂鍣紝绋嶅井寤惰繜涓€涓嬬‘淇濆鐞嗗凡缁忓紑濮?            QTimer.singleShot(1000, check_completion)
            
        except Exception as e:
            logger.error(f"澶勭悊鏍囩椤?{next_idx} 鏃跺嚭閿? {str(e)}")
            # 娣诲姞璇︾粏鐨勯敊璇俊鎭?            error_detail = traceback.format_exc()
            logger.error(f"璇︾粏閿欒淇℃伅: {error_detail}")
            
            tab["status"] = "澶辫触"
            self._update_tasks_table()
            self.current_processing_tab = None
            
            # 鍑洪敊鍚庯紝缁х画澶勭悊涓嬩竴涓换鍔?            QTimer.singleShot(500, self._process_next_task)
    
    def closeEvent(self, event):
        """绐楀彛鍏抽棴浜嬩欢"""
        # 妫€鏌ユ槸鍚︽湁姝ｅ湪杩涜鐨勫鐞?        if self.is_processing:
            reply = QMessageBox.question(
                self, 
                "纭閫€鍑?, 
                "鎵归噺澶勭悊姝ｅ湪杩涜涓紝纭畾瑕侀€€鍑哄悧锛?,
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                event.ignore()
                return
            
            # 鍋滄鎵€鏈夊鐞?            self._on_stop_batch()
        
        try:
            # 淇濆瓨褰撳墠妯℃澘鐘舵€?            self._save_template_state()
        except Exception as e:
            logger.error(f"淇濆瓨妯℃澘鐘舵€佹椂鍑洪敊: {str(e)}")
        
        # 鎭㈠鍘熷瀵硅瘽妗嗘柟娉?        if hasattr(self, '_original_info'):
            QMessageBox.information = self._original_info
        if hasattr(self, '_original_warning'):
            QMessageBox.warning = self._original_warning
        if hasattr(self, '_original_critical'):
            QMessageBox.critical = self._original_critical
        if hasattr(self, '_original_question'):
            QMessageBox.question = self._original_question
        
        logger.info("姝ｅ湪鍏抽棴鎵€鏈夋爣绛鹃〉")
        
        # 鍏抽棴鎵€鏈夋爣绛鹃〉
        for i, tab in enumerate(self.tabs):
            if "window" in tab and tab["window"]:
                try:
                    # 鍏堟竻鐞嗚祫婧?                    window = tab["window"]
                    if hasattr(window, "processor") and window.processor:
                        window.processor = None
                    if hasattr(window, "processing_thread") and window.processing_thread:
                        window.processing_thread = None
                    
                    # 鍏抽棴绐楀彛
                    window.close()
                    
                    logger.info(f"宸插叧闂爣绛鹃〉 {i+1}/{len(self.tabs)}")
                except Exception as e:
                    logger.error(f"鍏抽棴鏍囩椤?{tab['name']} 鏃跺嚭閿? {str(e)}")
        
        # 鎵ц鍨冨溇鍥炴敹
        gc.collect()
        
        # 鎺ュ彈鍏抽棴浜嬩欢
        event.accept()
