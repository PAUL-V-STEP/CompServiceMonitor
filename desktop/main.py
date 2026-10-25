"""
Desktop-приложение: анализ услуг ТО компьютерной техники.
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QLineEdit, QFrame, QScrollArea,
    QFileDialog, QStackedWidget, QSplitter, QMessageBox, QProgressBar, QComboBox,
    QTreeWidget, QTreeWidgetItem,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QFont, QIcon, QDragEnterEvent, QDropEvent, QColor, QBrush

from styles import DARK_THEME
from api_client import api_client


def setup_desktop_logging() -> logging.Logger:
    logs_dir = Path(__file__).resolve().parent.parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("compservice.desktop")
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        return logger
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-32s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        logs_dir / "desktop.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(file_handler)
    logger.addHandler(console)
    logger.propagate = False
    logger.info("Desktop-логирование: %s", logs_dir / "desktop.log")
    return logger


logger = setup_desktop_logging()


class WorkerThread(QThread):
    """Поток для выполнения API запросов"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class DropZone(QFrame):
    """Зона для drag & drop изображений"""
    fileDropped = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.setObjectName("uploadZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(200)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.icon_label = QLabel("📁")
        self.icon_label.setStyleSheet("font-size: 48px;")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.text_label = QLabel("Перетащите изображение или нажмите для выбора")
        self.text_label.setStyleSheet("color: #94a3b8; font-size: 14px;")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.hint_label = QLabel("PNG, JPG, GIF, WEBP до 10MB")
        self.hint_label.setStyleSheet("color: #64748b; font-size: 12px;")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.hide()
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        layout.addWidget(self.hint_label)
        layout.addWidget(self.preview_label)
        
        self.selected_file = None
    
    def mousePressEvent(self, event):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите изображение",
            "",
            "Изображения (*.png *.jpg *.jpeg *.gif *.webp)"
        )
        if file_path:
            self.set_file(file_path)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("QFrame#uploadZone { border-color: #06b6d4; background-color: rgba(6, 182, 212, 0.1); }")
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet("")
    
    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("")
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                self.set_file(file_path)
    
    def set_file(self, file_path: str):
        self.selected_file = file_path
        
        # Показываем превью
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(300, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.preview_label.setPixmap(pixmap)
            self.preview_label.show()
            self.icon_label.hide()
            self.text_label.setText(Path(file_path).name)
            self.hint_label.setText("Нажмите для замены")
        
        self.fileDropped.emit(file_path)
    
    def clear(self):
        self.selected_file = None
        self.preview_label.hide()
        self.icon_label.show()
        self.text_label.setText("Перетащите изображение или нажмите для выбора")
        self.hint_label.setText("PNG, JPG, GIF, WEBP до 10MB")


class ResultBlock(QFrame):
    """Блок результата анализа"""
    def __init__(self, title: str, items: list, icon: str = "→"):
        super().__init__()
        self.setObjectName("resultBlock")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)
        
        for item in items:
            item_label = QLabel(f"{icon} {item}")
            item_label.setWordWrap(True)
            item_label.setStyleSheet("color: #94a3b8; margin-left: 8px; line-height: 1.5;")
            layout.addWidget(item_label)


