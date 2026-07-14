"""MaxDirector dock — PySide6, instrument-grade dark (LightMatch DESIGN.md house style).

Drives the Controller pipeline: Direct → Compile → Preview → Apply → Render. Every network/
LLM/render step runs on a QThread so Max never freezes; scene-touching steps marshal back to
the main thread (Max is single-threaded). Loaded inside 3ds Max only.

Ease-of-use hardening (from the 3-lens UX audit):
* Async re-entrancy guarded — action buttons disable during work and the QThread ref is held,
  so an impatient double-click can't GC a running thread and crash Max; a busy bar shows work.
* Stage gating — re-Direct/re-Compile reset downstream artifacts so a stale plan can never be
  written into a live client scene.
* Main-thread Apply/Understand are try/except-guarded with a wait cursor (a failed safety
  backup surfaces an actionable message instead of a silent freeze).
* First-run states are actionable (empty key/brief guarded; Save tests the connection).
* Reference image/URL and director style are exposed; blind-mode (no scouts) warns loudly.
"""

from __future__ import annotations

import os
from typing import List, Optional

from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore

from ..core.cinematic import DIRECTORS
from ..core.models import Brief, RenderBackend
from ..maxbridge import config as _config
from ..maxbridge.controller import Controller

ACCENT = "#c6bfff"
BG = "#0e0e12"
PANEL = "#16161c"
ERR = "#ff6b6b"
WARN = "#e0a500"


