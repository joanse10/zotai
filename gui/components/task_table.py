"""
Componenta tabel de sarcini pentru coada de documente cu filtre și căutare —
optimizată pentru reconciliere in-place (fără distrugerea și recrearea rândurilor).
"""

import customtkinter as ctk
from typing import List, Callable, Optional, Dict
from gui.theme import Theme, ThemedSegmentedButton
from gui.models import TaskItem
from gui.components.task_row import TaskRowComponent
from core.i18n import tr


class TaskTableComponent(ctk.CTkFrame):
    def __init__(
        self,
        master,
        tasks: List[TaskItem],
        selected_task_id: Optional[str],
        on_select_task: Callable[[TaskItem], None],
        on_delete_task: Callable[[TaskItem], None],
        on_clear_completed: Callable[[], None]
    ):
        super().__init__(master, fg_color=Theme.BG_PANEL, corner_radius=10, border_width=1, border_color=Theme.BG_BORDER)

        self.tasks = tasks
        self.selected_task_id = selected_task_id
        self.on_select_task = on_select_task
        self.on_delete_task = on_delete_task
        self.on_clear_completed = on_clear_completed

        self.current_filter_key = "all"
        self.search_query = ""

        self._rows_by_id: Dict[str, TaskRowComponent] = {}
        self._empty_label: Optional[ctk.CTkLabel] = None

        self._build_ui()

    def _get_filter_values(self):
        return [tr("filter_all"), tr("filter_processing"), tr("filter_queued"), tr("filter_completed")]

    def _build_ui(self):
        # 1. Bara de control superioară (filtre + căutare)
        top_bar = ctk.CTkFrame(self, height=44, fg_color="transparent")
        top_bar.pack(fill="x", padx=12, pady=(12, 6))

        # Butoane de filtrare
        self.filter_buttons = ThemedSegmentedButton(
            top_bar,
            values=self._get_filter_values(),
            height=30,
            font=Theme.font_caption_bold(),
            border_width=1,
            fg_color=Theme.BG_PANEL_ALT,
            unselected_color=Theme.BG_PANEL_ALT,
            unselected_hover_color=Theme.BG_BORDER,
            selected_color=Theme.PRIMARY,
            selected_hover_color=Theme.PRIMARY_HOVER,
            command=self._on_filter_changed
        )
        self.filter_buttons.set(tr("filter_all"))
        self.filter_buttons.pack(side="left")

        # Butonul de ștergere a sarcinilor finalizate
        self.btn_clear = ctk.CTkButton(
            top_bar,
            text=tr("btn_clear_completed"),
            width=140,
            height=28,
            fg_color="transparent",
            hover_color=Theme.BG_BORDER,
            text_color=Theme.TEXT_MUTED,
            font=Theme.font_caption(),
            command=self.on_clear_completed
        )
        self.btn_clear.pack(side="right", padx=(8, 0))

        # Caseta de căutare
        self.search_entry = ctk.CTkEntry(
            top_bar,
            placeholder_text="🔍 ...",
            width=170,
            height=28,
            border_width=1,
            fg_color=Theme.BG_INPUT,
            border_color=Theme.BG_BORDER,
            text_color=Theme.TEXT_MAIN,
            font=Theme.font_caption()
        )
        self.search_entry.pack(side="right")
        self.search_entry.bind("<KeyRelease>", self._on_search_changed)

        # 2. Anteturile coloanelor tabelului
        th_bar = ctk.CTkFrame(self, height=36, fg_color=Theme.BG_PANEL_ALT, border_width=1, border_color=Theme.BG_BORDER, corner_radius=6)
        th_bar.pack(fill="x", padx=12, pady=(6, 4))
        th_bar.pack_propagate(False)
        th_bar.grid_columnconfigure(0, weight=4, minsize=200)
        th_bar.grid_columnconfigure(1, weight=0, minsize=80)
        th_bar.grid_columnconfigure(2, weight=0, minsize=40)
        th_bar.grid_columnconfigure(3, weight=1, minsize=110)
        th_bar.grid_columnconfigure(4, weight=1, minsize=120)
        th_bar.grid_columnconfigure(5, weight=0, minsize=32)

        self.th_doc = ctk.CTkLabel(th_bar, text=tr("col_doc"), anchor="w", font=Theme.font_caption_bold(), text_color=Theme.TEXT_MUTED)
        self.th_doc.grid(row=0, column=0, sticky="w", padx=(16, 4), pady=6)

        self.th_layer = ctk.CTkLabel(th_bar, text=tr("col_layer"), anchor="center", font=Theme.font_caption_bold(), text_color=Theme.TEXT_MUTED)
        self.th_layer.grid(row=0, column=1, sticky="w", padx=2, pady=6)

        self.th_lang = ctk.CTkLabel(th_bar, text=tr("col_lang"), anchor="center", font=Theme.font_caption_bold(), text_color=Theme.TEXT_MUTED)
        self.th_lang.grid(row=0, column=2, sticky="w", padx=2, pady=6)

        self.th_stage = ctk.CTkLabel(th_bar, text=tr("col_stage"), anchor="w", font=Theme.font_caption_bold(), text_color=Theme.TEXT_MUTED)
        self.th_stage.grid(row=0, column=3, sticky="w", padx=4, pady=6)

        self.th_zotero = ctk.CTkLabel(th_bar, text=tr("col_zotero"), anchor="w", font=Theme.font_caption_bold(), text_color=Theme.TEXT_MUTED)
        self.th_zotero.grid(row=0, column=4, sticky="w", padx=4, pady=6)

        # 3. Lista de sarcini cu derulare
        self.scroll_area = ctk.CTkScrollableFrame(
            self,
            fg_color=Theme.BG_PANEL,
            scrollbar_fg_color="transparent",
            scrollbar_button_color=Theme.BG_BORDER,
            scrollbar_button_hover_color=Theme.TEXT_MUTED
        )
        self.scroll_area.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        self.set_tasks(self.tasks, self.selected_task_id)

    def refresh_texts(self):
        self.filter_buttons.configure(values=self._get_filter_values())
        cur_map = {"all": tr("filter_all"), "proc": tr("filter_processing"),
                   "queue": tr("filter_queued"), "done": tr("filter_completed")}
        self.filter_buttons.set(cur_map.get(self.current_filter_key, tr("filter_all")))
        self.btn_clear.configure(text=tr("btn_clear_completed"))
        self.th_doc.configure(text=tr("col_doc"))
        self.th_layer.configure(text=tr("col_layer"))
        self.th_lang.configure(text=tr("col_lang"))
        self.th_stage.configure(text=tr("col_stage"))
        self.th_zotero.configure(text=tr("col_zotero"))

        if self._empty_label:
            self._empty_label.configure(text=tr("empty_queue"))

        # Actualizează rândurile existente fără a le recrea
        for row in self._rows_by_id.values():
            row.update_task(row.task)

    def select_task_by_id(self, task_id: Optional[str]):
        """Schimbă selecția vizuală instantaneu (0ms, fără redesenarea tabelului)."""
        if self.selected_task_id == task_id:
            return
        old_id = self.selected_task_id
        self.selected_task_id = task_id

        if old_id and old_id in self._rows_by_id:
            self._rows_by_id[old_id].set_selected(False)
        if task_id and task_id in self._rows_by_id:
            self._rows_by_id[task_id].set_selected(True)

    def update_single_task(self, task: TaskItem):
        """Actualizează o singură sarcină pe loc (in-place) fără a atinge celelalte rânduri."""
        if task.id in self._rows_by_id:
            self._rows_by_id[task.id].update_task(task)

    def _get_filtered_tasks(self) -> List[TaskItem]:
        filtered = []
        for t in self.tasks:
            if self.search_query and self.search_query.lower() not in t.file_name.lower():
                continue
            stage_l = t.pipeline_stage.lower()
            if self.current_filter_key == "proc" and any(k in stage_l for k in ("finalizat", "completed", "xmp", "așteptare", "pending")):
                continue
            if self.current_filter_key == "queue" and "offline" not in t.zotero_status.lower() and "așteptare" not in t.zotero_status.lower() and "queued" not in t.zotero_status.lower():
                continue
            if self.current_filter_key == "done" and not any(k in stage_l for k in ("finalizat", "completed", "xmp")):
                continue
            filtered.append(t)
        return filtered

    def set_tasks(self, tasks: List[TaskItem], selected_task_id: Optional[str]):
        """
        Reconciliere in-place de înaltă performanță:
        Refolosește widget-urile existente și evită distrugerea în masă a canvas-urilor Tkinter.
        """
        self.tasks = tasks
        self.selected_task_id = selected_task_id
        filtered = self._get_filtered_tasks()
        filtered_ids = {t.id for t in filtered}

        if not filtered:
            # Elimină rândurile existente
            for row in list(self._rows_by_id.values()):
                row.destroy()
            self._rows_by_id.clear()

            # Afișează mesajul de coadă goală
            if not self._empty_label:
                self._empty_label = ctk.CTkLabel(
                    self.scroll_area,
                    text=tr("empty_queue"),
                    font=Theme.font_body(),
                    text_color=Theme.TEXT_DARK
                )
            self._empty_label.pack(pady=40)
            return

        # Ascunde eticheta de coadă goală dacă există
        if self._empty_label:
            self._empty_label.pack_forget()

        # 1. Elimină rândurile care nu mai sunt în lista filtrată
        for rem_id in list(self._rows_by_id.keys()):
            if rem_id not in filtered_ids:
                self._rows_by_id[rem_id].destroy()
                del self._rows_by_id[rem_id]

        # 2. Actualizează rândurile existente sau creează-le doar pe cele noi
        for task in filtered:
            is_selected = (task.id == selected_task_id)
            if task.id in self._rows_by_id:
                # Actualizare pe loc: 0ms cost de creare widget
                self._rows_by_id[task.id].update_task(task, is_selected=is_selected)
            else:
                # Creare doar pentru sarcini nou apărute
                row = TaskRowComponent(
                    self.scroll_area,
                    task=task,
                    is_selected=is_selected,
                    on_select=self.on_select_task,
                    on_delete=self.on_delete_task
                )
                self._rows_by_id[task.id] = row
                row.pack(fill="x", pady=3, padx=6)

    def _on_filter_changed(self, value: str):
        if value == tr("filter_processing"):
            self.current_filter_key = "proc"
        elif value == tr("filter_queued"):
            self.current_filter_key = "queue"
        elif value == tr("filter_completed"):
            self.current_filter_key = "done"
        else:
            self.current_filter_key = "all"
        self.set_tasks(self.tasks, self.selected_task_id)

    def _on_search_changed(self, event):
        self.search_query = self.search_entry.get().strip()
        self.set_tasks(self.tasks, self.selected_task_id)
