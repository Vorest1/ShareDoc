from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QRect, Qt, QSignalBlocker, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFontMetrics
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .backend import (
    BackendError,
    ClientPreview,
    ClientSummary,
    ContractPreview,
    ContractSummary,
    GeneratedDocument,
    generate_documents_for_clients,
    generate_documents_for_contracts,
    get_client_previews_by_ids,
    get_contract_previews_by_ids,
    list_client_summaries,
    list_contract_summaries,
    send_document,
)


LETTER_TEMPLATE_KEYS = {"qualification", "scientific_guidance"}
CONTRACT_TEMPLATE_KEYS = {"contract_offer"}


class AutoHeightLabel(QLabel):
    def __init__(self, text: str = "", object_name: str = "valueLabel") -> None:
        super().__init__(text)

        self._h_padding = 12
        self._v_padding = 10

        self.setObjectName(object_name)
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.setContentsMargins(
            self._h_padding,
            self._v_padding,
            self._h_padding,
            self._v_padding,
        )
        self._update_height()

    def setText(self, text: str) -> None:
        super().setText(text)
        self._update_height()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_height()

    def _update_height(self) -> None:
        text = self.text() or " "

        margins = self.contentsMargins()
        available_width = max(
            120,
            self.width() - margins.left() - margins.right() - 2,
        )

        metrics = QFontMetrics(self.font())
        rect = metrics.boundingRect(
            QRect(0, 0, available_width, 10000),
            int(Qt.TextFlag.TextWordWrap),
            text,
        )

        height = rect.height() + margins.top() + margins.bottom() + 8
        self.setFixedHeight(max(44, height))