class MainWindow(QMainWindow):
    """Главное окно приложения"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Анализ услуг ТО компьютерной техники")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        # Применяем стили
        self.setStyleSheet(DARK_THEME)
        
        # Главный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Главный layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar
        self.setup_sidebar(main_layout)
        
        # Content area
        self.setup_content(main_layout)
        
        # Текущий worker
        self.current_worker = None
        
        # Проверяем подключение к серверу
        self.check_server_connection()
    
    def setup_sidebar(self, parent_layout):
        """Создание боковой панели"""
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(280)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Logo
        logo = QLabel("🖥 CompService")
        logo.setObjectName("logo")
        layout.addWidget(logo)
        
        # Navigation
        nav_widget = QWidget()
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(12, 16, 12, 16)
        nav_layout.setSpacing(4)
        
        self.nav_buttons = []
        nav_items = [
            ("📝 Анализ текста", 0),
            ("🖼️ Анализ изображений", 1),
            ("🌐 Парсинг сайта", 2),
            ("🔗 Сайты", 3),
            ("📋 История", 4)
        ]
        
        for text, index in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=index: self.switch_tab(idx))
            nav_layout.addWidget(btn)
            self.nav_buttons.append(btn)
        
        self.nav_buttons[0].setChecked(True)
        
        nav_layout.addStretch()
        
        # Status
        self.status_label = QLabel("● Проверка подключения...")
        self.status_label.setStyleSheet("color: #f59e0b; padding: 16px;")
        nav_layout.addWidget(self.status_label)
        
        layout.addWidget(nav_widget)
        parent_layout.addWidget(sidebar)
    
    def setup_content(self, parent_layout):
        """Создание области контента"""
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(40, 32, 40, 32)
        
        # Header
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 24)
        
        title = QLabel("Анализ услуг ТО техники")
        title.setObjectName("title")
        
        subtitle = QLabel("Разбор прайсов, визуалов и сайтов сервисных центров")
        subtitle.setObjectName("subtitle")
        
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        content_layout.addWidget(header)
        
        # Stacked widget для вкладок
        self.stacked_widget = QStackedWidget()
        
        # Добавляем вкладки
        self.stacked_widget.addWidget(self.create_text_tab())
        self.stacked_widget.addWidget(self.create_image_tab())
        self.stacked_widget.addWidget(self.create_parse_tab())
        self.stacked_widget.addWidget(self.create_sites_tab())
        self.stacked_widget.addWidget(self.create_history_tab())
        
        content_layout.addWidget(self.stacked_widget)
        
        # Results area
        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.hide()
        
        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_scroll.setWidget(self.results_widget)
        
        content_layout.addWidget(self.results_scroll)
        
        # Loading indicator
        self.loading_widget = QWidget()
        loading_layout = QVBoxLayout(self.loading_widget)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setFixedWidth(300)
        
        self.loading_label = QLabel("Анализирую данные...")
        self.loading_label.setStyleSheet("color: #94a3b8; font-size: 16px;")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        loading_layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self.loading_label)
        
        self.loading_widget.hide()
        content_layout.addWidget(self.loading_widget)
        
        parent_layout.addWidget(content_widget)
    
    def create_text_tab(self) -> QWidget:
        """Вкладка анализа текста"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Card
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        
        title = QLabel("Анализ описания услуг ТО")
        title.setObjectName("cardTitle")
        
        desc = QLabel("Вставьте прайс, коммерческое предложение, договор или текст лендинга сервиса")
        desc.setObjectName("cardDescription")
        
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Вставьте описание услуг техобслуживания...\n\nНапример: диагностика ПК от 500 ₽, выезд мастера 24 часа, абонентское ТО офиса, гарантия 90 дней...")
        self.text_input.setMinimumHeight(200)
        
        self.analyze_text_btn = QPushButton("⚡ Проанализировать")
        self.analyze_text_btn.setObjectName("primaryButton")
        self.analyze_text_btn.clicked.connect(self.analyze_text)
        
        card_layout.addWidget(title)
        card_layout.addWidget(desc)
        card_layout.addSpacing(16)
        card_layout.addWidget(self.text_input)
        card_layout.addSpacing(16)
        card_layout.addWidget(self.analyze_text_btn)
        
        layout.addWidget(card)
        layout.addStretch()
        
        return widget
    
    def create_image_tab(self) -> QWidget:
        """Вкладка анализа изображений"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Card
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        
        title = QLabel("Анализ изображений")
        title.setObjectName("cardTitle")
        
        desc = QLabel("Загрузите прайс, баннер сервиса, фото мастерской или скриншот страницы услуг")
        desc.setObjectName("cardDescription")
        
        self.drop_zone = DropZone()
        
        self.analyze_image_btn = QPushButton("⚡ Проанализировать")
        self.analyze_image_btn.setObjectName("primaryButton")
        self.analyze_image_btn.clicked.connect(self.analyze_image)
        
        card_layout.addWidget(title)
        card_layout.addWidget(desc)
        card_layout.addSpacing(16)
        card_layout.addWidget(self.drop_zone)
        card_layout.addSpacing(16)
        card_layout.addWidget(self.analyze_image_btn)
        
        layout.addWidget(card)
        layout.addStretch()
        
        return widget
    
    def create_parse_tab(self) -> QWidget:
        """Вкладка парсинга сайта"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Card
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        
        title = QLabel("Парсинг сайта сервисного центра")
        title.setObjectName("cardTitle")
        
        desc = QLabel("Разбирается только указанная страница. Найденные внутренние ссылки попадают в дерево для ручного выбора")
        desc.setObjectName("cardDescription")
        
        # URL input
        url_layout = QHBoxLayout()
        
        prefix = QLabel("https://")
        prefix.setStyleSheet("background-color: #243049; padding: 12px 16px; border-radius: 8px 0 0 8px; color: #64748b;")
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("service-center.ru/to")
        self.url_input.setStyleSheet("border-radius: 0 8px 8px 0;")
        
        url_layout.addWidget(prefix)
        url_layout.addWidget(self.url_input)

        saved_label = QLabel("Сохранённые сайты")
        saved_label.setObjectName("cardDescription")
        self.saved_sites_combo = QComboBox()
        self.saved_sites_combo.setEditable(False)
        self.saved_sites_combo.currentIndexChanged.connect(self.on_saved_site_chosen)
        
        self.parse_btn = QPushButton("⚡ Парсить и анализировать")
        self.parse_btn.setObjectName("primaryButton")
        self.parse_btn.clicked.connect(self.parse_site)
        
        card_layout.addWidget(title)
        card_layout.addWidget(desc)
        card_layout.addSpacing(16)
        card_layout.addWidget(saved_label)
        card_layout.addWidget(self.saved_sites_combo)
        card_layout.addSpacing(12)
        card_layout.addLayout(url_layout)
        card_layout.addSpacing(16)
        card_layout.addWidget(self.parse_btn)
        self.refresh_saved_sites_combo()
        
        layout.addWidget(card)
        layout.addStretch()
        
        return widget
    
    def create_history_tab(self) -> QWidget:
        """Вкладка истории"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Header with clear button
        header = QHBoxLayout()
        
        title = QLabel("История запросов")
        title.setObjectName("cardTitle")
        
        self.clear_history_btn = QPushButton("🗑️ Очистить")
        self.clear_history_btn.setObjectName("secondaryButton")
        self.clear_history_btn.clicked.connect(self.clear_history)
        
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.clear_history_btn)
        
        layout.addLayout(header)
        
        # History scroll area
        self.history_scroll = QScrollArea()
        self.history_scroll.setWidgetResizable(True)
        
        self.history_widget = QWidget()
        self.history_layout = QVBoxLayout(self.history_widget)
        self.history_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.history_scroll.setWidget(self.history_widget)
        layout.addWidget(self.history_scroll)
        
        return widget

    def create_sites_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        header = QHBoxLayout()
        title = QLabel("Дерево ссылок")
        title.setObjectName("cardTitle")
        self.parse_selected_btn = QPushButton("Парсить выбранные")
        self.parse_selected_btn.setObjectName("primaryButton")
        self.parse_selected_btn.clicked.connect(self.parse_checked_sites)
        self.clear_sites_btn = QPushButton("Очистить")
        self.clear_sites_btn.setObjectName("secondaryButton")
        self.clear_sites_btn.clicked.connect(self.clear_saved_sites)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.parse_selected_btn)
        header.addWidget(self.clear_sites_btn)
        layout.addLayout(header)

        hint = QLabel("Иерархия ссылок с разобранных страниц. Зелёные уже проанализированы. Отметьте и разберите вручную.")
        hint.setObjectName("cardDescription")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.sites_tree = QTreeWidget()
        self.sites_tree.setHeaderLabels(["Выбор", "Статус", "Страница", "URL"])
        self.sites_tree.setColumnWidth(0, 70)
        self.sites_tree.setColumnWidth(1, 130)
        self.sites_tree.setColumnWidth(2, 260)
        layout.addWidget(self.sites_tree)
        return widget
    
    def switch_tab(self, index: int):
        """Переключение вкладок"""
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        
        self.stacked_widget.setCurrentIndex(index)
        self.results_scroll.hide()
        
        # Загружаем историю при переключении на вкладку
        if index == 2:
            self.refresh_saved_sites_combo()
        if index == 3:
            self.load_saved_sites()
        if index == 4:
            self.load_history()
    
    def check_server_connection(self):
        """Проверка подключения к серверу"""
        if api_client.check_health():
            self.status_label.setText("● Система активна")
            self.status_label.setStyleSheet("color: #10b981; padding: 16px;")
        else:
            self.status_label.setText("● Сервер недоступен")
            self.status_label.setStyleSheet("color: #ef4444; padding: 16px;")
    
    def show_loading(self, message: str = "Анализирую данные..."):
        """Показать индикатор загрузки"""
        self.loading_label.setText(message)
        self.loading_widget.show()
        self.results_scroll.hide()
        
        # Отключаем кнопки
        self.analyze_text_btn.setEnabled(False)
        self.analyze_image_btn.setEnabled(False)
        self.parse_btn.setEnabled(False)
    
    def hide_loading(self):
        """Скрыть индикатор загрузки"""
        self.loading_widget.hide()
        
        # Включаем кнопки
        self.analyze_text_btn.setEnabled(True)
        self.analyze_image_btn.setEnabled(True)
        self.parse_btn.setEnabled(True)
    
    def show_results(self, analysis: dict, result_type: str = "text"):
        """Отображение результатов анализа"""
        # Очищаем предыдущие результаты
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Заголовок
        title = QLabel("📊 Результаты анализа")
        title.setObjectName("cardTitle")
        title.setStyleSheet("font-size: 18px; margin-bottom: 16px;")
        self.results_layout.addWidget(title)
        
        if result_type == "text" or result_type == "parse":
            if "overall_score" in analysis:
                score_frame = QFrame()
                score_frame.setObjectName("resultBlock")
                score_layout = QVBoxLayout(score_frame)
                score_title = QLabel("Оценка пакета услуг ТО")
                score_title.setObjectName("sectionTitle")
                score_value = QLabel(f"{analysis.get('overall_score', 0)}/10")
                score_value.setStyleSheet("font-size: 32px; font-weight: bold; color: #22d3ee;")
                score_layout.addWidget(score_title)
                score_layout.addWidget(score_value)
                self.results_layout.addWidget(score_frame)

            field_blocks = [
                ("Виды услуг", analysis.get("service_types")),
                ("Покрытие техники", analysis.get("equipment_coverage")),
                ("SLA и процесс", analysis.get("sla_and_process")),
                ("Цены и условия", analysis.get("pricing_notes")),
                ("Сильные стороны", analysis.get("strengths")),
                ("Пробелы и риски", analysis.get("gaps") or analysis.get("weaknesses")),
                ("Рекомендации", analysis.get("recommendations")),
            ]
            for title_text, items in field_blocks:
                if items:
                    self.results_layout.addWidget(ResultBlock(title_text, items))
            
            if analysis.get("summary"):
                summary_frame = QFrame()
                summary_frame.setObjectName("resultBlock")
                summary_frame.setStyleSheet("QFrame#resultBlock { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(6, 182, 212, 0.1), stop:1 rgba(139, 92, 246, 0.1)); }")
                summary_layout = QVBoxLayout(summary_frame)
                
                summary_title = QLabel("📝 Резюме")
                summary_title.setObjectName("sectionTitle")
                
                summary_text = QLabel(analysis["summary"])
                summary_text.setWordWrap(True)
                summary_text.setStyleSheet("color: #f1f5f9; font-size: 15px; line-height: 1.6;")
                
                summary_layout.addWidget(summary_title)
                summary_layout.addWidget(summary_text)
                self.results_layout.addWidget(summary_frame)
        
        elif result_type == "image":
            # Описание
            if analysis.get("description"):
                desc_frame = QFrame()
                desc_frame.setObjectName("resultBlock")
                desc_layout = QVBoxLayout(desc_frame)
                
                desc_title = QLabel("🖼️ Описание изображения")
                desc_title.setObjectName("sectionTitle")
                
                desc_text = QLabel(analysis["description"])
                desc_text.setWordWrap(True)
                desc_text.setStyleSheet("color: #94a3b8;")
                
                desc_layout.addWidget(desc_title)
                desc_layout.addWidget(desc_text)
                self.results_layout.addWidget(desc_frame)
            
            score = analysis.get("visual_quality_score", analysis.get("visual_style_score"))
            if score is not None:
                score_frame = QFrame()
                score_frame.setObjectName("resultBlock")
                score_layout = QVBoxLayout(score_frame)
                
                score_title = QLabel("Информативность визуала услуг")
                score_title.setObjectName("sectionTitle")
                
                score_value = QLabel(f"{score}/10")
                score_value.setStyleSheet("font-size: 32px; font-weight: bold; color: #22d3ee;")
                score_layout.addWidget(score_title)
                score_layout.addWidget(score_value)

                quality_text = analysis.get("visual_quality_analysis") or analysis.get("visual_style_analysis")
                if quality_text:
                    score_desc = QLabel(quality_text)
                    score_desc.setWordWrap(True)
                    score_desc.setStyleSheet("color: #94a3b8;")
                    score_layout.addWidget(score_desc)
                if analysis.get("communication_quality"):
                    comm = QLabel(analysis["communication_quality"])
                    comm.setWordWrap(True)
                    comm.setStyleSheet("color: #94a3b8;")
                    score_layout.addWidget(comm)
                self.results_layout.addWidget(score_frame)
            
            if analysis.get("detected_services"):
                self.results_layout.addWidget(ResultBlock("Услуги на изображении", analysis["detected_services"]))
            if analysis.get("equipment_shown"):
                self.results_layout.addWidget(ResultBlock("Техника / рабочее место", analysis["equipment_shown"]))
            if analysis.get("recommendations"):
                self.results_layout.addWidget(ResultBlock("Рекомендации", analysis["recommendations"]))
        
        self.results_layout.addStretch()
        self.results_scroll.show()
    
    def show_error(self, message: str):
        """Показать сообщение об ошибке"""
        QMessageBox.critical(self, "Ошибка", message)
    
    # === API методы ===
    
    def analyze_text(self):
        """Анализ текста"""
        text = self.text_input.toPlainText().strip()
        
        if len(text) < 10:
            self.show_error("Введите описание услуг минимум 10 символов")
            return
        
        logger.info("Запуск анализа текста, длина=%s", len(text))
        self.show_loading("Разбираю пакет услуг ТО...")
        
        self.current_worker = WorkerThread(api_client.analyze_text, text)
        self.current_worker.finished.connect(self.on_text_analysis_complete)
        self.current_worker.error.connect(lambda e: self.on_error(e))
        self.current_worker.start()
    
    def on_text_analysis_complete(self, result: dict):
        """Обработка результата анализа текста"""
        self.hide_loading()
        
        if result.get("success") and result.get("analysis"):
            self.show_results(result["analysis"], "text")
        else:
            self.show_error(result.get("error", "Неизвестная ошибка"))
    
    def analyze_image(self):
        """Анализ изображения"""
        if not self.drop_zone.selected_file:
            self.show_error("Выберите изображение для анализа")
            return
        
        logger.info("Запуск анализа изображения: %s", self.drop_zone.selected_file)
        self.show_loading("Разбираю визуал услуг ТО...")
        
        self.current_worker = WorkerThread(api_client.analyze_image, self.drop_zone.selected_file)
        self.current_worker.finished.connect(self.on_image_analysis_complete)
        self.current_worker.error.connect(lambda e: self.on_error(e))
        self.current_worker.start()
    
    def on_image_analysis_complete(self, result: dict):
        """Обработка результата анализа изображения"""
        self.hide_loading()
        
        if result.get("success") and result.get("analysis"):
            self.show_results(result["analysis"], "image")
        else:
            self.show_error(result.get("error", "Неизвестная ошибка"))
    
    def parse_site(self):
        """Парсинг сайта"""
        if not getattr(self, "_parsing_from_queue", False):
            self._parse_queue = []
        self._parsing_from_queue = False
        url = self.url_input.text().strip()
        
        if not url:
            self.show_error("Введите URL страницы услуг ТО")
            return
        
        logger.info("Запуск парсинга сайта: %s", url)
        self.show_loading("Загружаю страницу услуг ТО...")
        
        self.current_worker = WorkerThread(api_client.parse_demo, url)
        self.current_worker.finished.connect(self.on_parse_complete)
        self.current_worker.error.connect(lambda e: self.on_error(e))
        self.current_worker.start()
    
    def on_parse_complete(self, result: dict):
        """Обработка результата парсинга"""
        self.hide_loading()
        
        if result.get("success") and result.get("data"):
            data = result["data"]
            self.refresh_saved_sites_combo()
            self.load_saved_sites()
            if data.get("analysis"):
                self.show_results(data["analysis"], "parse")
            else:
                self.show_error("Не удалось проанализировать сайт")
            if getattr(self, "_parse_queue", None):
                self._parse_next_from_queue()
        else:
            self.show_error(result.get("error", "Неизвестная ошибка"))
            if getattr(self, "_parse_queue", None):
                self._parse_next_from_queue()
    
    def _url_for_input(self, url: str) -> str:
        return (url or "").replace("https://", "").replace("http://", "")

    def _flatten_tree(self, nodes, prefix=""):
        out = []
        for node in nodes or []:
            out.append({**node, "labelPrefix": prefix})
            out.extend(self._flatten_tree(node.get("children") or [], prefix + "— "))
        return out

    def refresh_saved_sites_combo(self):
        if not hasattr(self, "saved_sites_combo"):
            return
        self._updating_sites_combo = True
        self.saved_sites_combo.clear()
        self.saved_sites_combo.addItem("— выбрать из списка —", "")
        result = api_client.get_parsed_sites()
        items = self._flatten_tree(result.get("tree") or [])
        for item in items:
            mark = "✓ " if item.get("analyzed") else ""
            prefix = item.get("labelPrefix") or ""
            label = f"{mark}{prefix}{item.get('title') or item.get('url')}"
            self.saved_sites_combo.addItem(label, item.get("url"))
        self._updating_sites_combo = False

    def on_saved_site_chosen(self, index: int):
        if getattr(self, "_updating_sites_combo", False):
            return
        url = self.saved_sites_combo.itemData(index) or ""
        if url:
            self.url_input.setText(self._url_for_input(url))

    def select_saved_site(self, url: str, reparse: bool = False):
        self.url_input.setText(self._url_for_input(url))
        self.switch_tab(2)
        if reparse:
            self.parse_site()

    def _add_tree_item(self, parent, node):
        item = QTreeWidgetItem(parent)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        item.setCheckState(0, Qt.CheckState.Unchecked)
        analyzed = bool(node.get("analyzed"))
        item.setText(1, "✓ разобрана" if analyzed else "ожидает")
        item.setText(2, node.get("title") or node.get("url") or "")
        item.setText(3, node.get("url") or "")
        item.setData(0, Qt.ItemDataRole.UserRole, node.get("url"))
        item.setData(1, Qt.ItemDataRole.UserRole, node.get("id"))
        color = QColor("#10b981") if analyzed else QColor("#94a3b8")
        item.setForeground(1, QBrush(color))
        item.setForeground(2, QBrush(QColor("#e2e8f0") if analyzed else QColor("#cbd5e1")))
        for child in node.get("children") or []:
            self._add_tree_item(item, child)
        item.setExpanded(True)
        return item

    def load_saved_sites(self):
        if not hasattr(self, "sites_tree"):
            return
        self.sites_tree.clear()
        result = api_client.get_parsed_sites()
        tree = result.get("tree") or []
        self.refresh_saved_sites_combo()
        for node in tree:
            self._add_tree_item(self.sites_tree, node)

    def parse_checked_sites(self):
        urls = []

        def walk(item):
            if item.checkState(0) == Qt.CheckState.Checked:
                url = item.data(0, Qt.ItemDataRole.UserRole)
                if url:
                    urls.append(url)
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(self.sites_tree.topLevelItemCount()):
            walk(self.sites_tree.topLevelItem(i))
        if not urls:
            self.show_error("Отметьте ссылки в дереве для ручного разбора")
            return
        self._parse_queue = urls
        self._parse_next_from_queue()

    def _parse_next_from_queue(self):
        if not getattr(self, "_parse_queue", None):
            self.load_saved_sites()
            return
        url = self._parse_queue.pop(0)
        self._parsing_from_queue = True
        self.url_input.setText(self._url_for_input(url))
        self.parse_site()

    def delete_saved_site(self, site_id: str):
        api_client.delete_parsed_site(site_id)
        self.load_saved_sites()

    def clear_saved_sites(self):
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Очистить список сохранённых сайтов?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            api_client.clear_parsed_sites()
            self.load_saved_sites()

    def load_history(self):
        """Загрузка истории"""
        result = api_client.get_history()
        
        # Очищаем
        while self.history_layout.count():
            child = self.history_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if result.get("items"):
            for item in result["items"]:
                frame = QFrame()
                frame.setObjectName("historyItem")
                layout = QHBoxLayout(frame)
                
                # Иконка
                icons = {"text": "📝", "image": "🖼️", "parse": "🌐"}
                icon = QLabel(icons.get(item.get("request_type", ""), "📄"))
                icon.setStyleSheet("font-size: 24px;")
                
                # Контент
                content = QWidget()
                content_layout = QVBoxLayout(content)
                content_layout.setContentsMargins(0, 0, 0, 0)
                
                type_labels = {
                    "text": "Анализ описания услуг",
                    "image": "Анализ визуала ТО",
                    "parse": "Парсинг сайта сервиса",
                }
                type_label = QLabel(type_labels.get(item.get("request_type", ""), item.get("request_type", "")))
                type_label.setStyleSheet("color: #22d3ee; font-size: 12px; font-weight: bold;")
                
                summary = QLabel(item.get("request_summary", "")[:60] + "...")
                summary.setStyleSheet("color: #94a3b8;")
                
                content_layout.addWidget(type_label)
                content_layout.addWidget(summary)
                
                # Время
                timestamp = item.get("timestamp", "")
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp)
                        time_str = dt.strftime("%d.%m %H:%M")
                    except:
                        time_str = timestamp[:16]
                else:
                    time_str = ""
                
                time_label = QLabel(time_str)
                time_label.setStyleSheet("color: #64748b; font-size: 12px;")
                
                layout.addWidget(icon)
                layout.addWidget(content, stretch=1)
                layout.addWidget(time_label)
                
                self.history_layout.addWidget(frame)
        else:
            empty_label = QLabel("📋 История пуста")
            empty_label.setStyleSheet("color: #64748b; font-size: 16px; padding: 40px;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.history_layout.addWidget(empty_label)
        
        self.history_layout.addStretch()
    
    def clear_history(self):
        """Очистка истории"""
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Вы уверены, что хотите очистить историю?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            api_client.clear_history()
            self.load_history()
    
    def on_error(self, error: str):
        logger.error("Ошибка worker: %s", error)
        self.hide_loading()
        self.show_error(error)


def main():
    logger.info("Запуск desktop-приложения CompService")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

