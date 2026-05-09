import os

import vlc
from PyQt6.QtCore import QEvent, QTimer, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.i18n import _


class VideoPlayerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("video_player_widget")
        self._state = "idle"
        self._vlc_instance: vlc.Instance | None = None
        self._media_player: vlc.MediaPlayer | None = None
        self._current_file: str | None = None
        self._is_fullscreen = False
        self._fullscreen_window: QWidget | None = None
        self._is_seeking = False
        self._duration_ms = 0
        self._pending_restore_time = -1
        self._is_live_preview = False

        self._fullscreen_hide_timer = QTimer(self)
        self._fullscreen_hide_timer.setSingleShot(True)
        self._fullscreen_hide_timer.timeout.connect(self._hide_controls)

        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_progress)
        self._update_timer.setInterval(250)

        self._init_ui()
        self._init_vlc()
        self._apply_state()

    def _init_vlc(self):
        try:
            self._vlc_instance = vlc.Instance("--intf=dummy", "--no-video-title-show")
            self._media_player = self._vlc_instance.media_player_new()
        except Exception as exc:
            self._state = "error"
            self._show_error_message(_("VLC initialization failed") + f": {exc}")

    def _init_ui(self):
        self.setStyleSheet(
            """
            QWidget#video_player_widget {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 14px;
            }
            QLabel#player_title {
                color: #0f172a;
                font-size: 14px;
                font-weight: 600;
            }
            QLabel#player_badge {
                padding: 4px 10px;
                border-radius: 999px;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#player_hint {
                color: #64748b;
                font-size: 12px;
            }
            QWidget#video_container {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0f172a, stop:1 #111827);
                border-radius: 12px;
            }
            QLabel#player_thumbnail {
                background: transparent;
                color: #cbd5e1;
                font-size: 16px;
            }
            QLabel#player_overlay {
                background: rgba(15, 23, 42, 0.76);
                color: #f8fafc;
                border-radius: 10px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#player_error {
                background: rgba(220, 38, 38, 0.92);
                color: white;
                font-size: 13px;
                border-radius: 10px;
                padding: 10px 14px;
            }
            QWidget#player_controls {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
            QPushButton#player_btn {
                background: #ffffff;
                color: #0f172a;
                border: 1px solid #dbe4f0;
                border-radius: 9px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#player_btn:hover {
                border-color: #3b82f6;
                color: #1d4ed8;
            }
            QPushButton#player_btn:pressed {
                background: #eff6ff;
            }
            QPushButton#player_btn:disabled {
                color: #94a3b8;
                border-color: #e2e8f0;
                background: #f8fafc;
            }
            QSlider#player_progress_slider::groove:horizontal {
                height: 6px;
                background: #dbe4f0;
                border-radius: 3px;
            }
            QSlider#player_progress_slider::sub-page:horizontal {
                background: #2563eb;
                border-radius: 3px;
            }
            QSlider#player_progress_slider::handle:horizontal {
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
                background: #ffffff;
                border: 2px solid #2563eb;
            }
            QSlider#player_volume_slider::groove:horizontal {
                height: 4px;
                background: #dbe4f0;
                border-radius: 2px;
            }
            QSlider#player_volume_slider::sub-page:horizontal {
                background: #64748b;
                border-radius: 2px;
            }
            QSlider#player_volume_slider::handle:horizontal {
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
                background: #0f172a;
            }
            QLabel#player_time_label, QLabel#player_volume_label {
                color: #475569;
                font-size: 12px;
                font-family: Consolas, Monaco, monospace;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        self._title_label = QLabel(_("No video loaded"))
        self._title_label.setObjectName("player_title")
        header_layout.addWidget(self._title_label, stretch=1)

        self._status_badge = QLabel("Idle")
        self._status_badge.setObjectName("player_badge")
        header_layout.addWidget(self._status_badge)
        layout.addLayout(header_layout)

        self._hint_label = QLabel("Preview is available while downloading")
        self._hint_label.setObjectName("player_hint")
        layout.addWidget(self._hint_label)

        self._video_container = QWidget()
        self._video_container.setObjectName("video_container")
        self._video_container.setMinimumHeight(280)
        self._video_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._video_container.installEventFilter(self)
        self._video_layout = QVBoxLayout(self._video_container)
        self._video_layout.setContentsMargins(0, 0, 0, 0)

        self._thumbnail_label = QLabel(_("No video"))
        self._thumbnail_label.setObjectName("player_thumbnail")
        self._thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbnail_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._video_layout.addWidget(self._thumbnail_label)

        self._overlay_label = QLabel("")
        self._overlay_label.setObjectName("player_overlay")
        self._overlay_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._overlay_label.setVisible(False)
        self._video_layout.addWidget(
            self._overlay_label,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )

        self._error_label = QLabel()
        self._error_label.setObjectName("player_error")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setVisible(False)
        self._video_layout.addWidget(
            self._error_label,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        layout.addWidget(self._video_container)

        self._controls_widget = QWidget()
        self._controls_widget.setObjectName("player_controls")
        controls_layout = QHBoxLayout(self._controls_widget)
        controls_layout.setContentsMargins(12, 10, 12, 10)
        controls_layout.setSpacing(10)

        self._play_pause_btn = QPushButton("Play")
        self._play_pause_btn.setObjectName("player_btn")
        self._play_pause_btn.clicked.connect(self._on_play_pause_clicked)
        controls_layout.addWidget(self._play_pause_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("player_btn")
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        controls_layout.addWidget(self._stop_btn)

        self._progress_slider = QSlider(Qt.Orientation.Horizontal)
        self._progress_slider.setObjectName("player_progress_slider")
        self._progress_slider.setRange(0, 1000)
        self._progress_slider.setValue(0)
        self._progress_slider.sliderPressed.connect(self._on_seek_started)
        self._progress_slider.sliderReleased.connect(self._on_seek_released)
        self._progress_slider.sliderMoved.connect(self._on_slider_moved)
        controls_layout.addWidget(self._progress_slider, stretch=1)

        self._time_label = QLabel("00:00 / 00:00")
        self._time_label.setObjectName("player_time_label")
        self._time_label.setMinimumWidth(110)
        controls_layout.addWidget(self._time_label)

        self._volume_label = QLabel("VOL")
        self._volume_label.setObjectName("player_volume_label")
        controls_layout.addWidget(self._volume_label)

        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setObjectName("player_volume_slider")
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(50)
        self._volume_slider.setMaximumWidth(100)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        controls_layout.addWidget(self._volume_slider)

        self._fullscreen_btn = QPushButton("Full")
        self._fullscreen_btn.setObjectName("player_btn")
        self._fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        controls_layout.addWidget(self._fullscreen_btn)

        layout.addWidget(self._controls_widget)

    def _apply_state(self):
        has_media = bool(self._current_file)
        active_playback = self._state in {"loading", "playing", "paused"}

        self._play_pause_btn.setEnabled(has_media and self._state != "error")
        self._play_pause_btn.setText("Pause" if self._state == "playing" else "Play")
        self._stop_btn.setEnabled(active_playback)
        self._volume_slider.setEnabled(has_media and self._state != "error")
        self._progress_slider.setEnabled(
            has_media and self._duration_ms > 0 and self._state in {"playing", "paused"}
        )

        badge_text = {
            "idle": "Idle",
            "loading": "Buffering",
            "playing": "Playing",
            "paused": "Paused",
            "error": "Error",
        }.get(self._state, self._state.title())
        badge_style = {
            "idle": "#e2e8f0; color: #475569;",
            "loading": "#dbeafe; color: #1d4ed8;",
            "playing": "#dcfce7; color: #166534;",
            "paused": "#fef3c7; color: #92400e;",
            "error": "#fee2e2; color: #b91c1c;",
        }.get(self._state, "#e2e8f0; color: #475569;")
        self._status_badge.setText(badge_text)
        self._status_badge.setStyleSheet(f"background: {badge_style}")

        if self._state == "error":
            self._hint_label.setText("Playback failed. Check VLC and the media file.")
        elif self._is_live_preview:
            self._hint_label.setText("Previewing an in-progress download")
        elif has_media:
            self._hint_label.setText("Ready for replay, pause and seeking")
        else:
            self._hint_label.setText("Preview is available while downloading")

        self._overlay_label.setVisible(self._state == "loading" or self._is_live_preview)
        if self._state == "loading":
            self._overlay_label.setText("Buffering video...")
        elif self._is_live_preview:
            self._overlay_label.setText("Live preview")

    def _set_video_surface(self):
        if self._media_player is None:
            return
        target_widget = self._fullscreen_window if self._is_fullscreen and self._fullscreen_window else self._video_container
        self._media_player.set_hwnd(int(target_widget.winId()))

    def _show_thumbnail(self, show: bool):
        self._thumbnail_label.setVisible(show)
        if show:
            self._thumbnail_label.raise_()

    def _show_error_message(self, message: str):
        self._error_label.setText(message)
        self._error_label.setVisible(True)
        self._error_label.raise_()
        self._thumbnail_label.setVisible(False)
        self._overlay_label.setVisible(False)

    def _clear_error(self):
        self._error_label.setVisible(False)

    def _hide_controls(self):
        if self._is_fullscreen:
            self._controls_widget.hide()

    def _toggle_fullscreen(self):
        if self._is_fullscreen:
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()

    def _enter_fullscreen(self):
        if self._is_fullscreen:
            return

        self._is_fullscreen = True
        self._fullscreen_window = QWidget()
        self._fullscreen_window.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self._fullscreen_window.setStyleSheet("background: black;")
        self._fullscreen_window.showFullScreen()
        self._fullscreen_window.installEventFilter(self)
        self._fullscreen_window.setFocus()

        self._video_container.setParent(self._fullscreen_window)
        self._controls_widget.setParent(self._fullscreen_window)
        self._video_container.setGeometry(self._fullscreen_window.rect())
        self._controls_widget.setGeometry(
            20,
            max(20, self._fullscreen_window.height() - 82),
            self._fullscreen_window.width() - 40,
            60,
        )
        self._video_container.show()
        self._controls_widget.show()
        self._set_video_surface()
        self._fullscreen_hide_timer.start(3000)

    def _exit_fullscreen(self):
        if not self._is_fullscreen:
            return

        self._is_fullscreen = False
        self._fullscreen_hide_timer.stop()

        if self._fullscreen_window is None:
            return

        self._fullscreen_window.removeEventFilter(self)
        self._fullscreen_window.close()
        self._fullscreen_window.deleteLater()
        self._fullscreen_window = None

        self._video_container.setParent(self)
        self._controls_widget.setParent(self)
        main_layout = self.layout()
        if main_layout is not None:
            main_layout.insertWidget(2, self._video_container)
            main_layout.insertWidget(3, self._controls_widget)
        self._video_container.show()
        self._controls_widget.show()
        self._set_video_surface()

    def eventFilter(self, obj, event):
        if obj == self._fullscreen_window:
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Escape:
                    self._exit_fullscreen()
                    return True
                if event.key() == Qt.Key.Key_Space:
                    self._on_play_pause_clicked()
                    return True
            elif event.type() == QEvent.Type.MouseMove:
                self._controls_widget.show()
                self._fullscreen_hide_timer.start(3000)
        if obj == self._video_container and event.type() == QEvent.Type.MouseButtonDblClick:
            self._toggle_fullscreen()
            return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._thumbnail_label.pixmap() is not None and not self._thumbnail_label.pixmap().isNull():
            self.set_thumbnail(self._thumbnail_label.pixmap())

    def set_video_info(self, title: str, bv_id: str):
        self._title_label.setText(f"{title}  |  {bv_id}")

    def show_error(self, message: str):
        self._state = "error"
        self._show_error_message(message)
        if self._media_player is not None:
            self._media_player.stop()
        self._update_timer.stop()
        self._apply_state()

    def load_file(self, file_path: str, preserve_position: bool = False) -> bool:
        if self._media_player is None or self._vlc_instance is None:
            self.show_error(_("VLC not available"))
            return False

        file_path = os.path.normpath(file_path)
        if not os.path.exists(file_path):
            self.show_error(_("File not found") + f": {os.path.basename(file_path)}")
            return False

        restore_time = -1
        if preserve_position and self._media_player is not None:
            restore_time = max(0, self._media_player.get_time())

        self._current_file = file_path
        self._is_live_preview = file_path.endswith(".part")
        self._duration_ms = 0
        self._pending_restore_time = restore_time
        self._is_seeking = False
        self._clear_error()
        self._show_thumbnail(False)

        media = self._vlc_instance.media_new("file:///" + file_path.replace("\\", "/"))
        if hasattr(media, "parse_async"):
            media.parse_async()
        self._media_player.set_media(media)
        self._set_video_surface()
        self._media_player.audio_set_volume(self._volume_slider.value())
        self._media_player.play()

        self._state = "loading"
        self._update_timer.start()
        self._apply_state()
        return True

    def play(self):
        if self._media_player is None:
            return
        if self._state == "paused":
            self._media_player.play()
            self._state = "playing"
            self._apply_state()
        elif self._state == "idle" and self._current_file:
            self.load_file(self._current_file, preserve_position=False)

    def pause(self):
        if self._media_player is None or self._state != "playing":
            return
        self._media_player.pause()
        self._state = "paused"
        self._apply_state()

    def stop(self):
        if self._media_player is None:
            return
        self._media_player.stop()
        self._state = "idle"
        self._duration_ms = 0
        self._pending_restore_time = -1
        self._show_thumbnail(True)
        self._progress_slider.setValue(0)
        self._time_label.setText("00:00 / 00:00")
        self._update_timer.stop()
        self._apply_state()

    def set_volume(self, level: int):
        if self._media_player is not None:
            self._media_player.audio_set_volume(level)

    def _on_play_pause_clicked(self):
        if self._state == "playing":
            self.pause()
        else:
            self.play()

    def _on_stop_clicked(self):
        self.stop()

    def _on_seek_started(self):
        self._is_seeking = True

    def _on_seek_released(self):
        if self._media_player is None or self._duration_ms <= 0:
            self._is_seeking = False
            return

        position = self._progress_slider.value() / 1000.0
        target_ms = int(self._duration_ms * position)
        self._media_player.set_time(target_ms)
        self._time_label.setText(f"{self._format_time(target_ms)} / {self._format_time(self._duration_ms)}")
        self._is_seeking = False

    def _on_slider_moved(self, value: int):
        if self._duration_ms <= 0:
            return
        current_ms = int(self._duration_ms * (value / 1000.0))
        self._time_label.setText(f"{self._format_time(current_ms)} / {self._format_time(self._duration_ms)}")

    def _on_volume_changed(self, value: int):
        self.set_volume(value)

    def _update_progress(self):
        if self._media_player is None:
            return

        player_state = self._media_player.get_state() if hasattr(self._media_player, "get_state") else None
        if player_state == vlc.State.Error:
            self.show_error(_("Playback failed"))
            return
        if player_state == vlc.State.Playing:
            self._state = "playing"
        elif player_state == vlc.State.Paused:
            self._state = "paused"
        elif player_state in {vlc.State.Opening, vlc.State.Buffering}:
            self._state = "loading"
        elif player_state == vlc.State.Ended and not self._is_live_preview:
            self.stop()
            return

        current_ms = max(0, self._media_player.get_time())
        length_ms = max(0, self._media_player.get_length())
        if length_ms > 0:
            self._duration_ms = length_ms

        if self._pending_restore_time > 0 and current_ms >= 0:
            self._media_player.set_time(self._pending_restore_time)
            self._pending_restore_time = -1

        if not self._is_seeking and self._duration_ms > 0:
            slider_value = int((current_ms / self._duration_ms) * 1000) if self._duration_ms else 0
            self._progress_slider.blockSignals(True)
            self._progress_slider.setValue(max(0, min(1000, slider_value)))
            self._progress_slider.blockSignals(False)

        total_label = self._format_time(self._duration_ms) if self._duration_ms > 0 else "--:--"
        self._time_label.setText(f"{self._format_time(current_ms)} / {total_label}")
        self._apply_state()

    @staticmethod
    def _format_time(ms: int) -> str:
        if ms <= 0:
            return "00:00"
        total_seconds = ms // 1000
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def set_thumbnail(self, pixmap: QPixmap):
        if pixmap.isNull():
            self._thumbnail_label.setText(_("No thumbnail"))
            self._thumbnail_label.setPixmap(QPixmap())
            return

        scaled = pixmap.scaled(
            max(1, self._video_container.width()),
            max(1, self._video_container.height()),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._thumbnail_label.setPixmap(scaled)