class GeneratePage(QWidget):
    open_send_page = pyqtSignal(object)

    STEP_TEMPLATE = 0
    STEP_DATA = 1
    STEP_PREVIEW = 2
    STEP_ACTIONS = 3

    def __init__(self) -> None:
        super().__init__()

        self.selected_template_key: str | None = None
        self.client_summaries: list[ClientSummary] = []
        self.contract_summaries: list[ContractSummary] = []

        self.selected_client_ids: list[int] = []
        self.selected_contract_ids: list[int] = []
        self.selected_client_previews: list[ClientPreview] = []
        self.selected_contract_previews: list[ContractPreview] = []
        self.generated_documents: list[GeneratedDocument] = []

        self._build_ui()
        self._load_reference_data()
        self._set_step(self.STEP_TEMPLATE)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        title = QLabel("Создание документа")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Работа выполняется по шагам: сначала выберите шаблон, затем данные, "
            "после этого проверьте информацию и перейдите к следующим действиям."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        root.addWidget(title)
        root.addWidget(subtitle)

        steps_row = QHBoxLayout()
        steps_row.setSpacing(10)

        self.step_chip_1 = self._make_step_chip("1. Выберите шаблон")
        self.step_chip_2 = self._make_step_chip("2. Выберите данные")
        self.step_chip_3 = self._make_step_chip("3. Проверьте данные")
        self.step_chip_4 = self._make_step_chip("4. Следующие действия")

        steps_row.addWidget(self.step_chip_1)
        steps_row.addWidget(self.step_chip_2)
        steps_row.addWidget(self.step_chip_3)
        steps_row.addWidget(self.step_chip_4)

        root.addLayout(steps_row)

        self.step_stack = QStackedWidget()
        self.step_stack.addWidget(self._build_template_page())
        self.step_stack.addWidget(self._build_data_page())
        self.step_stack.addWidget(self._build_preview_page())
        self.step_stack.addWidget(self._build_actions_page())

        root.addWidget(self.step_stack, 1)

        nav_row = QHBoxLayout()
        nav_row.setSpacing(12)

        self.back_button = QPushButton("Назад")
        self.back_button.clicked.connect(self._go_back)

        self.next_button = QPushButton("Далее")
        self.next_button.setObjectName("primaryButton")
        self.next_button.clicked.connect(self._go_next)

        nav_row.addStretch(1)
        nav_row.addWidget(self.back_button)
        nav_row.addWidget(self.next_button)

        root.addLayout(nav_row)

    def _build_template_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)

        box = QGroupBox("Шаг 1. Выберите шаблон")
        box_layout = QVBoxLayout(box)
        box_layout.setSpacing(12)

        info = self._info_label(
            "От выбранного шаблона зависит следующий шаг.\n"
            "Письмо → выбор одной или нескольких компаний-клиентов.\n"
            "Договор → выбор одного или нескольких существующих контрактов."
        )

        self.template_group = QButtonGroup(self)
        self.template_group.setExclusive(True)

        self.template_contract = self._make_template_button(
            "contract_offer",
            "Договор на обучение",
        )
        self.template_qualification = self._make_template_button(
            "qualification",
            "Письмо: повышение квалификации",
        )
        self.template_scientific = self._make_template_button(
            "scientific_guidance",
            "Письмо: научное руководство",
        )

        self.template_mode_info = self._info_label("Шаблон пока не выбран.")

        box_layout.addWidget(info)
        box_layout.addWidget(self.template_contract)
        box_layout.addWidget(self.template_qualification)
        box_layout.addWidget(self.template_scientific)
        box_layout.addWidget(self.template_mode_info)

        layout.addWidget(box)
        layout.addStretch(1)
        return page

    def _build_data_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)

        self.data_box = QGroupBox("Шаг 2. Выберите данные")
        data_layout = QVBoxLayout(self.data_box)
        data_layout.setSpacing(12)

        self.data_mode_info = self._info_label(
            "Сначала выберите шаблон на предыдущем шаге."
        )

        self.selector_stack = QStackedWidget()
        self.selector_stack.addWidget(self._build_empty_selector())
        self.selector_stack.addWidget(self._build_client_selector())
        self.selector_stack.addWidget(self._build_contract_selector())

        self.data_selection_info = self._info_label("Ничего не выбрано.")

        data_layout.addWidget(self.data_mode_info)
        data_layout.addWidget(self.selector_stack, 1)
        data_layout.addWidget(self.data_selection_info)

        layout.addWidget(self.data_box)
        return page

    def _build_preview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)

        box = QGroupBox("Шаг 3. Проверьте данные")
        box_layout = QVBoxLayout(box)
        box_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        self.preview_mode_value = self._add_preview_field(content_layout, "Режим")
        self.preview_template_value = self._add_preview_field(content_layout, "Шаблон")
        self.preview_company_value = self._add_preview_field(content_layout, "Организация / выборка")
        self.preview_contact_value = self._add_preview_field(content_layout, "Контакты / представители")
        self.preview_email_value = self._add_preview_field(content_layout, "Email")
        self.preview_program_value = self._add_preview_field(content_layout, "Программа")
        self.preview_period_value = self._add_preview_field(content_layout, "Период обучения")
        self.preview_contract_value = self._add_preview_field(content_layout, "Договор")
        self.preview_listeners_value = self._add_preview_field(content_layout, "Количество слушателей")
        self.preview_total_value = self._add_preview_field(content_layout, "Сумма")
        content_layout.addStretch(1)

        scroll.setWidget(content)
        box_layout.addWidget(scroll)

        layout.addWidget(box)
        return page

    def _build_actions_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)

        box = QGroupBox("Шаг 4. Следующие действия")
        box_layout = QVBoxLayout(box)
        box_layout.setSpacing(12)

        self.actions_context_info = self._info_label(
            "Документ ещё не подготовлен к генерации."
        )
        self.output_info = self._info_label("Документы ещё не сформированы.")

        button_row = QHBoxLayout()
        button_row.setSpacing(12)

        self.generate_button = QPushButton("Сформировать документ")
        self.generate_button.setObjectName("primaryButton")
        self.generate_button.clicked.connect(self._generate)

        self.open_file_button = QPushButton("Открыть документ")
        self.open_file_button.clicked.connect(self._open_generated_file)
        self.open_file_button.setEnabled(False)

        self.open_folder_button = QPushButton("Открыть папку")
        self.open_folder_button.clicked.connect(self._open_generated_folder)
        self.open_folder_button.setEnabled(False)

        self.goto_send_button = QPushButton("Перейти к отправке")
        self.goto_send_button.clicked.connect(self._go_to_send)
        self.goto_send_button.setEnabled(False)

        button_row.addWidget(self.generate_button)
        button_row.addWidget(self.open_file_button)
        button_row.addWidget(self.open_folder_button)
        button_row.addStretch(1)
        button_row.addWidget(self.goto_send_button)

        box_layout.addWidget(self.actions_context_info)
        box_layout.addWidget(self.output_info)
        box_layout.addLayout(button_row)

        layout.addWidget(box)
        layout.addStretch(1)
        return page

    def _build_empty_selector(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        label = self._info_label("Сначала выберите шаблон.")
        layout.addWidget(label)
        layout.addStretch(1)
        return page

    def _build_client_selector(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        search_row = QHBoxLayout()
        self.client_search_input = QLineEdit()
        self.client_search_input.setPlaceholderText(
            "Поиск по названию компании или email"
        )
        self.client_search_input.textChanged.connect(self._apply_client_filter)

        self.client_refresh_button = QPushButton("Обновить")
        self.client_refresh_button.clicked.connect(self._load_clients)

        self.client_select_all_button = QPushButton("Выбрать все")
        self.client_select_all_button.clicked.connect(self._select_all_clients)

        self.client_clear_button = QPushButton("Снять выбор")
        self.client_clear_button.clicked.connect(self._clear_client_selection)

        search_row.addWidget(self.client_search_input, 1)
        search_row.addWidget(self.client_refresh_button)
        search_row.addWidget(self.client_select_all_button)
        search_row.addWidget(self.client_clear_button)

        self.client_table = QTableWidget(0, 4)
        self.client_table.setHorizontalHeaderLabels(
            ["Выбор", "Организация", "Краткое название", "Email"]
        )
        self.client_table.verticalHeader().setVisible(False)
        self.client_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.client_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.client_table.itemChanged.connect(self._on_client_item_changed)
        self.client_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.client_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.client_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.client_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.client_table.setMinimumHeight(320)

        layout.addLayout(search_row)
        layout.addWidget(self.client_table)
        return page

    def _build_contract_selector(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        search_row = QHBoxLayout()
        self.contract_search_input = QLineEdit()
        self.contract_search_input.setPlaceholderText(
            "Поиск по номеру договора, организации или программе"
        )
        self.contract_search_input.textChanged.connect(self._apply_contract_filter)

        self.contract_refresh_button = QPushButton("Обновить")
        self.contract_refresh_button.clicked.connect(self._load_contracts)

        self.contract_select_all_button = QPushButton("Выбрать все")
        self.contract_select_all_button.clicked.connect(self._select_all_contracts)

        self.contract_clear_button = QPushButton("Снять выбор")
        self.contract_clear_button.clicked.connect(self._clear_contract_selection)

        search_row.addWidget(self.contract_search_input, 1)
        search_row.addWidget(self.contract_refresh_button)
        search_row.addWidget(self.contract_select_all_button)
        search_row.addWidget(self.contract_clear_button)

        self.contract_table = QTableWidget(0, 7)
        self.contract_table.setHorizontalHeaderLabels(
            [
                "Выбор",
                "Номер договора",
                "Дата",
                "Организация",
                "Программа",
                "Слушатели",
                "Сумма",
            ]
        )
        self.contract_table.verticalHeader().setVisible(False)
        self.contract_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.contract_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.contract_table.itemChanged.connect(self._on_contract_item_changed)
        self.contract_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for index in range(1, 7):
            self.contract_table.horizontalHeader().setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
        self.contract_table.setMinimumHeight(320)

        layout.addLayout(search_row)
        layout.addWidget(self.contract_table)
        return page

    def _make_step_chip(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setObjectName("stepChip")
        label.setProperty("state", "future")
        return label

    def _make_template_button(self, key: str, title: str) -> QPushButton:
        button = QPushButton(title)
        button.setCheckable(True)
        button.setProperty("template_key", key)
        button.setMinimumHeight(52)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda: self._select_template(button))
        self.template_group.addButton(button)
        return button

    def _value_label(self, text: str) -> QLabel:
        return AutoHeightLabel(text, "valueLabel")

    def _info_label(self, text: str) -> QLabel:
        return AutoHeightLabel(text, "infoCard")

    def _add_preview_field(self, parent_layout: QVBoxLayout, title: str) -> QLabel:
        frame = QFrame()
        frame.setObjectName("previewField")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("previewCaption")

        value_label = self._value_label("Не выбрано")

        frame_layout.addWidget(title_label)
        frame_layout.addWidget(value_label)
        parent_layout.addWidget(frame)
        return value_label

    def _load_reference_data(self) -> None:
        self._load_clients()
        self._load_contracts()

    def _load_clients(self) -> None:
        try:
            self.client_summaries = list_client_summaries()
            if self.selected_template_key in LETTER_TEMPLATE_KEYS:
                self._fill_client_table(self._filtered_clients())
        except BackendError as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def _load_contracts(self) -> None:
        try:
            self.contract_summaries = list_contract_summaries()
            if self.selected_template_key in CONTRACT_TEMPLATE_KEYS:
                self._fill_contract_table(self._filtered_contracts())
        except BackendError as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def _filtered_clients(self) -> list[ClientSummary]:
        text = self.client_search_input.text().strip().lower() if hasattr(self, "client_search_input") else ""
        if not text:
            return list(self.client_summaries)
        return [
            item
            for item in self.client_summaries
            if text in item.company_full_name.lower()
            or text in item.company_short_name.lower()
            or text in item.email.lower()
        ]

    def _filtered_contracts(self) -> list[ContractSummary]:
        text = self.contract_search_input.text().strip().lower() if hasattr(self, "contract_search_input") else ""
        if not text:
            return list(self.contract_summaries)
        return [
            item
            for item in self.contract_summaries
            if text in item.contract_number.lower()
            or text in item.company_short_name.lower()
            or text in item.program_name.lower()
        ]

    def _fill_client_table(self, rows: list[ClientSummary]) -> None:
        with QSignalBlocker(self.client_table):
            self.client_table.setRowCount(len(rows))
            for row_index, item in enumerate(rows):
                checkbox_item = QTableWidgetItem()
                checkbox_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                checkbox_item.setCheckState(
                    Qt.CheckState.Checked if item.client_id in self.selected_client_ids else Qt.CheckState.Unchecked
                )
                checkbox_item.setData(Qt.ItemDataRole.UserRole, item.client_id)
                self.client_table.setItem(row_index, 0, checkbox_item)

                values = [
                    item.company_full_name,
                    item.company_short_name,
                    item.email,
                ]
                for col_index, value in enumerate(values, start=1):
                    cell = QTableWidgetItem(value)
                    cell.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    self.client_table.setItem(row_index, col_index, cell)

        self._update_client_selection_info()

    def _fill_contract_table(self, rows: list[ContractSummary]) -> None:
        with QSignalBlocker(self.contract_table):
            self.contract_table.setRowCount(len(rows))
            for row_index, item in enumerate(rows):
                checkbox_item = QTableWidgetItem()
                checkbox_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                checkbox_item.setCheckState(
                    Qt.CheckState.Checked if item.contract_id in self.selected_contract_ids else Qt.CheckState.Unchecked
                )
                checkbox_item.setData(Qt.ItemDataRole.UserRole, item.contract_id)
                self.contract_table.setItem(row_index, 0, checkbox_item)

                values = [
                    item.contract_number,
                    item.contract_date,
                    item.company_short_name,
                    item.program_name,
                    item.listeners_count,
                    item.total_price,
                ]
                for col_index, value in enumerate(values, start=1):
                    cell = QTableWidgetItem(value)
                    cell.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    self.contract_table.setItem(row_index, col_index, cell)

        self._update_contract_selection_info()

    def _collect_checked_ids(self, table: QTableWidget) -> list[int]:
        ids: list[int] = []
        for row_index in range(table.rowCount()):
            item = table.item(row_index, 0)
            if item is None:
                continue
            if item.checkState() == Qt.CheckState.Checked:
                row_id = item.data(Qt.ItemDataRole.UserRole)
                if row_id is not None:
                    ids.append(int(row_id))
        return ids

    def _on_client_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        self.selected_client_ids = self._collect_checked_ids(self.client_table)
        self.selected_client_previews = []
        self.generated_documents = []
        self._reset_generated_state()
        self._update_client_selection_info()

    def _on_contract_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        self.selected_contract_ids = self._collect_checked_ids(self.contract_table)
        self.selected_contract_previews = []
        self.generated_documents = []
        self._reset_generated_state()
        self._update_contract_selection_info()

    def _select_template(self, button: QPushButton) -> None:
        self.selected_template_key = str(button.property("template_key"))

        self.selected_client_ids = []
        self.selected_contract_ids = []
        self.selected_client_previews = []
        self.selected_contract_previews = []
        self.generated_documents = []

        title = self._template_title(self.selected_template_key)
        self._clear_preview_page()
        self._reset_generated_state()

        if self.selected_template_key in LETTER_TEMPLATE_KEYS:
            self.template_mode_info.setText(
                f"Выбран шаблон: {title}\n"
                "На следующем шаге можно выбрать одну или несколько компаний-клиентов."
            )
            self.data_mode_info.setText(
                f"Режим: {title}\n"
                "Отметьте одну или несколько компаний галочками."
            )
            self.selector_stack.setCurrentIndex(1)
            self._fill_client_table(self._filtered_clients())
        elif self.selected_template_key in CONTRACT_TEMPLATE_KEYS:
            self.template_mode_info.setText(
                f"Выбран шаблон: {title}\n"
                "На следующем шаге можно выбрать один или несколько существующих договоров."
            )
            self.data_mode_info.setText(
                f"Режим: {title}\n"
                "Отметьте один или несколько договоров галочками."
            )
            self.selector_stack.setCurrentIndex(2)
            self._fill_contract_table(self._filtered_contracts())
        else:
            self.template_mode_info.setText("Шаблон пока не выбран.")
            self.data_mode_info.setText("Сначала выберите шаблон.")
            self.selector_stack.setCurrentIndex(0)
            self.data_selection_info.setText("Ничего не выбрано.")

    def _apply_client_filter(self) -> None:
        self._fill_client_table(self._filtered_clients())

    def _apply_contract_filter(self) -> None:
        self._fill_contract_table(self._filtered_contracts())

    def _select_all_clients(self) -> None:
        self._set_all_check_states(self.client_table, Qt.CheckState.Checked)
        self.selected_client_ids = self._collect_checked_ids(self.client_table)
        self._update_client_selection_info()

    def _clear_client_selection(self) -> None:
        self._set_all_check_states(self.client_table, Qt.CheckState.Unchecked)
        self.selected_client_ids = []
        self._update_client_selection_info()

    def _select_all_contracts(self) -> None:
        self._set_all_check_states(self.contract_table, Qt.CheckState.Checked)
        self.selected_contract_ids = self._collect_checked_ids(self.contract_table)
        self._update_contract_selection_info()

    def _clear_contract_selection(self) -> None:
        self._set_all_check_states(self.contract_table, Qt.CheckState.Unchecked)
        self.selected_contract_ids = []
        self._update_contract_selection_info()

    def _set_all_check_states(self, table: QTableWidget, state: Qt.CheckState) -> None:
        with QSignalBlocker(table):
            for row_index in range(table.rowCount()):
                item = table.item(row_index, 0)
                if item is not None:
                    item.setCheckState(state)

    def _update_client_selection_info(self) -> None:
        count = len(self.selected_client_ids)
        if count == 0:
            self.data_selection_info.setText("Компании не выбраны.")
            return

        names = [item.company_full_name for item in self.client_summaries if item.client_id in self.selected_client_ids]
        preview_lines = names[:5]
        suffix = "\n…" if len(names) > 5 else ""
        self.data_selection_info.setText(
            f"Выбрано компаний: {count}\n" + "\n".join(preview_lines) + suffix
        )

    def _update_contract_selection_info(self) -> None:
        count = len(self.selected_contract_ids)
        if count == 0:
            self.data_selection_info.setText("Договоры не выбраны.")
            return

        labels = [
            f"№ {item.contract_number} — {item.company_short_name}"
            for item in self.contract_summaries
            if item.contract_id in self.selected_contract_ids
        ]
        preview_lines = labels[:5]
        suffix = "\n…" if len(labels) > 5 else ""
        self.data_selection_info.setText(
            f"Выбрано договоров: {count}\n" + "\n".join(preview_lines) + suffix
        )

    def _refresh_preview_page(self) -> None:
        template_title = self._template_title(self.selected_template_key)
        self.preview_template_value.setText(template_title)

        if self.selected_template_key in LETTER_TEMPLATE_KEYS:
            previews = self.selected_client_previews
            count = len(previews)

            if count == 1:
                preview = previews[0]
                self.preview_mode_value.setText("Письмо → по компании")
                self.preview_company_value.setText(preview.company_full_name)

                contact_lines = []
                if preview.representative_name:
                    contact_lines.append(preview.representative_name)
                if preview.representative_phone:
                    contact_lines.append(preview.representative_phone)
                self.preview_contact_value.setText(
                    "\n".join(contact_lines) if contact_lines else "Не указано"
                )
                self.preview_email_value.setText(preview.email or "Не указано")
            else:
                self.preview_mode_value.setText("Письмо → массовая рассылка по компаниям")
                self.preview_company_value.setText(self._build_company_summary(previews))
                self.preview_contact_value.setText(
                    "Для каждой выбранной организации будут использованы её собственные данные представителя."
                )
                self.preview_email_value.setText(self._build_email_summary([item.email for item in previews]))

            self.preview_program_value.setText(template_title)
            self.preview_period_value.setText("Будет взято из программы шаблона")
            self.preview_contract_value.setText("Не требуется")
            self.preview_listeners_value.setText("Не требуется")
            self.preview_total_value.setText("Не требуется")
            return

        if self.selected_template_key in CONTRACT_TEMPLATE_KEYS:
            previews = self.selected_contract_previews
            count = len(previews)

            if count == 1:
                preview = previews[0]
                self.preview_mode_value.setText("Договор → по контракту")
                self.preview_company_value.setText(preview.company_full_name)

                contact_lines = []
                if preview.contact_full_name:
                    contact_lines.append(preview.contact_full_name)
                if preview.contact_phone:
                    contact_lines.append(preview.contact_phone)
                self.preview_contact_value.setText(
                    "\n".join(contact_lines) if contact_lines else "Не указано"
                )
                self.preview_email_value.setText(preview.contact_email or "Не указано")
                self.preview_program_value.setText(preview.program_name)
                self.preview_period_value.setText(preview.training_period)
                self.preview_contract_value.setText(preview.contract_number)
                self.preview_listeners_value.setText(preview.listeners_count)
                self.preview_total_value.setText(preview.total_price)
            else:
                self.preview_mode_value.setText("Договор → массовая рассылка по договорам")
                self.preview_company_value.setText(self._build_contract_company_summary(previews))
                self.preview_contact_value.setText(
                    "Для каждого договора будут использованы собственные контактные данные заказчика."
                )
                self.preview_email_value.setText(
                    self._build_email_summary([item.contact_email for item in previews])
                )
                self.preview_program_value.setText(self._build_program_summary(previews))
                self.preview_period_value.setText(self._build_period_summary(previews))
                self.preview_contract_value.setText(self._build_contract_summary(previews))
                self.preview_listeners_value.setText(self._build_listeners_summary(previews))
                self.preview_total_value.setText(self._build_total_summary(previews))

    def _refresh_actions_page(self) -> None:
        template_title = self._template_title(self.selected_template_key)

        if self.selected_template_key in LETTER_TEMPLATE_KEYS:
            count = len(self.selected_client_ids)
            self.actions_context_info.setText(
                f"Шаблон: {template_title}\n"
                f"Выбрано организаций: {count}\n"
                f"Будет сформировано документов: {count}"
            )
            self.generate_button.setText(
                "Сформировать документы" if count > 1 else "Сформировать документ"
            )
            return

        if self.selected_template_key in CONTRACT_TEMPLATE_KEYS:
            count = len(self.selected_contract_ids)
            self.actions_context_info.setText(
                f"Шаблон: {template_title}\n"
                f"Выбрано договоров: {count}\n"
                f"Будет сформировано документов: {count}"
            )
            self.generate_button.setText(
                "Сформировать документы" if count > 1 else "Сформировать документ"
            )
            return

        self.actions_context_info.setText("Недостаточно данных для генерации документа.")
        self.generate_button.setText("Сформировать документ")

    def _build_company_summary(self, previews: list[ClientPreview]) -> str:
        lines = [f"Выбрано организаций: {len(previews)}"]
        lines.extend(f"{index}. {item.company_full_name}" for index, item in enumerate(previews[:5], start=1))
        if len(previews) > 5:
            lines.append("…")
        return "\n".join(lines)

    def _build_contract_company_summary(self, previews: list[ContractPreview]) -> str:
        lines = [f"Выбрано договоров: {len(previews)}"]
        lines.extend(
            f"{index}. {item.company_full_name}" for index, item in enumerate(previews[:5], start=1)
        )
        if len(previews) > 5:
            lines.append("…")
        return "\n".join(lines)

    def _build_email_summary(self, emails: list[str]) -> str:
        cleaned = [email for email in emails if email]
        if not cleaned:
            return "Email не указаны"
        lines = [f"Указано email: {len(cleaned)}"]
        lines.extend(cleaned[:5])
        if len(cleaned) > 5:
            lines.append("…")
        return "\n".join(lines)

    def _build_program_summary(self, previews: list[ContractPreview]) -> str:
        values = list(dict.fromkeys(item.program_name for item in previews if item.program_name))
        if not values:
            return "Не указано"
        if len(values) == 1:
            return values[0]
        lines = [f"Разных программ: {len(values)}"]
        lines.extend(values[:5])
        if len(values) > 5:
            lines.append("…")
        return "\n".join(lines)

    def _build_period_summary(self, previews: list[ContractPreview]) -> str:
        values = list(dict.fromkeys(item.training_period for item in previews if item.training_period))
        if not values:
            return "Не указано"
        if len(values) == 1:
            return values[0]
        lines = [f"Разных периодов: {len(values)}"]
        lines.extend(values[:5])
        if len(values) > 5:
            lines.append("…")
        return "\n".join(lines)

    def _build_contract_summary(self, previews: list[ContractPreview]) -> str:
        lines = [f"Выбрано договоров: {len(previews)}"]
        lines.extend(f"№ {item.contract_number}" for item in previews[:5])
        if len(previews) > 5:
            lines.append("…")
        return "\n".join(lines)

    def _build_listeners_summary(self, previews: list[ContractPreview]) -> str:
        total = 0
        for item in previews:
            try:
                total += int(item.listeners_count)
            except ValueError:
                pass
        return f"Суммарно слушателей: {total}"

    def _build_total_summary(self, previews: list[ContractPreview]) -> str:
        if len(previews) == 1:
            return previews[0].total_price
        lines = [f"Документов: {len(previews)}"]
        lines.extend(f"№ {item.contract_number}: {item.total_price}" for item in previews[:5])
        if len(previews) > 5:
            lines.append("…")
        return "\n".join(lines)

    def _clear_preview_page(self) -> None:
        for label in (
            self.preview_mode_value,
            self.preview_template_value,
            self.preview_company_value,
            self.preview_contact_value,
            self.preview_email_value,
            self.preview_program_value,
            self.preview_period_value,
            self.preview_contract_value,
            self.preview_listeners_value,
            self.preview_total_value,
        ):
            label.setText("Не выбрано")

    def _reset_generated_state(self) -> None:
        self.generated_documents = []
        self.output_info.setText("Документы ещё не сформированы.")
        self.open_file_button.setEnabled(False)
        self.open_folder_button.setEnabled(False)
        self.goto_send_button.setEnabled(False)

    def _set_step(self, step_index: int) -> None:
        self.step_stack.setCurrentIndex(step_index)

        chips = [
            self.step_chip_1,
            self.step_chip_2,
            self.step_chip_3,
            self.step_chip_4,
        ]

        for index, chip in enumerate(chips):
            if index < step_index:
                state = "done"
            elif index == step_index:
                state = "current"
            else:
                state = "future"
            chip.setProperty("state", state)
            chip.style().unpolish(chip)
            chip.style().polish(chip)
            chip.update()

        self.back_button.setEnabled(step_index > self.STEP_TEMPLATE)

        if step_index == self.STEP_TEMPLATE:
            self.next_button.setEnabled(True)
            self.next_button.setText("Далее")
        elif step_index == self.STEP_DATA:
            self.next_button.setEnabled(True)
            self.next_button.setText("Далее")
        elif step_index == self.STEP_PREVIEW:
            self.next_button.setEnabled(True)
            self.next_button.setText("К действиям")
        else:
            self.next_button.setEnabled(False)
            self.next_button.setText("Далее")

    def _go_back(self) -> None:
        current = self.step_stack.currentIndex()
        if current > self.STEP_TEMPLATE:
            self._set_step(current - 1)

    def _go_next(self) -> None:
        current = self.step_stack.currentIndex()

        if current == self.STEP_TEMPLATE:
            if not self.selected_template_key:
                QMessageBox.warning(self, "Нет шаблона", "Сначала выберите шаблон.")
                return
            self._set_step(self.STEP_DATA)
            return

        if current == self.STEP_DATA:
            try:
                self._load_selected_previews()
            except BackendError as exc:
                QMessageBox.critical(self, "Ошибка", str(exc))
                return

            self._refresh_preview_page()
            self._set_step(self.STEP_PREVIEW)
            return

        if current == self.STEP_PREVIEW:
            self._refresh_actions_page()
            self._set_step(self.STEP_ACTIONS)
            return

    def _load_selected_previews(self) -> None:
        if self.selected_template_key in LETTER_TEMPLATE_KEYS:
            if not self.selected_client_ids:
                raise BackendError("Для шаблона письма выберите хотя бы одну компанию.")
            self.selected_client_previews = get_client_previews_by_ids(self.selected_client_ids)
            self.selected_contract_previews = []
            return

        if self.selected_template_key in CONTRACT_TEMPLATE_KEYS:
            if not self.selected_contract_ids:
                raise BackendError("Для шаблона договора выберите хотя бы один договор.")
            self.selected_contract_previews = get_contract_previews_by_ids(self.selected_contract_ids)
            self.selected_client_previews = []
            return

        raise BackendError("Сначала выберите шаблон.")

    def _generate(self) -> None:
        if not self.selected_template_key:
            QMessageBox.warning(self, "Нет шаблона", "Сначала выберите шаблон.")
            return

        try:
            if self.selected_template_key in LETTER_TEMPLATE_KEYS:
                if not self.selected_client_ids:
                    QMessageBox.warning(
                        self,
                        "Нет компаний",
                        "Для шаблона письма выберите хотя бы одну компанию.",
                    )
                    return
                self.generated_documents = generate_documents_for_clients(
                    template_key=self.selected_template_key,
                    client_ids=self.selected_client_ids,
                )
            elif self.selected_template_key in CONTRACT_TEMPLATE_KEYS:
                if not self.selected_contract_ids:
                    QMessageBox.warning(
                        self,
                        "Нет договоров",
                        "Для шаблона договора выберите хотя бы один договор.",
                    )
                    return
                self.generated_documents = generate_documents_for_contracts(
                    template_key=self.selected_template_key,
                    contract_ids=self.selected_contract_ids,
                )
            else:
                QMessageBox.warning(self, "Нет шаблона", "Сначала выберите шаблон.")
                return

            count = len(self.generated_documents)
            first_path = self.generated_documents[0].file_path
            lines = [
                f"Документов сформировано: {count}",
                f"Папка: {first_path.parent}",
            ]
            lines.extend(item.file_path.name for item in self.generated_documents[:5])
            if count > 5:
                lines.append("…")

            self.output_info.setText("\n".join(lines))
            self.open_file_button.setEnabled(True)
            self.open_folder_button.setEnabled(True)
            self.goto_send_button.setEnabled(True)

        except BackendError as exc:
            QMessageBox.critical(self, "Ошибка генерации", str(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка генерации",
                f"Не удалось сформировать документы: {exc}",
            )

    def _open_generated_file(self) -> None:
        if not self.generated_documents:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.generated_documents[0].file_path)))

    def _open_generated_folder(self) -> None:
        if not self.generated_documents:
            return
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self.generated_documents[0].file_path.parent))
        )

    def _go_to_send(self) -> None:
        if not self.generated_documents:
            return
        self.open_send_page.emit(list(self.generated_documents))

    def reset(self) -> None:
        self.selected_template_key = None
        self.selected_client_ids = []
        self.selected_contract_ids = []
        self.selected_client_previews = []
        self.selected_contract_previews = []
        self.generated_documents = []

        with QSignalBlocker(self.template_group):
            for button in self.template_group.buttons():
                button.setChecked(False)

        self.client_search_input.clear()
        self.contract_search_input.clear()

        self.template_mode_info.setText("Шаблон пока не выбран.")
        self.data_mode_info.setText("Сначала выберите шаблон на предыдущем шаге.")
        self.selector_stack.setCurrentIndex(0)
        self.data_selection_info.setText("Ничего не выбрано.")
        self.actions_context_info.setText("Документ ещё не подготовлен к генерации.")
        self._clear_preview_page()
        self._reset_generated_state()
        self._fill_client_table(self.client_summaries)
        self._fill_contract_table(self.contract_summaries)
        self._set_step(self.STEP_TEMPLATE)

    def _template_title(self, template_key: str | None) -> str:
        mapping = {
            "contract_offer": "Договор на обучение",
            "qualification": "Письмо: повышение квалификации",
            "scientific_guidance": "Письмо: научное руководство",
        }
        return mapping.get(template_key or "", "Документ")


