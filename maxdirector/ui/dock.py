"""MaxDirector dock — PySide6, instrument-grade dark (LightMatch DESIGN.md house style).

Drives the Controller pipeline. Every network/LLM/CV step runs on a QThread worker so Max's
UI never freezes; scene-touching steps (apply/preview/render) marshal back to the main thread
(Max is single-threaded for scene access). Approve gates are explicit buttons.

Loaded inside 3ds Max only (PySide6 + the Controller's pymxs bridge).
"""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore

from ..core.models import Brief, RenderBackend
from ..maxbridge import config as _config
from ..maxbridge.controller import Controller

ACCENT = "#c6bfff"   # tungsten-lavender accent; the only saturated colour
BG = "#0e0e12"
PANEL = "#16161c"


class _Worker(QtCore.QThread):
    done = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, fn, *a, **k):
        super().__init__()
        self._fn, self._a, self._k = fn, a, k

    def run(self):
        try:
            self.done.emit(self._fn(*self._a, **self._k))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class MaxDirectorDock(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MaxDirector")
        self.setStyleSheet(f"QWidget{{background:{BG};color:#e8e8ef;font-family:Inter,Segoe UI;}}"
                           f"QPushButton{{background:{PANEL};border:1px solid #2a2a33;padding:6px 10px;border-radius:6px;}}"
                           f"QPushButton#primary{{background:{ACCENT};color:#12121a;font-weight:600;}}"
                           f"QLineEdit,QComboBox,QPlainTextEdit,QTreeWidget{{background:{PANEL};border:1px solid #2a2a33;border-radius:6px;padding:4px;}}")
        self.cfg = _config.load()
        self.ctrl = Controller(self.cfg)
        self.digest = None
        self.storyboard = None
        self.plan = None
        self.resolved = None
        self._worker: Optional[_Worker] = None
        self._build()

    # ---------------------------------------------------------------- layout
    def _build(self):
        L = QtWidgets.QVBoxLayout(self)
        # key + model row
        row = QtWidgets.QHBoxLayout()
        self.key = QtWidgets.QLineEdit(self.cfg.api_key)
        self.key.setPlaceholderText("oc_ gateway key")
        self.key.setEchoMode(QtWidgets.QLineEdit.Password)
        self.model = QtWidgets.QComboBox()
        self.model.addItems(["claude-opus-4-8", "gpt-5.5"])
        self.model.setCurrentText(self.cfg.model)
        save = QtWidgets.QPushButton("Save")
        save.clicked.connect(self._save_cfg)
        row.addWidget(QtWidgets.QLabel("Key")); row.addWidget(self.key, 1)
        row.addWidget(self.model); row.addWidget(save)
        L.addLayout(row)

        # brief
        self.prompt = QtWidgets.QPlainTextEdit()
        self.prompt.setPlaceholderText("e.g. cinematic golden-hour 3-shot reveal of the living room")
        self.prompt.setFixedHeight(60)
        L.addWidget(self.prompt)
        opt = QtWidgets.QHBoxLayout()
        self.duration = QtWidgets.QDoubleSpinBox(); self.duration.setRange(2, 120); self.duration.setValue(12)
        self.aspect = QtWidgets.QComboBox(); self.aspect.addItems(["16:9", "2.39:1", "9:16", "1:1"])
        self.backend = QtWidgets.QComboBox(); self.backend.addItems(["vray", "vantage"])
        opt.addWidget(QtWidgets.QLabel("dur")); opt.addWidget(self.duration)
        opt.addWidget(QtWidgets.QLabel("aspect")); opt.addWidget(self.aspect)
        opt.addWidget(QtWidgets.QLabel("render")); opt.addWidget(self.backend)
        L.addLayout(opt)

        # actions
        acts = QtWidgets.QHBoxLayout()
        self.b_direct = QtWidgets.QPushButton("Direct"); self.b_direct.setObjectName("primary")
        self.b_compile = QtWidgets.QPushButton("Compile"); self.b_compile.setEnabled(False)
        self.b_apply = QtWidgets.QPushButton("Apply"); self.b_apply.setEnabled(False)
        self.b_render = QtWidgets.QPushButton("Render"); self.b_render.setEnabled(False)
        for b in (self.b_direct, self.b_compile, self.b_apply, self.b_render):
            acts.addWidget(b)
        L.addLayout(acts)
        self.b_direct.clicked.connect(self._on_direct)
        self.b_compile.clicked.connect(self._on_compile)
        self.b_apply.clicked.connect(self._on_apply)
        self.b_render.clicked.connect(self._on_render)

        # storyboard / plan tree + log
        self.tree = QtWidgets.QTreeWidget(); self.tree.setHeaderLabels(["Shot", "Move / Finding", "Detail"])
        L.addWidget(self.tree, 1)
        self.log = QtWidgets.QPlainTextEdit(); self.log.setReadOnly(True); self.log.setFixedHeight(90)
        L.addWidget(self.log)

    # ---------------------------------------------------------------- helpers
    def _say(self, msg: str):
        self.log.appendPlainText(msg)

    def _save_cfg(self):
        self.cfg.api_key = self.key.text().strip()
        self.cfg.model = self.model.currentText()
        self.cfg.save()
        self.ctrl = Controller(self.cfg)
        self._say("settings saved.")

    def _brief(self) -> Brief:
        return Brief(prompt=self.prompt.toPlainText().strip(),
                     duration_s=self.duration.value(), aspect=self.aspect.currentText(),
                     render_backend=RenderBackend(self.backend.currentText()))

    def _run(self, fn, on_done):
        self._worker = _Worker(fn)
        self._worker.done.connect(on_done)
        self._worker.failed.connect(lambda e: self._say(f"error: {e}"))
        self._worker.start()

    # ---------------------------------------------------------------- pipeline
    def _on_direct(self):
        self._save_cfg()
        self.digest = self.ctrl.understand()   # scene read: fast, main thread
        self._say(f"scene: {len(self.digest.nodes)} objects, {len(self.digest.cameras)} cameras.")
        for w in self.digest.warnings:
            self._say("⚠ " + w)
        brief = self._brief()
        self._say("directing… (LLM)")
        self._run(lambda: self.ctrl.direct(self.digest, brief), self._directed)

    def _directed(self, result):
        sb, notes = result
        for n in notes:
            self._say("note: " + n)
        if sb is None:
            self._say("no storyboard returned."); return
        self.storyboard = sb
        self.tree.clear()
        for s in sb.shots:
            QtWidgets.QTreeWidgetItem(self.tree, [s.id, s.camera_move.value, s.intent])
        for g in self.ctrl.resolve_gaps(sb, self.digest):
            gap = g["gap"]
            item = QtWidgets.QTreeWidgetItem(self.tree, [gap.shot_id, f"gap: {gap.kind}", gap.reason])
            item.setForeground(1, QtGui.QColor(ACCENT))
        self.b_compile.setEnabled(True)
        self._say("storyboard ready — review, then Compile.")

    def _on_compile(self):
        self._say("compiling authoring plan… (LLM)")
        self._run(lambda: self.ctrl.compile_and_check(self.digest, self.storyboard), self._compiled)

    def _compiled(self, result):
        plan, resolved, findings, errors = result
        for e in errors:
            self._say("plan issue: " + e)
        if plan is None:
            self._say("no plan returned."); return
        self.plan, self.resolved = plan, resolved
        self.tree.clear()
        for s in plan.shots:
            QtWidgets.QTreeWidgetItem(self.tree, [s.id, s.path.kind, f"{s.camera.name} @ {s.camera.fov_mm}mm"])
        for f in findings:
            it = QtWidgets.QTreeWidgetItem(self.tree, [f.shot_id, f"critic: {f.code}", f.message])
            it.setForeground(1, QtGui.QColor("#ff6b6b" if f.severity.value == "block" else "#e0a500"))
        if self.ctrl.blocked(findings):
            self._say("critic BLOCKED — fix before applying (re-Direct or adjust).")
            self.b_apply.setEnabled(False)
        else:
            self.b_apply.setEnabled(True)
            self._say("plan checked — Apply when ready (backup is automatic).")

    def _on_apply(self):
        self._say("applying (backup → one undo → verify)…")
        # scene mutation: must run on the main thread; QThread not used here
        res = self.ctrl.apply(self.resolved, self.plan, self.digest)
        self._say(f"applied: {len(res.verified)} verified, {len(res.unverified)} unverified, {len(res.failed)} failed.")
        for u in res.unverified:
            self._say("⚠ NOT VERIFIED: " + u)
        self.b_render.setEnabled(res.ok or bool(res.verified))

    def _on_render(self):
        self._say(f"rendering via {self.plan.render.backend.value} (shot by shot)…")
        self._run(lambda: self.ctrl.render(self.plan, on_progress=lambda s, st: self._say(f"  {s}: {st}")),
                  lambda r: self._say("render complete: " + ", ".join(f"{k}={v}" for k, v in r.items())))


_DOCK = None


def show_dock():
    global _DOCK
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
    except Exception:
        pass
    if _DOCK is None:
        _DOCK = MaxDirectorDock()
    _DOCK.show()
    _DOCK.raise_()
    return _DOCK