class _Worker(QtCore.QThread):
    done = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self.done.emit(self._fn())
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class MaxDirectorDock(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MaxDirector")
        self.setStyleSheet(
            f"QWidget{{background:{BG};color:#e8e8ef;font-family:Inter,Segoe UI;}}"
            f"QPushButton{{background:{PANEL};border:1px solid #2a2a33;padding:6px 10px;border-radius:6px;}}"
            f"QPushButton:disabled{{color:#5a5a66;border-color:#20202a;}}"
            f"QPushButton#primary{{background:{ACCENT};color:#12121a;font-weight:600;}}"
            f"QLineEdit,QComboBox,QPlainTextEdit,QTreeWidget,QSpinBox,QDoubleSpinBox"
            f"{{background:{PANEL};border:1px solid #2a2a33;border-radius:6px;padding:4px;}}"
            f"QLabel#help{{color:#9a9aa8;}}"
        )
        self.cfg = _config.load()
        self.ctrl = Controller(self.cfg)
        self.digest = None
        self.storyboard = None
        self.plan = None
        self.resolved = None
        self._blocked = False
        self._applied = False
        self.ref_image_path = ""
        self._active = False
        self._workers: List[_Worker] = []
        self._build()
        self._refresh_buttons()

    # ---------------------------------------------------------------- layout
    def _build(self):
        L = QtWidgets.QVBoxLayout(self)

        # key + model + test/save
        row = QtWidgets.QHBoxLayout()
        self.key = QtWidgets.QLineEdit(self.cfg.api_key)
        self.key.setPlaceholderText("oc_ gateway key")
        self.key.setEchoMode(QtWidgets.QLineEdit.Password)
        self.model = QtWidgets.QComboBox()
        self.model.addItems(["claude-opus-4-8", "gpt-5.5"])
        self.model.setCurrentText(self.cfg.model)
        self.b_save = QtWidgets.QPushButton("Test && Save")
        self.b_save.clicked.connect(self._on_test_save)
        row.addWidget(QtWidgets.QLabel("Key")); row.addWidget(self.key, 1)
        row.addWidget(self.model); row.addWidget(self.b_save)
        L.addLayout(row)

        help_lbl = QtWidgets.QLabel("1 Paste key → Test & Save   2 Type a brief   3 Direct → Compile → Preview → Apply → Render")
        help_lbl.setObjectName("help")
        L.addWidget(help_lbl)

        # brief
        self.prompt = QtWidgets.QPlainTextEdit()
        self.prompt.setPlaceholderText("e.g. cinematic golden-hour 3-shot reveal of the living room")
        self.prompt.setFixedHeight(56)
        L.addWidget(self.prompt)

        # options
        opt = QtWidgets.QHBoxLayout()
        self.director = QtWidgets.QComboBox()
        self.director.addItems(["(auto)"] + sorted(DIRECTORS))
        self.mood = QtWidgets.QLineEdit(); self.mood.setPlaceholderText("mood (optional)")
        self.duration = QtWidgets.QDoubleSpinBox(); self.duration.setRange(2, 120); self.duration.setValue(12)
        self.aspect = QtWidgets.QComboBox(); self.aspect.addItems(["16:9", "2.39:1", "9:16", "1:1"])
        self.backend = QtWidgets.QComboBox(); self.backend.addItems(["vray", "vantage"])
        opt.addWidget(QtWidgets.QLabel("dir")); opt.addWidget(self.director)
        opt.addWidget(self.mood, 1)
        opt.addWidget(QtWidgets.QLabel("dur")); opt.addWidget(self.duration)
        opt.addWidget(self.aspect); opt.addWidget(self.backend)
        L.addLayout(opt)

        # reference row (marquee feature — now reachable)
        refrow = QtWidgets.QHBoxLayout()
        self.b_refimg = QtWidgets.QPushButton("Ref image…")
        self.b_refimg.clicked.connect(self._pick_ref_image)
        self.ref_chip = QtWidgets.QLabel("no reference")
        self.ref_chip.setObjectName("help")
        self.ref_video = QtWidgets.QLineEdit(); self.ref_video.setPlaceholderText("reference video URL (optional)")
        refrow.addWidget(self.b_refimg); refrow.addWidget(self.ref_chip)
        refrow.addWidget(self.ref_video, 1)
        L.addLayout(refrow)

        # actions + busy bar
        acts = QtWidgets.QHBoxLayout()
        self.b_direct = QtWidgets.QPushButton("Direct"); self.b_direct.setObjectName("primary")
        self.b_compile = QtWidgets.QPushButton("Compile")
        self.b_preview = QtWidgets.QPushButton("Preview")
        self.b_apply = QtWidgets.QPushButton("Apply")
        self.b_render = QtWidgets.QPushButton("Render")
        for b in (self.b_direct, self.b_compile, self.b_preview, self.b_apply, self.b_render):
            acts.addWidget(b)
        L.addLayout(acts)
        self.b_direct.clicked.connect(self._on_direct)
        self.b_compile.clicked.connect(self._on_compile)
        self.b_preview.clicked.connect(self._on_preview)
        self.b_apply.clicked.connect(self._on_apply)
        self.b_render.clicked.connect(self._on_render)

        self.busy = QtWidgets.QProgressBar()
        self.busy.setRange(0, 0)          # indeterminate
        self.busy.setTextVisible(False)
        self.busy.setFixedHeight(4)
        self.busy.setVisible(False)
        L.addWidget(self.busy)

        # tree + log
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Shot", "Move / Finding", "Detail"])
        ph = QtWidgets.QTreeWidgetItem(self.tree, ["", "Direct to generate a shot list", ""])
        ph.setForeground(1, QtGui.QColor("#5a5a66"))
        L.addWidget(self.tree, 1)

        botrow = QtWidgets.QHBoxLayout()
        self.b_diag = QtWidgets.QPushButton("Diagnostics")
        self.b_diag.clicked.connect(self._diagnostics)
        botrow.addWidget(self.b_diag); botrow.addStretch(1)
        L.addLayout(botrow)

        self.log = QtWidgets.QPlainTextEdit(); self.log.setReadOnly(True); self.log.setFixedHeight(96)
        L.addWidget(self.log)

    # ---------------------------------------------------------------- helpers
    def _say(self, msg: str, color: Optional[str] = None):
        if color:
            self.log.appendHtml(f'<span style="color:{color}">{msg}</span>')
        else:
            self.log.appendPlainText(msg)

    def _busy_on(self):
        self._active = True
        self.busy.setVisible(True)
        for b in (self.b_direct, self.b_compile, self.b_preview, self.b_apply, self.b_render, self.b_save):
            b.setEnabled(False)

    def _busy_off(self):
        self._active = False
        self.busy.setVisible(False)
        self._refresh_buttons()

    def _refresh_buttons(self):
        """Stage gating — each button reflects the CURRENT upstream artifact, never a stale one."""
        if self._active:
            return
        has_brief = bool(self.key.text().strip()) and bool(self.prompt.toPlainText().strip())
        self.b_direct.setEnabled(has_brief)
        self.b_save.setEnabled(True)
        self.b_compile.setEnabled(self.storyboard is not None)
        ok_plan = self.resolved is not None and not self._blocked
        self.b_preview.setEnabled(ok_plan)
        self.b_apply.setEnabled(ok_plan)
        self.b_render.setEnabled(self._applied)
        self.b_direct.setToolTip("" if has_brief else "Paste your key and type a brief first")
        self.b_compile.setToolTip("" if self.storyboard else "Enabled after Direct")
        self.b_apply.setToolTip("" if ok_plan else "Enabled after Compile passes the critic")
        self.b_render.setToolTip("" if self._applied else "Enabled after Apply")

    def _run(self, fn, on_done):
        """Run fn on a worker; hold the ref so it can't be GC'd mid-run; re-enable on finish."""
        self._busy_on()
        w = _Worker(fn)
        self._workers.append(w)

        def _finish_ok(result, worker=w):
            self._busy_off()
            self._drop(worker)
            on_done(result)

        def _finish_err(msg, worker=w):
            self._busy_off()
            self._drop(worker)
            self._say(f"⚠ {msg}", ERR)
            self._say("→ check your key/network, then try again.", WARN)

        w.done.connect(_finish_ok)
        w.failed.connect(_finish_err)
        w.start()

    def _drop(self, worker):
        try:
            self._workers.remove(worker)
        except ValueError:
            pass

    def _brief(self) -> Brief:
        ds = self.director.currentText()
        return Brief(
            prompt=self.prompt.toPlainText().strip(),
            director_style=None if ds == "(auto)" else ds,
            mood=self.mood.text().strip() or None,
            duration_s=self.duration.value(),
            aspect=self.aspect.currentText(),
            fps=24,
            render_backend=RenderBackend(self.backend.currentText()),
            ref_image_path=self.ref_image_path or None,
            ref_video_url=self.ref_video.text().strip() or None,
        )

    # ---------------------------------------------------------------- config / refs
    def _persist(self):
        self.cfg.api_key = self.key.text().strip()
        self.cfg.model = self.model.currentText()
        self.cfg.save()
        self.ctrl = Controller(self.cfg)

    def _on_test_save(self):
        self._persist()
        if not self.cfg.api_key:
            self._say("Paste your oc_ key, then Test & Save.", WARN)
            self._refresh_buttons()
            return
        self._say("testing gateway…")
        from ..core import provider
        self._run(lambda: provider.ping(self.cfg.api_key, self.cfg.model),
                  lambda r: self._say(f"✓ {r}", ACCENT))

    def _pick_ref_image(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Reference image", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.ref_image_path = path
            self.ref_chip.setText("ref: " + os.path.basename(path))
            self.ref_chip.setStyleSheet(f"color:{ACCENT}")

    def _diagnostics(self):
        self._say("— diagnostics —")
        self._say(f"key: {'set' if self.cfg.api_key else 'MISSING'}   model: {self.cfg.model}")
        try:
            up = self.ctrl.cv.available if self.ctrl.cv else False
        except Exception:
            up = False
        self._say(f"CV sidecar: {'up (best-of-N/reference available)' if up else 'down (LLM-only mode)'}")
        self._say("click Test & Save to verify the gateway.")

    # ---------------------------------------------------------------- pipeline
    def _on_direct(self):
        if not self.key.text().strip():
            self._say("Paste your oc_ key and Test & Save first.", WARN); return
        if not self.prompt.toPlainText().strip():
            self._say("Type a brief first.", WARN); return
        self._persist()
        # reset EVERYTHING downstream so a stale plan can't be applied to the scene
        self.storyboard = self.plan = self.resolved = None
        self._blocked = self._applied = False

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            self.digest = self.ctrl.understand()      # scene read + scout capture (main thread)
        except Exception as e:  # noqa: BLE001
            self._say(f"⚠ scene read failed: {e}", ERR); return
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        self._say(f"scene: {len(self.digest.nodes)} objects, {len(self.digest.cameras)} cameras.")
        for w in self.digest.warnings:
            self._say("⚠ " + w, WARN)
        self._say("directing… (LLM — this can take up to a minute)")
        brief = self._brief()
        self._run(lambda: self.ctrl.direct(self.digest, brief), self._directed)

    def _directed(self, result):
        sb, notes, raw = result
        for n in notes:
            self._say("note: " + n)
        if sb is None:
            self._say("no storyboard — the model didn't return valid JSON.", ERR)
            if raw:
                self._say("model reply (first 300 chars): " + raw[:300].replace("\n", " "))
            self._say("→ click Direct again to retry (a long plan can truncate).", WARN)
            return
        self.storyboard = sb
        self.tree.clear()
        for s in sb.shots:
            scout = f"scout {s.from_scout}" if s.from_scout is not None else (s.subject_node or "")
            QtWidgets.QTreeWidgetItem(self.tree, [s.id, s.camera_move.value, f"{s.intent}  ·  {scout}"])
        for g in self.ctrl.resolve_gaps(sb, self.digest):
            gap = g["gap"]
            it = QtWidgets.QTreeWidgetItem(self.tree, [gap.shot_id, f"gap: {gap.kind}", gap.reason])
            it.setForeground(1, QtGui.QColor(ACCENT))
        self._refresh_buttons()
        self._say(f"storyboard: {len(sb.shots)} shots — review, then Compile.", ACCENT)

    def _on_compile(self):
        self.plan = self.resolved = None
        self._blocked = self._applied = False
        self._say("compiling authoring plan… (LLM)")
        self._run(lambda: self.ctrl.compile_and_check(self.digest, self.storyboard), self._compiled)

    def _compiled(self, result):
        plan, resolved, findings, errors, raw = result
        for e in errors:
            self._say("plan issue: " + e, WARN)
        if plan is None:
            self._say("no plan — the model didn't return valid JSON.", ERR)
            if raw:
                self._say("model reply (first 300 chars): " + raw[:300].replace("\n", " "))
            self._say("→ click Compile again to retry.", WARN)
            return
        self.plan, self.resolved = plan, resolved
        blocks = sum(1 for f in findings if f.severity.value == "block")
        warns = sum(1 for f in findings if f.severity.value == "warn")
        self.tree.clear()
        for s in plan.shots:
            QtWidgets.QTreeWidgetItem(self.tree, [s.id, s.path.kind, f"{s.camera.name} · {s.camera.fov_mm:.0f}mm"])
        crit = QtWidgets.QTreeWidgetItem(self.tree, ["Critic", f"{blocks} blockers · {warns} warnings", ""])
        for f in findings:
            it = QtWidgets.QTreeWidgetItem(crit, [f.shot_id, f"{f.severity.value.upper()}: {f.code}", f.message])
            it.setForeground(1, QtGui.QColor(ERR if f.severity.value == "block" else WARN))
        crit.setExpanded(True)
        self._blocked = self.ctrl.blocked(findings)
        self._refresh_buttons()
        if self._blocked:
            self._say(f"critic BLOCKED ({blocks}) — re-Direct or adjust the brief before applying.", ERR)
        else:
            self._say("plan checked — Preview to see it, or Apply (backup is automatic).", ACCENT)

    def _on_preview(self):
        self._say("rendering preview playblasts…")
        self._run(lambda: self.ctrl.preview(self.resolved),
                  lambda shots: self._say("preview: " + ", ".join(f"{k}→{os.path.basename(v) if v else 'failed'}" for k, v in shots.items())))

    def _on_apply(self):
        self._say("applying (backup → one undo → verify)…")
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            res = self.ctrl.apply(self.resolved, self.plan, self.digest)
        except Exception as e:  # noqa: BLE001  — e.g. a failed safety backup
            self._say(f"⚠ apply aborted: {e}", ERR)
            self._say("→ save the scene / check the folder is writable, then Apply again.", WARN)
            return
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self._say(f"applied: {len(res.verified)} verified, {len(res.unverified)} unverified, {len(res.failed)} failed.")
        for u in res.unverified:
            self._say("⚠ NOT VERIFIED: " + u, WARN)
        self._applied = res.ok or bool(res.verified)
        self._refresh_buttons()
        if self._applied:
            self._say("applied — Render when ready.", ACCENT)

    def _on_render(self):
        ids = [s.id for s in self.plan.shots]
        self._say(f"rendering {len(ids)} shot(s) via {self.plan.render.backend.value}, one by one…")
        self._run(lambda: self.ctrl.render(self.plan, on_progress=lambda s, st: self._say(f"  {s}: {st}")),
                  lambda r: self._render_done(r, ids))

    def _render_done(self, results: dict, ids: List[str]):
        ok = [s for s, v in results.items() if v == "ok"]
        bad = [s for s, v in results.items() if v != "ok"]
        never = [s for s in ids if s not in results]     # Vantage halts the queue
        self._say(f"render: {len(ok)} ok, {len(bad)} failed"
                  + (f", {len(never)} not run ({', '.join(never)})" if never else "."),
                  ACCENT if not bad and not never else WARN)
        for s in bad:
            self._say(f"  ✗ {s}: {results[s]}", ERR)


_DOCK = None


def show_dock():
    global _DOCK
    try:
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
    except Exception:
        pass
    if _DOCK is None:
        _DOCK = MaxDirectorDock()
    _DOCK.show()
    _DOCK.raise_()
    return _DOCK