class SendPage(QWidget):
    send_completed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.current_file_path: Path | None = None
        self.send_documents: list[GeneratedDocument] = []
        self.is_mass_mode = False
        self._build_ui()
        self.reset()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Отправка документа")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Проверьте файл, получателя и текст письма перед отправкой."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 4, 0)
        content_layout.setSpacing(16)

        file_box = QGroupBox("1. Документ")
        file_layout = QVBoxLayout(file_box)
        file_layout.setSpacing(12)

        self.file_info = self._info_label("Документ не выбран.")

        file_buttons = QHBoxLayout()
        file_buttons.setSpacing(12)

        self.choose_file_button = QPushButton("Выбрать файл")
        self.choose_file_button.clicked.connect(self._choose_file)

        self.open_file_button = QPushButton("Открыть документ")
        self.open_file_button.clicked.connect(self._open_file)

        file_buttons.addWidget(self.choose_file_button)
        file_buttons.addWidget(self.open_file_button)
        file_buttons.addStretch(1)

        file_layout.addWidget(self.file_info)
        file_layout.addLayout(file_buttons)
        content_layout.addWidget(file_box)

        recipient_box = QGroupBox("2. Получатель")
        recipient_layout = QVBoxLayout(recipient_box)
        recipient_layout.setSpacing(12)

        self.recipient_info = self._info_label("Получатель пока не задан.")

        self.to_input = QLineEdit()
        self.cc_input = QLineEdit()
        self.subject_input = QLineEdit()

        self.to_input.setPlaceholderText("Email получателя")
        self.cc_input.setPlaceholderText("Email в копии (необязательно)")
        self.subject_input.setPlaceholderText("Тема письма")

        recipient_layout.addWidget(self.recipient_info)
        self._add_input_field(recipient_layout, "Кому", self.to_input)
        self._add_input_field(recipient_layout, "Копия", self.cc_input)
        self._add_input_field(recipient_layout, "Тема письма", self.subject_input)
        content_layout.addWidget(recipient_box)

        body_box = QGroupBox("3. Текст письма")
        body_layout = QVBoxLayout(body_box)
        body_layout.setSpacing(12)

        body_caption = QLabel("Текст письма")
        body_caption.setObjectName("previewCaption")

        self.body_input = QTextEdit()
        self.body_input.setMinimumHeight(240)
        self.body_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        body_layout.addWidget(body_caption)
        body_layout.addWidget(self.body_input)
        content_layout.addWidget(body_box)

        actions_box = QGroupBox("4. Действия")
        actions_layout = QVBoxLayout(actions_box)
        actions_layout.setSpacing(12)

        self.send_info = self._info_label("Письмо ещё не отправлено.")

        buttons = QHBoxLayout()
        buttons.setSpacing(12)

        self.send_button = QPushButton("Отправить письмо")
        self.send_button.setObjectName("primaryButton")
        self.send_button.clicked.connect(self._send)

        buttons.addWidget(self.send_button)
        buttons.addStretch(1)

        actions_layout.addWidget(self.send_info)
        actions_layout.addLayout(buttons)
        content_layout.addWidget(actions_box)
        content_layout.addStretch(1)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

    def _info_label(self, text: str) -> QLabel:
        return AutoHeightLabel(text, "infoCard")

    def _add_input_field(
        self,
        parent_layout: QVBoxLayout,
        title: str,
        widget: QWidget,
    ) -> None:
        frame = QFrame()
        frame.setObjectName("previewField")

        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("previewCaption")

        frame_layout.addWidget(title_label)
        frame_layout.addWidget(widget)
        parent_layout.addWidget(frame)

    def set_context(self, documents: list[GeneratedDocument]) -> None:
        self.send_documents = list(documents)
        self.is_mass_mode = len(documents) > 1

        if not documents:
            self.reset()
            return

        self.current_file_path = documents[0].file_path
        self.cc_input.clear()
        self.body_input.setPlainText(
            "Добрый день.\n\n"
            "Направляем вам документ во вложении.\n"
            "Пожалуйста, ознакомьтесь с ним.\n\n"
            "С уважением,\n"
            "ФГАНУ ЦИТиС"
        )
        self.send_info.setText("Письмо ещё не отправлено.")

        if len(documents) == 1:
            document = documents[0]
            self.file_info.setText(
                f"Выбранный документ:\n{document.file_path.name}\n{document.file_path}"
            )
            self.recipient_info.setText(
                f"Один получатель:\n{document.to_email or 'Не указано'}"
            )
            self.to_input.setReadOnly(False)
            self.subject_input.setReadOnly(False)
            self.to_input.setText(document.to_email)
            self.subject_input.setText(document.subject)
            self.send_button.setText("Отправить письмо")
            return

        self.file_info.setText(self._build_mass_file_info(documents))
        self.recipient_info.setText(self._build_mass_recipient_info(documents))
        self.to_input.setReadOnly(True)
        self.subject_input.setReadOnly(True)
        self.to_input.setText("Автоматически по списку")
        self.subject_input.setText("Индивидуальные темы по каждому документу")
        self.send_button.setText("Отправить письма")

    def _build_mass_file_info(self, documents: list[GeneratedDocument]) -> str:
        lines = [f"Подготовлено документов: {len(documents)}"]
        lines.extend(item.file_path.name for item in documents[:5])
        if len(documents) > 5:
            lines.append("…")
        return "\n".join(lines)

    def _build_mass_recipient_info(self, documents: list[GeneratedDocument]) -> str:
        lines = [f"Получателей: {len(documents)}"]
        lines.extend(
            f"{item.label}: {item.to_email or 'Email не указан'}"
            for item in documents[:5]
        )
        if len(documents) > 5:
            lines.append("…")
        return "\n".join(lines)

    def _choose_file(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите документ",
            str(Path.cwd()),
            "Документы (*.docx *.pdf *.txt);;Все файлы (*.*)",
        )
        if not file_name:
            return

        self.send_documents = []
        self.is_mass_mode = False
        self.current_file_path = Path(file_name)
        self.file_info.setText(
            f"Выбранный документ:\n{self.current_file_path.name}\n{self.current_file_path}"
        )
        self.recipient_info.setText("Ручной режим отправки одного файла.")
        self.to_input.setReadOnly(False)
        self.subject_input.setReadOnly(False)
        self.to_input.clear()
        self.subject_input.clear()
        self.send_button.setText("Отправить письмо")

    def _open_file(self) -> None:
        if self.current_file_path is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.current_file_path)))

    def _send(self) -> None:
        body = self.body_input.toPlainText().strip()
        cc = self.cc_input.text().strip() or None

        if self.is_mass_mode and self.send_documents:
            invalid = [
                item.label
                for item in self.send_documents
                if not item.to_email or "@" not in item.to_email
            ]
            if invalid:
                QMessageBox.warning(
                    self,
                    "Некорректные адреса",
                    "У части документов не указан корректный email:\n"
                    + "\n".join(invalid[:10]),
                )
                return

            try:
                for item in self.send_documents:
                    send_document(
                        file_path=item.file_path,
                        to_email=item.to_email,
                        subject=item.subject,
                        body=body,
                        cc=cc,
                    )

                self.send_info.setText(
                    f"Письма успешно отправлены.\nВсего: {len(self.send_documents)}"
                )
                QMessageBox.information(
                    self,
                    "Готово",
                    f"Писем успешно отправлено: {len(self.send_documents)}.",
                )
                self.send_completed.emit()
            except BackendError as exc:
                QMessageBox.critical(self, "Ошибка отправки", str(exc))
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "Ошибка отправки",
                    f"Не удалось отправить письма: {exc}",
                )
            return

        if self.current_file_path is None:
            QMessageBox.warning(self, "Нет файла", "Сначала выберите документ.")
            return

        to_email = self.to_input.text().strip()
        subject = self.subject_input.text().strip()

        if not to_email:
            QMessageBox.warning(self, "Нет получателя", "Укажите адрес получателя.")
            return

        if "@" not in to_email:
            QMessageBox.warning(self, "Неверный адрес", "Проверьте адрес получателя.")
            return

        if not subject:
            QMessageBox.warning(self, "Нет темы", "Укажите тему письма.")
            return

        try:
            send_document(
                file_path=self.current_file_path,
                to_email=to_email,
                subject=subject,
                body=body,
                cc=cc,
            )
            self.send_info.setText(
                "Письмо успешно отправлено.\n"
                f"Кому: {to_email}\n"
                f"Файл: {self.current_file_path.name}"
            )
            QMessageBox.information(self, "Готово", "Письмо успешно отправлено.")
            self.send_completed.emit()
        except BackendError as exc:
            QMessageBox.critical(self, "Ошибка отправки", str(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка отправки",
                f"Не удалось отправить письмо: {exc}",
            )

    def reset(self) -> None:
        self.current_file_path = None
        self.send_documents = []
        self.is_mass_mode = False
        self.file_info.setText("Документ не выбран.")
        self.recipient_info.setText("Получатель пока не задан.")
        self.to_input.clear()
        self.cc_input.clear()
        self.subject_input.clear()
        self.to_input.setReadOnly(False)
        self.subject_input.setReadOnly(False)
        self.body_input.setPlainText(
            "Добрый день.\n\n"
            "Направляем вам документ во вложении.\n"
            "Пожалуйста, ознакомьтесь с ним.\n\n"
            "С уважением,\n"
            "ФГАНУ ЦИТиС"
        )
        self.send_info.setText("Письмо ещё не отправлено.")
        self.send_button.setText("Отправить письмо")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ShareDoc")
        self.resize(1440, 920)
        self.setMinimumSize(1240, 820)

        self._build_ui()
        self._apply_styles()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(260)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 18, 18, 18)
        sidebar_layout.setSpacing(12)

        app_title = QLabel("ShareDoc")
        app_title.setObjectName("appTitle")

        app_subtitle = QLabel("Подготовка и отправка документов")
        app_subtitle.setObjectName("appSubtitle")
        app_subtitle.setWordWrap(True)

        self.nav_generate = QPushButton("Создать документ")
        self.nav_generate.setCheckable(True)
        self.nav_send = QPushButton("Отправить документ")
        self.nav_send.setCheckable(True)

        for button in (self.nav_generate, self.nav_send):
            button.setMinimumHeight(46)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )

        nav_group = QButtonGroup(self)
        nav_group.setExclusive(True)
        nav_group.addButton(self.nav_generate, 0)
        nav_group.addButton(self.nav_send, 1)
        self.nav_generate.setChecked(True)

        self.pages = QStackedWidget()
        self.generate_page = GeneratePage()
        self.send_page = SendPage()

        self.pages.addWidget(self.generate_page)
        self.pages.addWidget(self.send_page)

        self.nav_generate.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        self.nav_send.clicked.connect(lambda: self.pages.setCurrentIndex(1))

        self.generate_page.open_send_page.connect(self._open_send_page)
        self.send_page.send_completed.connect(self._reset_after_send)

        sidebar_layout.addWidget(app_title)
        sidebar_layout.addWidget(app_subtitle)
        sidebar_layout.addSpacing(14)
        sidebar_layout.addWidget(self.nav_generate)
        sidebar_layout.addWidget(self.nav_send)
        sidebar_layout.addStretch(1)

        help_label = QLabel(
            "Порядок работы:\n"
            "1. Выберите шаблон\n"
            "2. Выберите данные\n"
            "3. Проверьте данные\n"
            "4. Сформируйте и отправьте документы"
        )
        help_label.setObjectName("helpLabel")
        help_label.setWordWrap(True)
        sidebar_layout.addWidget(help_label)

        root.addWidget(sidebar)
        root.addWidget(self.pages, 1)

        status = QStatusBar()
        status.showMessage("Готово к работе")
        self.setStatusBar(status)

    def _open_send_page(self, documents: list[GeneratedDocument]) -> None:
        self.send_page.set_context(documents)
        self.pages.setCurrentIndex(1)
        self.nav_send.setChecked(True)
        self.statusBar().showMessage("Подготовлен экран отправки")

    def _reset_after_send(self) -> None:
        self.send_page.reset()
        self.generate_page.reset()
        self.pages.setCurrentIndex(0)
        self.nav_generate.setChecked(True)
        self.statusBar().showMessage("Отправка завершена. Форма сброшена.")

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f5f7fb;
            }

            #sidebar {
                background: #1f2937;
                border-right: 1px solid #243244;
            }

            #appTitle {
                color: white;
                font-size: 24px;
                font-weight: 700;
            }

            #appSubtitle {
                color: #d3dce8;
                font-size: 13px;
            }

            #helpLabel {
                color: #d3dce8;
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                padding: 12px;
            }

            #pageTitle {
                color: #101828;
                font-size: 28px;
                font-weight: 700;
            }

            #pageSubtitle {
                color: #475467;
                font-size: 14px;
            }

            QGroupBox {
                background: #ffffff;
                border: 1px solid #dfe5ee;
                border-radius: 16px;
                margin-top: 10px;
                font-weight: 700;
                color: #1d2939;
                padding-top: 10px;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
            }

            QPushButton {
                background: #ffffff;
                color: #101828;
                border: 1px solid #d0d7e2;
                border-radius: 12px;
                padding: 10px 14px;
                font-size: 14px;
                min-height: 20px;
            }

            QPushButton:hover {
                background: #f8fafc;
            }

            QPushButton:checked {
                background: #dbeafe;
                border: 1px solid #60a5fa;
                font-weight: 700;
            }

            QPushButton#primaryButton {
                background: #2563eb;
                color: #ffffff;
                border: 1px solid #2563eb;
                font-weight: 700;
            }

            QPushButton#primaryButton:hover {
                background: #1d4ed8;
                border: 1px solid #1d4ed8;
            }

            QLineEdit, QTextEdit {
                background: #ffffff;
                border: 1px solid #d0d7e2;
                border-radius: 12px;
                padding: 10px 12px;
                font-size: 14px;
            }

            QLineEdit:focus, QTextEdit:focus {
                border: 1px solid #60a5fa;
            }

            QTableWidget {
                background: #ffffff;
                border: 1px solid #dfe5ee;
                border-radius: 12px;
                gridline-color: #edf2f7;
                selection-background-color: #dbeafe;
            }

            QHeaderView::section {
                background: #f3f6fb;
                border: none;
                border-bottom: 1px solid #dfe5ee;
                padding: 10px;
                font-weight: 700;
                color: #344054;
            }

            #infoCard, #valueLabel {
                background: #f8fafc;
                border: 1px solid #e3e8ef;
                border-radius: 12px;
                color: #101828;
            }

            #previewCaption {
                color: #344054;
                font-size: 13px;
                font-weight: 700;
                padding-left: 4px;
            }

            #stepChip {
                border-radius: 12px;
                padding: 10px 12px;
                font-weight: 700;
                background: #eef2f7;
                color: #667085;
                border: 1px solid #d0d7e2;
            }

            #stepChip[state="current"] {
                background: #dbeafe;
                color: #1d4ed8;
                border: 1px solid #60a5fa;
            }

            #stepChip[state="done"] {
                background: #ecfdf3;
                color: #027a48;
                border: 1px solid #86efac;
            }

            #stepChip[state="future"] {
                background: #f4f6f8;
                color: #667085;
                border: 1px solid #d0d7e2;
            }
            """
        )
