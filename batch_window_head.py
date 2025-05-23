#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
鎵归噺澶勭悊绐楀彛
"""

import os
import sys
import time
import json
import traceback
import gc
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# 娣诲姞椤圭洰鏍圭洰褰曞埌 Python 璺緞
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from PyQt5.QtCore import Qt, QTimer, QRect, QSize, pyqtSlot, QObject, QEvent, pyqtSignal, QMetaObject, QThread, Q_ARG
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap, QFont, QResizeEvent, QCursor, QPalette, QBrush, QRadialGradient
from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, 
    QCheckBox, QProgressBar, QRadioButton, QComboBox, QLineEdit, 
    QFileDialog, QMessageBox, QDialog, QSplitter, QStatusBar, QSpacerItem,
    QSizePolicy, QFrame, QAbstractItemView, QStyle, QStyleOption, QMenu,
    QButtonGroup, QScrollArea, QTextEdit, QLayout, QAction, QToolButton,
    QDialogButtonBox, QInputDialog
)

from src.ui.main_window import MainWindow
from src.utils.logger import get_logger
from src.utils.template_state import TemplateState

logger = get_logger()

class BatchWindow(QMainWindow):
    """鎵归噺澶勭悊澶氫釜妯℃澘鐨勪富绐楀彛"""
    
    def __init__(self, parent=None):
        """鍒濆鍖栨壒閲忓鐞嗙獥鍙?""
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
        self.ui_refresh_timer.start(5000)  # 姣?绉掑埛鏂颁竴娆I
        
        logger.info("鎵归噺澶勭悊绐楀彛鍒濆鍖栧畬鎴?)
    
    def _periodic_ui_refresh(self):
        """瀹氭湡鍒锋柊UI鐘舵€?""
        try:
            # 濡傛灉褰撳墠姝ｅ湪澶勭悊浠诲姟锛屽垯涓嶅埛鏂癠I
            if self.is_processing:
                return
                
            # 妫€鏌ユ槸鍚︽湁鏍囩椤甸渶瑕佸埛鏂?            for tab in self.tabs:
                if "window" in tab and tab["window"] and tab["window"].isVisible():
                    try:
                        # 纭繚鏍囩椤靛唴瀹瑰彲瑙?                        tab["window"].update()
                    except Exception as e:
                        logger.debug(f"瀹氭湡鍒锋柊鏍囩椤?'{tab['name']}' 鏃跺嚭閿? {str(e)}")
            
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
        
        # 娣诲姞妯℃澘閫夋嫨鍣ㄦ寜閽?        self.btn_template_selector = QPushButton("妯℃澘閫夋嫨鍣?)
        self.btn_template_selector.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.btn_template_selector.setIcon(self.style().standardIcon(QStyle.SP_FileDialogListView))
        self.btn_template_selector.setToolTip("鎵撳紑澶у瀷妯℃澘閫夋嫨绐楀彛锛屾柟渚垮嬀閫夊涓ā鏉?)
        self.btn_template_selector.clicked.connect(self._open_template_selector)
        
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
        batch_buttons.addWidget(self.btn_template_selector)
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
    
    def _on_tab_close(self, index):
        """澶勭悊鏍囩椤靛叧闂簨浠?""
        # 纭繚鑷冲皯淇濈暀涓€涓爣绛鹃〉
        if self.tab_widget.count() <= 1:
            QMessageBox.warning(self, "璀﹀憡", "鑷冲皯闇€瑕佷繚鐣欎竴涓ā鏉挎爣绛鹃〉")
            return
        
        # 姝ｅ湪澶勭悊鏃朵笉鍏佽鍏抽棴鏍囩椤?        if self.is_processing:
            QMessageBox.warning(self, "璀﹀憡", "鎵归噺澶勭悊杩囩▼涓笉鑳藉叧闂爣绛鹃〉")
            return
        
        # 纭鍏抽棴
        tab_name = self.tab_widget.tabText(index)
        reply = QMessageBox.question(
            self, 
            "鍏抽棴妯℃澘", 
            f"纭畾瑕佸叧闂ā鏉?'{tab_name}' 鍚楋紵",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 浠庡垪琛ㄤ腑绉婚櫎
            closed_tab = self.tabs.pop(index)
            logger.info(f"鍏抽棴鏍囩椤? {closed_tab['name']}, 绱㈠紩: {index}")
            
            # 鍏抽棴鏍囩椤?            self.tab_widget.removeTab(index)
            
            # 鏇存柊鎵€鏈夋爣绛鹃〉鐨勭储寮?            for i, tab in enumerate(self.tabs):
                old_index = tab.get("tab_index", -1)
                tab["tab_index"] = i
                logger.debug(f"鏇存柊鏍囩椤电储寮? {tab['name']} - 浠?{old_index} 鍒?{i}")
            
            # 鏇存柊浠诲姟琛ㄦ牸
            self._update_tasks_table()
            
            # 淇濆瓨褰撳墠妯℃澘鐘舵€?            self._save_template_state()
    
    def _on_tab_double_clicked(self, index):
        """澶勭悊鏍囩椤靛弻鍑讳簨浠讹紝鍏佽鐢ㄦ埛缂栬緫鏍囩鍚嶇О"""
        # 姝ｅ湪澶勭悊鏃朵笉鍏佽缂栬緫鏍囩鍚?        if self.is_processing:
            QMessageBox.warning(self, "璀﹀憡", "鎵归噺澶勭悊杩囩▼涓笉鑳戒慨鏀规爣绛惧悕")
            return
            
        # 鑾峰彇褰撳墠鏍囩鍚?        current_name = self.tab_widget.tabText(index)
        
        # 寮瑰嚭杈撳叆瀵硅瘽妗?        new_name, ok = QInputDialog.getText(
            self, 
            "淇敼妯℃澘鍚嶇О", 
            "璇疯緭鍏ユ柊鐨勬ā鏉垮悕绉?",
            text=current_name
        )
        
        # 濡傛灉鐢ㄦ埛纭淇敼涓斿悕绉颁笉涓虹┖
        if ok and new_name.strip():
            # 鏇存柊TabWidget涓婄殑鏍囩鍚?            self.tab_widget.setTabText(index, new_name)
            
            # 鏇存柊鍐呴儴瀛樺偍鐨勬爣绛句俊鎭?            if 0 <= index < len(self.tabs):
                self.tabs[index]["name"] = new_name
                logger.info(f"妯℃澘鍚嶇О宸蹭慨鏀? '{current_name}' -> '{new_name}'")
                
                # 鏇存柊浠诲姟琛ㄦ牸
                self._update_tasks_table()
                
                # 淇濆瓨鏇存柊鍚庣殑妯℃澘鐘舵€?                self._save_template_state()
    
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
            
            # 杩炴帴澶嶉€夋鐘舵€佸彉鍖栦俊鍙?            checkbox.stateChanged.connect(self._on_checkbox_state_changed)
            
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
            
        # 鏇存柊闃熷垪淇℃伅锛氭湭寮€濮嬫壒澶勭悊鏃讹紝鏄剧ず閫変腑鐨勬ā鏉挎暟閲?        if not self.is_processing:
            self._update_queue_display()
    
    def _update_queue_display(self):
        """鏇存柊闃熷垪鏄剧ず淇℃伅"""
        if self.is_processing:
            return
        
        selected_count = 0
        for row in range(self.tasks_table.rowCount()):
            checkbox_container = self.tasks_table.cellWidget(row, 0)
            if checkbox_container:
                checkbox = checkbox_container.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    selected_count += 1
        
        self.label_queue.setText(f"闃熷垪: 0/{selected_count}")
        logger.debug(f"鏇存柊闃熷垪鏄剧ず淇℃伅: 0/{selected_count}")
    
    def _on_checkbox_state_changed(self, state):
        """澶勭悊澶嶉€夋鐘舵€佸彉鍖?""
        if not self.is_processing:
            self._update_queue_display()
    
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
        first_checkbox_container = self.tasks_table.cellWidget(0, 0)
        if first_checkbox_container:
            first_checkbox = first_checkbox_container.findChild(QCheckBox)
            if first_checkbox:
                new_state = not first_checkbox.isChecked()
                
                # 鏇存柊鎵€鏈夊閫夋
                for row in range(self.tasks_table.rowCount()):
                    checkbox_container = self.tasks_table.cellWidget(row, 0)
                    if checkbox_container:
                        checkbox = checkbox_container.findChild(QCheckBox)
                        if checkbox:
                            checkbox.setChecked(new_state)
                
                # 鏇存柊鎸夐挳鏂囨湰
                self.btn_select_all.setText("鍙栨秷鍏ㄩ€? if new_state else "鍏ㄩ€?)
                
                # 鏇存柊闃熷垪鏄剧ず
                selected_count = self.tasks_table.rowCount() if new_state else 0
                self.label_queue.setText(f"闃熷垪: 0/{selected_count}")
                
                # 鏇存柊鐘舵€佹爮鏄剧ず
                if new_state:
                    self.statusBar.showMessage(f"宸查€夋嫨鍏ㄩ儴 {selected_count} 涓ā鏉?, 3000)
                else:
                    self.statusBar.showMessage("宸插彇娑堥€夋嫨鎵€鏈夋ā鏉?, 3000)
    
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
            # 鍏堝仠姝㈠彲鑳芥鍦ㄨ繍琛岀殑浠讳綍澶勭悊
            self._reset_batch_ui()
            
            # 鍦ㄥ紑濮嬪墠鍏堣繘琛屽瀮鍦惧洖鏀讹紝閲婃斁璧勬簮
            gc.collect()
            
            # 閲嶇疆缁熻淇℃伅
            self.batch_start_time = time.time()
            self.total_processed_count = 0
            self.total_process_time = 0
            
            # 娓呯┖澶勭悊闃熷垪骞堕噸鏂版坊鍔犻€変腑鐨勪换鍔?            self.processing_queue = selected_indexes.copy()
            
            # 璁板綍澶勭悊闃熷垪鏃ュ織
            queue_info = []
            for idx in selected_indexes:
                if 0 <= idx < len(self.tabs):
                    queue_info.append(f"{idx}:{self.tabs[idx]['name']}")
            logger.info(f"澶勭悊闃熷垪: {', '.join(queue_info)}")
            
            # 鏇存柊鐣岄潰鐘舵€?            # 棣栧厛閲嶇疆鎵€鏈夋爣绛鹃〉鐨勭姸鎬?            for tab in self.tabs:
                if tab["status"] in ["澶勭悊涓?, "绛夊緟涓?]:
                    tab["status"] = "鍑嗗灏辩华"
            
            # 鐒跺悗璁剧疆閫変腑鏍囩椤电殑鐘舵€?            for idx in selected_indexes:
                if 0 <= idx < len(self.tabs):
                    self.tabs[idx]["status"] = "绛夊緟涓?
                    # 閲嶇疆鍚勪釜浠诲姟鐨勫鐞嗙粺璁?                    self.tabs[idx]["process_count"] = 0
                    self.tabs[idx]["process_time"] = 0
                    self.tabs[idx]["start_time"] = None
            
            self._update_tasks_table()
            
            # 鏇存柊鐣岄潰鐘舵€?            self.is_processing = True
            self.btn_start_batch.setEnabled(False)
            self.btn_stop_batch.setEnabled(True)
            
            # 鏇存柊闃熷垪鐘舵€?            self.label_queue.setText(f"闃熷垪: 0/{len(selected_indexes)}")
            
            # 鎵瑰鐞嗘ā寮忎笅鍚敤瀵硅瘽妗嗚繃婊?            logger.info("鍚敤鎵瑰鐞嗘ā寮忓璇濇杩囨护")
            
            # 纭繚UI瀹屽叏鏇存柊
            QApplication.processEvents()
            
            # 浣跨敤瀹氭椂鍣ㄥ欢杩熷紑濮嬪鐞嗭紝缁橴I涓€浜涘搷搴旀椂闂?            QTimer.singleShot(500, self._process_next_task)
            
            # 璁板綍璇︾粏鏃ュ織锛屼互渚挎帓鏌ラ棶棰?            logger.info(f"灏嗗鐞嗕互涓嬫爣绛鹃〉绱㈠紩: {selected_indexes}")
    
    def _on_stop_batch(self):
        """鍋滄鎵归噺澶勭悊"""
        if not self.is_processing:
            return
        
        # 纭鍋滄
        reply = QMessageBox.question(
            self, 
            "鍋滄澶勭悊", 
            "纭畾瑕佸仠姝㈠綋鍓嶇殑鎵归噺澶勭悊浠诲姟鍚楋紵",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
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
            
            # 娓呯┖闃熷垪
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
    
    def _reset_batch_ui(self):
        """閲嶇疆鎵瑰鐞嗙晫闈㈢姸鎬?""
        logger.info("閲嶇疆鎵瑰鐞嗙晫闈㈢姸鎬?)
        
        # 澶囦唤骞舵竻绌哄鐞嗛槦鍒?        original_queue = list(self.processing_queue) if self.processing_queue else []
        self.processing_queue = []
        
        # 閲嶇疆鐘舵€佸彉閲?        self.is_processing = False
        current_tab = self.current_processing_tab  # 淇濆瓨浠ヤ究璁板綍
        self.current_processing_tab = None
        
        # 鏇存柊UI鍏冪礌
        self.btn_start_batch.setEnabled(True)
        self.btn_stop_batch.setEnabled(False)
        self.batch_progress.setValue(0)
        self.statusBar.showMessage("鎵归噺澶勭悊宸插仠姝?, 3000)
        
        # 濡傛灉涓嶆槸澶勭悊瀹屾垚鍚庤皟鐢ㄧ殑閲嶇疆锛岄偅涔堜篃閲嶇疆缁熻淇℃伅
        if original_queue and len(self.tabs) > 0 and not any(tab["status"] == "瀹屾垚" for tab in self.tabs):
            self.total_processed_count = 0
            self.total_process_time = 0
            self.batch_start_time = None
            self.label_total_videos.setText("鎬昏棰戞暟: 0")
            self.label_total_time.setText("鎬荤敤鏃? -")
            logger.info(f"閲嶇疆缁熻淇℃伅锛屾湁 {len(original_queue)} 涓换鍔℃湭澶勭悊")
        
        # 灏濊瘯閲婃斁鎵€鏈夋爣绛鹃〉鐨勮祫婧?        for tab in self.tabs:
            if "window" in tab and tab["window"]:
                try:
                    window = tab["window"]
                    # 灏濊瘯娓呯悊澶勭悊鍣ㄨ祫婧?                    if hasattr(window, "processor") and window.processor:
                        if hasattr(window.processor, "stop_processing"):
                            try:
                                window.processor.stop_processing()
                            except:
                                pass
                        window.processor = None
                    
                    # 閲嶇疆澶勭悊绾跨▼
                    if hasattr(window, "processing_thread") and window.processing_thread:
                        window.processing_thread = None
                except Exception as e:
                    logger.error(f"閲嶇疆鏍囩椤佃祫婧愭椂鍑洪敊: {str(e)}")
        
        # 寮哄埗澶勭悊鎵€鏈夋寕璧风殑浜嬩欢
        QApplication.processEvents()
        
        # 鎵ц鍨冨溇鍥炴敹
        gc.collect()
        
        # 鍒锋柊鎵€鏈夋爣绛鹃〉鏄剧ず
        self._refresh_all_tabs_ui()
        
        # 璁板綍璇︾粏鏃ュ織
        if current_tab is not None:
            logger.info(f"閲嶇疆鎵瑰鐞嗘ā寮忥紝涔嬪墠澶勭悊鐨勬爣绛鹃〉绱㈠紩: {current_tab}")
        if original_queue:
            logger.info(f"澶勭悊闃熷垪宸叉竻绌猴紝鍘熼槦鍒楀寘鍚? {original_queue}")
        
        logger.info("鎵瑰鐞嗘ā寮忓凡閲嶇疆")
    
    def _refresh_all_tabs_ui(self):
        """鍒锋柊鎵€鏈夋爣绛鹃〉鐨刄I鏄剧ず"""
        logger.info("寮€濮嬪埛鏂版墍鏈夋爣绛鹃〉UI鏄剧ず")
        try:
            # 鏇存柊浠诲姟琛ㄦ牸
            self._update_tasks_table()
            
            # 鍒锋柊鏍囩椤垫帶浠?            self.tab_widget.update()
            
            # 閬嶅巻鎵€鏈夋爣绛鹃〉锛屽埛鏂癠I
            for i in range(self.tab_widget.count()):
                # 鑾峰彇鏍囩椤电獥鍙?                tab_widget = self.tab_widget.widget(i)
                if tab_widget:
                    # 鍒囨崲鍒拌鏍囩椤典互纭繚鍏跺彲瑙?                    self.tab_widget.setCurrentIndex(i)
                    
                    # 灏濊瘯鍒锋柊鏍囩椤电殑UI
                    try:
                        # 寮哄埗閲嶇粯
                        tab_widget.update()
                        
                        # 濡傛灉鏈夊瓙绐楀彛锛屼篃鍒锋柊瀹冧滑
                        for child in tab_widget.findChildren(QWidget):
                            if child and not child.isHidden():
                                child.update()
                    except Exception as e:
                        logger.error(f"鍒锋柊鏍囩椤?{i} UI鏃跺嚭閿? {str(e)}")
                
                # 纭繚Qt浜嬩欢寰幆澶勭悊缁樺埗浜嬩欢
                QApplication.processEvents()
            
            # 鏈€鍚庡啀娆℃洿鏂版暣涓獥鍙?            self.update()
            
            logger.info("鎵€鏈夋爣绛鹃〉UI鍒锋柊瀹屾垚")
        except Exception as e:
            logger.error(f"鍒锋柊鎵€鏈夋爣绛鹃〉UI鏃跺嚭閿? {str(e)}")
    
    def _process_next_task(self):
        """澶勭悊闃熷垪涓殑涓嬩竴涓换鍔?""
        # 棣栧厛妫€鏌ユ槸鍚﹁繕鍦ㄦ壒澶勭悊杩囩▼涓?        if not self.is_processing:
            logger.info("鎵瑰鐞嗗凡鍋滄锛屼笉鍐嶇户缁鐞嗛槦鍒?)
            self.statusBar.showMessage("鎵瑰鐞嗗凡鍋滄", 3000)
            return
        
        # 妫€鏌ラ槦鍒楁槸鍚︿负绌?        if not self.processing_queue:
            logger.info("鎵瑰鐞嗛槦鍒楀凡澶勭悊瀹屾瘯")
            
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
            
            # 寮哄埗娓呯悊鎵€鏈夋爣绛鹃〉鐨勮祫婧?            try:
                logger.info("鎵瑰鐞嗗畬鎴愶紝娓呯悊鎵€鏈夋爣绛鹃〉璧勬簮...")
                # 娓呯悊姣忎釜鏍囩椤电殑澶勭悊鍣ㄨ祫婧?                for tab in self.tabs:
                    if "window" in tab and tab["window"]:
                        window = tab["window"]
                        if hasattr(window, "processor") and window.processor:
                            try:
                                # 浣跨敤鏂版坊鍔犵殑璧勬簮閲婃斁鏂规硶
                                if hasattr(window.processor, "release_resources"):
                                    logger.info(f"閲婃斁鏍囩椤?'{tab['name']}' 鐨勫鐞嗗櫒璧勬簮")
                                    try:
                                        # 瀹夊叏鍦伴噴鏀惧鐞嗗櫒璧勬簮锛岄槻姝㈡竻鐞哢I鍏冪礌
                                        window.processor.release_resources()
                                    except Exception as e:
                                        logger.error(f"浣跨敤release_resources鏂规硶閲婃斁璧勬簮鏃跺嚭閿? {str(e)}")
                                elif hasattr(window.processor, "clean_temp_files"):
                                    # 閫€鍖栨柟妗堬細鑷冲皯娓呯悊涓存椂鏂囦欢
                                    logger.info(f"浣跨敤clean_temp_files澶囬€夋柟妗堟竻鐞嗘爣绛鹃〉 '{tab['name']}' 鐨勪复鏃舵枃浠?)
                                    try:
                                        window.processor.clean_temp_files()
                                    except Exception as e:
                                        logger.error(f"浣跨敤clean_temp_files鏂规硶娓呯悊涓存椂鏂囦欢鏃跺嚭閿? {str(e)}")
                                
                                # 娓呯┖澶勭悊鍣ㄥ紩鐢?                                window.processor = None
                            except Exception as e:
                                logger.error(f"閲婃斁鏍囩椤?'{tab['name']}' 璧勬簮鏃跺嚭閿? {str(e)}")
                        
                        # 纭繚绐楀彛UI鍏冪礌瀹屽ソ
                        try:
                            # 鍒锋柊绐楀彛
                            if hasattr(window, "update"):
                                window.update()
                                
                            # 纭繚绐楀彛缁勪欢鍙
                            for widget_name in ["stackedWidget", "panel_material", "panel_setting", "save_dir_display"]:
                                if hasattr(window, widget_name):
                                    widget = getattr(window, widget_name)
                                    if widget and hasattr(widget, "show"):
                                        widget.show()
                                        if hasattr(widget, "update"):
                                            widget.update()
                        except Exception as e:
                            logger.error(f"鍒锋柊绐楀彛UI鍏冪礌鏃跺嚭閿? {str(e)}")
                
                # 鎵ц涓€娆″畬鏁寸殑鍨冨溇鍥炴敹
                import gc
                gc.collect(0)
                gc.collect(1)
                gc.collect(2)
                
                # 寮哄埗鎵ц涓€娆t浜嬩欢澶勭悊
                QApplication.processEvents()
                
                # 鍒锋柊鐣岄潰鏄剧ず
                self._refresh_all_tabs_ui()
                
                logger.info("鎵€鏈夋爣绛鹃〉璧勬簮娓呯悊瀹屾垚")
                
                # 纭繚鎵€鏈夋爣绛鹃〉浠嶇劧鍙
                for i, tab in enumerate(self.tabs):
                    if "window" in tab and tab["window"]:
                        try:
                            # 鍒锋柊鏍囩椤垫樉绀?                            self.tab_widget.setCurrentIndex(i)
                            QApplication.processEvents()
                            self.tab_widget.update()
                            
                            # 棰濆纭繚鏍囩椤靛唴瀹规樉绀烘纭?                            tab_widget = self.tab_widget.widget(i)
                            if tab_widget:
                                tab_widget.show()
                                tab_widget.update()
                        except Exception as e:
                            logger.error(f"鍒锋柊鏍囩椤?{tab['name']} 鏄剧ず鏃跺嚭閿? {str(e)}")
                
                # 鏈€鍚庡啀鍒锋柊涓€娆℃暣涓壒澶勭悊绐楀彛
                self.update()
                QApplication.processEvents()
                
                # 浣跨敤涓撻棬鐨勫嚱鏁板叏闈㈠埛鏂版墍鏈夋爣绛鹃〉UI
                self._refresh_tabs_after_resource_release()
                
                # 纭繚涓荤晫闈㈡樉绀烘甯?                self.show()
                self.activateWindow()
                self.raise_()
                QApplication.processEvents()
            except Exception as e:
                logger.error(f"鎵瑰鐞嗙粨鏉熸竻鐞嗚祫婧愭椂鍑洪敊: {str(e)}")
                
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
        
        # 鍦ㄥ紑濮嬫柊妯℃澘鍓嶆墽琛屼竴娆″唴瀛樻竻鐞嗭紝纭繚绯荤粺鍐呭瓨鍏呰冻
        try:
            # 鎵ц鍐呭瓨娓呯悊
            import gc
            logger.info("鍦ㄥ紑濮嬫柊妯℃澘鍓嶆墽琛屽唴瀛樻竻鐞?..")
            before_count = gc.get_count()
            # 鎵ц瀹屾暣鐨勫瀮鍦惧洖鏀?            gc.collect(0)  # 鏀堕泦绗?浠ｅ璞?            gc.collect(1)  # 鏀堕泦绗?浠ｅ璞?            gc.collect(2)  # 鏀堕泦绗?浠ｅ璞?            after_count = gc.get_count()
            logger.info(f"鍐呭瓨娓呯悊瀹屾垚: {before_count} -> {after_count}")
            
            # 寮哄埗鎵ц涓€娆t浜嬩欢澶勭悊
            QApplication.processEvents()
        except Exception as e:
            logger.error(f"鍐呭瓨娓呯悊杩囩▼涓嚭閿? {str(e)}")
            # 閿欒涓嶅簲闃绘缁х画杩涜
        
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
                        
                        # 纭繚褰诲簳娓呯悊璧勬簮锛岄伩鍏嶅唴瀛樻硠婕?                        try:
                            # 1. 鍏抽棴瑙嗛澶勭悊鍣ㄧ殑鎵€鏈夎祫婧?                            if hasattr(window, "processor") and window.processor:
                                # 浣跨敤鏂版坊鍔犵殑璧勬簮閲婃斁鏂规硶
                                if hasattr(window.processor, "release_resources"):
                                    logger.info("浣跨敤release_resources鏂规硶閲婃斁澶勭悊鍣ㄨ祫婧?..")
                                    window.processor.release_resources()
                                elif hasattr(window.processor, "clean_temp_files"):
                                    logger.info("寮€濮嬫竻鐞嗕复鏃舵枃浠?..")
                                    window.processor.clean_temp_files()
                                    if hasattr(window.processor, "stop_processing"):
                                        window.processor.stop_processing()
                                # 娓呯┖澶勭悊鍣ㄥ紩鐢?                                window.processor = None
                                logger.info("瑙嗛澶勭悊鍣ㄥ凡娓呯┖")
                            
                            # 2. 娓呯┖澶勭悊绾跨▼
                            if hasattr(window, "processing_thread") and window.processing_thread:
                                window.processing_thread = None
                                logger.info("澶勭悊绾跨▼宸叉竻绌?)
                            
                            # 3. 寮哄埗鎵ц涓€娆ython鍨冨溇鍥炴敹
                            import gc
                            # 鑾峰彇褰撳墠鏈洖鏀跺璞℃暟閲?                            before_count = gc.get_count()
                            logger.info(f"鎵ц鍨冨溇鍥炴敹鍓嶆湭鍥炴敹瀵硅薄璁℃暟: {before_count}")
                            
                            # 鎵ц瀹屾暣鐨勫瀮鍦惧洖鏀?                            gc.collect(0)  # 鏀堕泦绗?浠ｅ璞?                            gc.collect(1)  # 鏀堕泦绗?浠ｅ璞?                            gc.collect(2)  # 鏀堕泦绗?浠ｅ璞?                            
                            # 鑾峰彇鍥炴敹鍚庡璞℃暟閲?                            after_count = gc.get_count()
                            logger.info(f"鎵ц鍨冨溇鍥炴敹鍚庢湭鍥炴敹瀵硅薄璁℃暟: {after_count}")
                            
                            # 4. 灏濊瘯閲婃斁鍏朵粬鍙兘鐨勮祫婧?- 浣嗕繚鐣橴I鐣岄潰鍏冪礌
                            for attr_name in dir(window):
                                if attr_name.startswith("__") or attr_name.startswith("ui_"):
                                    continue  # 璺宠繃UI鐩稿叧鍏冪礌
                                
                                # 璺宠繃鎵€鏈塓Widget绫诲瀷鐨勫璞★紝浠ヤ繚鐣欑晫闈㈠厓绱?                                attr = getattr(window, attr_name, None)
                                # 璺宠繃鐣岄潰鐩稿叧鍏冪礌鍜屽熀鏈睘鎬?                                if (attr is None or 
                                    isinstance(attr, (QWidget, QLayout, QAction, QObject)) or
                                    attr_name in ['tab_widget', 'menuBar', 'statusBar', 'centralWidget']):
                                    continue
                                
                                # 鍙叧闂槑纭煡閬撳彲浠ュ叧闂殑璧勬簮绫诲瀷
                                if hasattr(attr, "close") and callable(getattr(attr, "close")):
                                    try:
                                        getattr(attr, "close")()
                                        logger.debug(f"宸插叧闂祫婧? {attr_name}")
                                    except Exception as e:
                                        logger.debug(f"鍏抽棴璧勬簮 {attr_name} 鏃跺嚭閿? {str(e)}")
                            
                            # 5. 寮哄埗鎵ц涓€娆t浜嬩欢澶勭悊
                            QApplication.processEvents()
                            
                            logger.info("璧勬簮娓呯悊瀹屾垚锛岀郴缁熷唴瀛樺凡閲婃斁")
                        except Exception as e:
                            logger.error(f"娓呯悊璧勬簮鏃跺嚭閿? {str(e)}")
                            error_detail = traceback.format_exc()
                            logger.error(f"璇︾粏閿欒淇℃伅: {error_detail}")
                        
                        # 浣跨敤鐭椂闂村欢杩熻皟鐢ㄤ笅涓€涓换鍔★紝纭繚UI鏈夋椂闂存洿鏂?                        QTimer.singleShot(1000, self._process_next_task)  # 寤堕暱绛夊緟鏃堕棿鍒?绉掞紝缁欑郴缁熸洿澶氭椂闂撮噴鏀捐祫婧?                    else:
                        # 濡傛灉绾跨▼浠嶅湪杩愯锛屽啀娆℃鏌?                        # 涓轰簡閬垮厤鍗′綇锛屾垜浠篃妫€鏌ヤ竴涓嬫槸鍚︾嚎绋嬬‘瀹炲湪宸ヤ綔
                        if hasattr(window, "last_progress_update"):
                            current_time = time.time()
                            time_since_update = current_time - window.last_progress_update
                            logger.debug(f"  - 涓婃杩涘害鏇存柊: {time_since_update:.1f}绉掑墠")
                            
                            # 澧炲姞瓒呮椂鏃堕棿鍒?0绉掞紝瑙嗛澶勭悊鍙兘闇€瑕佹洿闀挎椂闂?                            if time_since_update > 30:  # 濡傛灉30绉掓病鏈夎繘搴︽洿鏂?                                logger.warning(f"浠诲姟 {tab['name']} 浼间箮宸插崱浣?(>30绉掓棤杩涘害鏇存柊)锛屽皾璇曞己鍒舵洿鏂拌繘搴?)
                                
                                # 鑾峰彇姝ゆ爣绛鹃〉鐨勫己鍒舵洿鏂板皾璇曟鏁?                                force_update_retries = tab.get("force_update_retries", 0)
                                
                                # 灏濊瘯浣跨敤寮哄埗鏇存柊鏂规硶
                                if force_update_retries < 3 and hasattr(window, "force_progress_update"):
                                    logger.info(f"灏濊瘯寮哄埗鏇存柊杩涘害鐘舵€侊紝绗瑊force_update_retries + 1}娆″皾璇?)
                                    force_update_success = window.force_progress_update()
                                    
                                    # 涓嶇缁撴灉濡備綍锛岄兘澧炲姞灏濊瘯娆℃暟
                                    tab["force_update_retries"] = force_update_retries + 1
                                    
                                    if force_update_success:
                                        logger.info(f"寮哄埗鏇存柊杩涘害鎴愬姛锛岀户缁瓑寰呭鐞?)
                                        # 鏇存柊涓婃杩涘害鏃堕棿浠ラ伩鍏嶇珛鍗冲啀娆¤Е鍙?                                        window.last_progress_update = time.time()
                                        QTimer.singleShot(5000, check_completion)  # 5绉掑悗鍐嶆妫€鏌?                                        return
                                    else:
                                        logger.warning(f"寮哄埗鏇存柊杩涘害澶辫触锛屽皾璇曞惎鐢ㄤ紶缁熸仮澶嶆柟寮?)
                                
                                # 濡傛灉寮哄埗鏇存柊澶辫触鎴栧皾璇曟鏁板凡鐢ㄥ畬锛屽皾璇曚紶缁熸仮澶嶆柟娉?                                if force_update_retries >= 3:
                                    logger.warning(f"浠诲姟 {tab['name']} 宸插皾璇曞己鍒舵洿鏂?{force_update_retries} 娆★紝浠嶆棤鍝嶅簲锛屽垽瀹氫负瓒呮椂")
                                
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
                                    
                                    # 鍋滄褰撳墠浠诲姟锛岀户缁笅涓€涓?                                    tab["status"] = "澶辫触(澶勭悊閿欒)"
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
            
            # 閲嶇疆寮哄埗鏇存柊閲嶈瘯璁℃暟
            tab["force_update_retries"] = 0
            
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
    
    def _update_task_status(self, tab_idx, status):
        """鏇存柊浠诲姟鐘舵€侊紙鐢卞伐浣滅嚎绋嬭皟鐢紝淇濊瘉鍦║I绾跨▼鎵ц锛?""
        try:
            if 0 <= tab_idx < len(self.tabs):
                old_status = self.tabs[tab_idx].get("status", "")
                self.tabs[tab_idx]["status"] = status
                
                # 濡傛灉鏄畬鎴愮姸鎬侊紝鏇存柊鏈€鍚庡鐞嗘椂闂?                if status in ["瀹屾垚", "澶辫触"]:
                    import datetime
                    self.tabs[tab_idx]["last_process_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # 澶勭悊瀹屾垚鍚庤嚜鍔ㄤ繚瀛樻ā鏉跨姸鎬?                    self._save_template_state()
                
                self._update_tasks_table()
                logger.info(f"浠诲姟 '{self.tabs[tab_idx]['name']}' 鐘舵€佹洿鏂颁负: {status} (涔嬪墠: {old_status})")
                
                # 濡傛灉鏄湪鎵瑰鐞嗚繃绋嬩腑锛屽苟涓旂姸鎬佸彉涓?澶辫触"锛岄渶瑕佸鐞嗛槦鍒?                if self.is_processing and status == "澶辫触" and self.current_processing_tab == tab_idx:
                    logger.info(f"浠诲姟 '{self.tabs[tab_idx]['name']}' 澶辫触锛屽噯澶囧鐞嗕笅涓€涓换鍔?)
                    self.current_processing_tab = None
                    # 浣跨敤鐭欢杩熷啀澶勭悊涓嬩竴涓换鍔★紝浠ョ‘淇漊I鏈夋椂闂存洿鏂?                    QTimer.singleShot(500, self._process_next_task)
            else:
                logger.warning(f"鏃犳晥鐨勬爣绛剧储寮? {tab_idx}")
        except Exception as e:
            logger.error(f"鏇存柊浠诲姟鐘舵€佹椂鍑洪敊: {str(e)}")
            logger.error(traceback.format_exc())
    
    def _setup_dialog_filter(self):
        """璁剧疆鍏ㄥ眬瀵硅瘽妗嗚繃婊ゅ櫒锛岀敤浜庡湪鎵瑰鐞嗘ā寮忎笅鎶戝埗瀵硅瘽妗?""
        # 淇濆瓨鍘熷鐨凲MessageBox鏂规硶
        self._original_info = QMessageBox.information
        self._original_warning = QMessageBox.warning
        self._original_critical = QMessageBox.critical
        self._original_question = QMessageBox.question
        
        # 瀹氫箟鍦ㄦ壒澶勭悊妯″紡涓嬩娇鐢ㄧ殑鏇夸唬鏂规硶
        def _filtered_info(parent, title, text, *args, **kwargs):
            # 濡傛灉姝ｅ湪鎵瑰鐞嗕笖涓嶆槸鏉ヨ嚜BatchWindow鐨勬秷鎭紝鍒欏拷鐣?            if self.is_processing and parent is not self:
                logger.info(f"鎵瑰鐞嗘ā寮忔姂鍒朵俊鎭璇濇: {title} - {text}")
                # 閫氬父淇℃伅瀵硅瘽妗嗚繑鍥濹MessageBox.Ok
                return QMessageBox.Ok
            # 鍚﹀垯浣跨敤鍘熷鏂规硶
            return self._original_info(parent, title, text, *args, **kwargs)
        
        def _filtered_warning(parent, title, text, *args, **kwargs):
            # 濡傛灉姝ｅ湪鎵瑰鐞嗕笖涓嶆槸鏉ヨ嚜BatchWindow鐨勬秷鎭紝鍒欏拷鐣?            if self.is_processing and parent is not self:
                logger.warning(f"鎵瑰鐞嗘ā寮忔姂鍒惰鍛婂璇濇: {title} - {text}")
                # 閫氬父璀﹀憡瀵硅瘽妗嗚繑鍥濹MessageBox.Ok
                return QMessageBox.Ok
            # 鍚﹀垯浣跨敤鍘熷鏂规硶
            return self._original_warning(parent, title, text, *args, **kwargs)
        
        def _filtered_critical(parent, title, text, *args, **kwargs):
            # 濡傛灉姝ｅ湪鎵瑰鐞嗕笖涓嶆槸鏉ヨ嚜BatchWindow鐨勬秷鎭紝鍒欏拷鐣?            if self.is_processing and parent is not self:
                logger.error(f"鎵瑰鐞嗘ā寮忔姂鍒堕敊璇璇濇: {title} - {text}")
                # 閫氬父閿欒瀵硅瘽妗嗚繑鍥濹MessageBox.Ok
                return QMessageBox.Ok
            # 鍚﹀垯浣跨敤鍘熷鏂规硶
            return self._original_critical(parent, title, text, *args, **kwargs)
        
        def _filtered_question(parent, title, text, *args, **kwargs):
            # 濡傛灉姝ｅ湪鎵瑰鐞嗕笖涓嶆槸鏉ヨ嚜BatchWindow鐨勬秷鎭紝鍒欏拷鐣?            if self.is_processing and parent is not self:
                logger.info(f"鎵瑰鐞嗘ā寮忔姂鍒堕棶棰樺璇濇: {title} - {text}")
                # 瀵逛簬闂瀵硅瘽妗嗭紝閫氬父杩斿洖Yes浣滀负鑲畾鍥炵瓟
                return QMessageBox.Yes
            # 鍚﹀垯浣跨敤鍘熷鏂规硶
            return self._original_question(parent, title, text, *args, **kwargs)
        
        # 鏇挎崲鍏ㄥ眬鏂规硶
        QMessageBox.information = _filtered_info
        QMessageBox.warning = _filtered_warning
        QMessageBox.critical = _filtered_critical
        QMessageBox.question = _filtered_question
    
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
    
    def _save_template_state(self):
        """淇濆瓨褰撳墠妯℃澘鐘舵€?""
        try:
            # 鏀堕泦鍚勬爣绛鹃〉鐨勬枃浠惰矾寰勫拰鏂囦欢澶硅矾寰勪俊鎭?            for i, tab in enumerate(self.tabs):
                if "window" in tab and tab["window"]:
                    window = tab["window"]
                    
                    # 鑾峰彇褰撳墠閰嶇疆鏂囦欢璺緞
                    config_file = ""
                    if hasattr(window, "config_file") and window.config_file:
                        config_file = window.config_file
                    
                    # 鑾峰彇褰撳墠澶勭悊鏂囦欢澶硅矾寰?                    folder_path = ""
                    if hasattr(window, "input_folder_path"):
                        folder_path = window.input_folder_path.text().strip()
                    
                    # 鑾峰彇瀹炰緥ID
                    instance_id = tab.get("instance_id", "")
                    if not instance_id and hasattr(window, "user_settings") and hasattr(window.user_settings, "instance_id"):
                        instance_id = window.user_settings.instance_id
                    
                    # 鏇存柊鏍囩椤典俊鎭?                    tab["file_path"] = config_file
                    tab["folder_path"] = folder_path
                    tab["tab_index"] = i  # 鏇存柊鏍囩椤电储寮曪紝纭繚涓庡綋鍓嶆樉绀洪『搴忎竴鑷?                    
                    # 纭繚鏈夊疄渚婭D
                    if not tab.get("instance_id"):
                        tab["instance_id"] = instance_id or f"tab_saved_{i}_{time.time()}"
                    
                    logger.debug(f"淇濆瓨妯℃澘鐘舵€? {tab['name']}, 绱㈠紩: {i}, 鏂囦欢澶? {folder_path}, 瀹炰緥ID: {tab.get('instance_id', '')}")
            
            # 淇濆瓨鍒伴厤缃枃浠?            self.template_state.save_template_tabs(self.tabs)
            logger.info(f"宸蹭繚瀛?{len(self.tabs)} 涓ā鏉跨姸鎬?)
        except Exception as e:
            logger.error(f"淇濆瓨妯℃澘鐘舵€佹椂鍑洪敊: {str(e)}")
    
    def _open_template_selector(self):
        """鎵撳紑妯℃澘閫夋嫨鍣ㄥぇ绐楀彛"""
        try:
            # 鍒涘缓妯℃澘閫夋嫨鍣ㄥ璇濇
            selector = TemplateSelector(self.tabs, parent=self)
            
            # 鏄剧ず瀵硅瘽妗?            if selector.exec_() == QDialog.Accepted:
                # 鑾峰彇鐢ㄦ埛閫夋嫨鐨勬ā鏉?                selected_templates = selector.get_selected_templates()
                
                # 鏄剧ず閫夋嫨缁撴灉
                if selected_templates:
                    self.statusBar.showMessage(f"宸查€夋嫨 {len(selected_templates)} 涓ā鏉胯繘琛屾壒澶勭悊", 3000)
                else:
                    self.statusBar.showMessage("鏈€夋嫨浠讳綍妯℃澘", 3000)
        except Exception as e:
            logger.error(f"鎵撳紑妯℃澘閫夋嫨鍣ㄦ椂鍑洪敊: {str(e)}")
            QMessageBox.warning(self, "閿欒", f"鎵撳紑妯℃澘閫夋嫨鍣ㄦ椂鍑洪敊: {str(e)}")

    def _refresh_tabs_after_resource_release(self):
        """鍦ㄨ祫婧愰噴鏀惧悗鍒锋柊鎵€鏈夋爣绛鹃〉鐨刄I鏄剧ず锛岀‘淇漊I淇濇寔鍙"""
        try:
            logger.info("鍦ㄨ祫婧愰噴鏀惧悗鍒锋柊鎵€鏈夋爣绛鹃〉UI...")
            
            # 棣栧厛纭繚鎵瑰鐞嗙獥鍙ｈ嚜韬樉绀烘甯?            self.update()
            QApplication.processEvents()
            
            # 鏇存柊浠诲姟琛ㄦ牸
            self._update_tasks_table()
            
            # 鍒锋柊鏍囩鎺т欢
            self.tab_widget.update()
            
            # 閬嶅巻鎵€鏈夋爣绛鹃〉
            for i in range(self.tab_widget.count()):
                try:
                    # 鑾峰彇鏍囩椤靛拰瀵瑰簲鐨勭獥鍙?                    tab_widget = self.tab_widget.widget(i)
                    if not tab_widget:
                        continue
                    
                    # 鍒囨崲鍒拌鏍囩椤?                    self.tab_widget.setCurrentIndex(i)
                    QApplication.processEvents()
                    
                    # 纭繚鏍囩椤靛彲瑙?                    tab_widget.show()
                    tab_widget.update()
                    
                    # 鍒锋柊鏍囩椤典腑鐨勭獥鍙?                    if i < len(self.tabs):
                        tab = self.tabs[i]
                        if "window" in tab and tab["window"]:
                            window = tab["window"]
                            
                            # 鍒锋柊涓荤獥鍙?                            if hasattr(window, "update"):
                                window.update()
                                
                            # 鍒锋柊鍏抽敭UI缁勪欢
                            for widget_name in ["stackedWidget", "panel_material", "panel_setting", 
                                               "save_dir_display", "material_table", "btn_start"]:
                                if hasattr(window, widget_name):
                                    widget = getattr(window, widget_name)
                                    if widget and hasattr(widget, "show"):
                                        widget.show()
                                        if hasattr(widget, "update"):
                                            widget.update()
                
                    # 鍒锋柊鎵€鏈夊瓙缁勪欢
                    for child in tab_widget.findChildren(QWidget):
                        if child and not child.isHidden():
                            try:
                                child.show()
                                child.update()
                            except Exception as e:
                                logger.debug(f"鍒锋柊瀛愮粍浠舵椂鍑洪敊: {str(e)}")
                    
                    # 澶勭悊浜嬩欢寰幆
                    QApplication.processEvents()
                except Exception as e:
                    logger.error(f"鍒锋柊鏍囩椤?{i} 鏃跺嚭閿? {str(e)}")
                
            # 鏈€鍚庣‘淇濇暣浣揢I鍒锋柊
            self.update()
            QApplication.processEvents()
            
            logger.info("鏍囩椤礥I鍒锋柊瀹屾垚")
        except Exception as e:
            logger.error(f"鍒锋柊鏍囩椤礥I鏃跺嚭閿? {str(e)}")

# 鏂板妯℃澘閫夋嫨鍣ㄥ璇濇绫?class TemplateSelector(QDialog):
    """妯℃澘閫夋嫨鍣ㄥ璇濇锛屾彁渚涗竴涓洿澶х殑绐楀彛鏉ラ€夋嫨瑕佹壒澶勭悊鐨勬ā鏉?""
    
    def __init__(self, templates, parent=None):
        super().__init__(parent)
        self.templates = templates
        # 鑾峰彇宸茬粡鍦ㄨ〃鏍间腑閫変腑鐨勬ā鏉垮悕绉?        self.batch_window = parent
        self.selected_templates = []
        # 浠庤〃鏍间腑鑾峰彇褰撳墠閫変腑鐨勬ā鏉?        if hasattr(self.batch_window, 'tasks_table'):
            for row in range(self.batch_window.tasks_table.rowCount()):
                checkbox_container = self.batch_window.tasks_table.cellWidget(row, 0)
                if checkbox_container:
                    checkbox = checkbox_container.findChild(QCheckBox)
                    if checkbox and checkbox.isChecked() and row < len(templates):
                        self.selected_templates.append(templates[row].get("name", f"妯℃澘{row+1}"))
        self._init_ui()
    
    def _init_ui(self):
        """鍒濆鍖朥I"""
        # 璁剧疆绐楀彛灞炴€?        self.setWindowTitle("妯℃澘閫夋嫨鍣?)
        self.resize(900, 700)
        
        # 涓诲竷灞€
        layout = QVBoxLayout(self)
        
        # 璇存槑鏍囩
        label = QLabel("璇烽€夋嫨瑕佹壒閲忓鐞嗙殑妯℃澘:")
        layout.addWidget(label)
        
        # 鍒涘缓琛ㄦ牸
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["閫夋嫨", "妯℃澘鍚嶇О", "淇濆瓨鐩綍", "鐘舵€?, "鏈€鍚庡鐞嗘椂闂?])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # 濉厖琛ㄦ牸
        self._fill_table()
        
        layout.addWidget(self.table)
        
        # 蹇嵎鎿嶄綔鎸夐挳
        button_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("鍏ㄩ€?)
        select_all_btn.clicked.connect(self._select_all)
        button_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("鍙栨秷鍏ㄩ€?)
        deselect_all_btn.clicked.connect(self._deselect_all)
        button_layout.addWidget(deselect_all_btn)
        
        invert_selection_btn = QPushButton("鍙嶉€?)
        invert_selection_btn.clicked.connect(self._invert_selection)
        button_layout.addWidget(invert_selection_btn)
        
        layout.addLayout(button_layout)
        
        # 纭畾鍜屽彇娑堟寜閽?        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _fill_table(self):
        """濉厖琛ㄦ牸鏁版嵁"""
        self.table.setRowCount(len(self.templates))
        
        for row, tab in enumerate(self.templates):
            # 鍒涘缓澶嶉€夋
            checkbox = QCheckBox()
            # 妫€鏌ユā鏉垮悕绉版槸鍚﹀湪宸查€夊垪琛ㄤ腑
            template_name = tab.get("name", f"妯℃澘{row+1}")
            checkbox.setChecked(template_name in self.selected_templates)
            
            # 鍒涘缓澶嶉€夋鍗曞厓鏍煎眳涓殑瀹瑰櫒
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            
            # 璁剧疆绗竴鍒椾负澶嶉€夋
            self.table.setCellWidget(row, 0, checkbox_widget)
            
            # 璁剧疆鍏朵粬鍒?            self.table.setItem(row, 1, QTableWidgetItem(template_name))
            self.table.setItem(row, 2, QTableWidgetItem(tab.get("output_dir", "-")))
            
            # 鐘舵€佸垪
            status_item = QTableWidgetItem(tab.get("status", "寰呭鐞?))
            
            # 鏍规嵁鐘舵€佽缃鑹?            if tab.get("status") == "瀹屾垚":
                status_item.setBackground(QColor("#C8E6C9"))  # 娣＄豢鑹?            elif tab.get("status") == "澶辫触":
                status_item.setBackground(QColor("#FFCDD2"))  # 娣＄孩鑹?            elif tab.get("status") == "澶勭悊涓?:
                status_item.setBackground(QColor("#FFF9C4"))  # 娣￠粍鑹?            
            self.table.setItem(row, 3, status_item)
            
            # 鏈€鍚庡鐞嗘椂闂?            self.table.setItem(row, 4, QTableWidgetItem(tab.get("last_process_time", "-")))
        
        # 鑷姩璋冩暣琛岄珮
        self.table.resizeRowsToContents()
        logger.debug(f"妯℃澘閫夋嫨鍣ㄥ垵濮嬮€変腑鐨勬ā鏉? {self.selected_templates}")
    
    def _select_all(self):
        """鍏ㄩ€夋墍鏈夋ā鏉?""
        for row in range(self.table.rowCount()):
            self._set_checkbox(row, True)
    
    def _deselect_all(self):
        """鍙栨秷鍏ㄩ€?""
        for row in range(self.table.rowCount()):
            self._set_checkbox(row, False)
    
    def _invert_selection(self):
        """鍙嶅悜閫夋嫨"""
        for row in range(self.table.rowCount()):
            current_state = self._get_checkbox(row).isChecked()
            self._set_checkbox(row, not current_state)
    
    def _get_checkbox(self, row):
        """鑾峰彇鎸囧畾琛岀殑澶嶉€夋"""
        checkbox_widget = self.table.cellWidget(row, 0)
        if checkbox_widget:
            # 鎵惧埌QCheckBox瀛愰儴浠?            return checkbox_widget.findChild(QCheckBox)
        return None
    
    def _set_checkbox(self, row, checked):
        """璁剧疆鎸囧畾琛岀殑澶嶉€夋鐘舵€?""
        checkbox = self._get_checkbox(row)
        if checkbox:
            checkbox.setChecked(checked)
    
    def get_selected_templates(self):
        """鑾峰彇宸查€夋嫨鐨勬ā鏉垮悕绉板垪琛?""
        selected_templates = []
        for row in range(self.table.rowCount()):
            checkbox = self._get_checkbox(row)
            if checkbox and checkbox.isChecked():
                template_name = self.table.item(row, 1).text()
                selected_templates.append(template_name)
        return selected_templates
    
    def accept(self):
        """纭畾鎸夐挳琚偣鍑?""
        # 鏇存柊閫変腑鐨勬ā鏉?        self.selected_templates = self.get_selected_templates()
        logger.info(f"妯℃澘閫夋嫨鍣ㄧ‘璁ら€夋嫨浜?{len(self.selected_templates)} 涓ā鏉?)
        
        # 鏇存柊鎵瑰鐞嗙獥鍙ｄ腑鐨勫閫夋鐘舵€佷笌妯℃澘閫夋嫨鍣ㄤ繚鎸佷竴鑷?        if hasattr(self.batch_window, 'tasks_table') and self.batch_window.tasks_table:
            for row in range(self.batch_window.tasks_table.rowCount()):
                if row < len(self.templates):
                    checkbox_container = self.batch_window.tasks_table.cellWidget(row, 0)
                    if checkbox_container:
                        checkbox = checkbox_container.findChild(QCheckBox)
                        if checkbox:
                            template_name = self.templates[row].get("name", f"妯℃澘{row+1}")
                            checkbox.setChecked(template_name in self.selected_templates)
                            logger.debug(f"鏇存柊鎵瑰鐞嗙獥鍙ｅ閫夋鐘舵€? 妯℃澘 {template_name} - {'閫変腑' if template_name in self.selected_templates else '鏈€変腑'}")
            
            # 鏇存柊闃熷垪鏄剧ず淇℃伅
            self.batch_window._update_queue_display()
        
        super().accept()
