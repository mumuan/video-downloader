from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QSizePolicy
from PyQt6.QtCore import Qt, QTimer, QSize, QEvent, QPoint, QRect
from PyQt6.QtGui import QPixmap, QKeyEvent, QEnterEvent
import vlc

from src.i18n import _


class VideoPlayerWidget(QWidget):
    """
    VLC-based video player widget with watch-while-downloading support.
    States: idle, playing, paused, error
    Supports fullscreen mode with hover-to-show controls.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("video_player_widget")
        self._state = "idle"
        self._vlc_instance: vlc.Instance | None = None
        self._media_player: vlc.MediaPlayer | None = None
        self._current_file: str | None = None
        self._current_media: vlc.Media | None = None
        self._thumbnail_loader = None
        self._is_fullscreen = False
        self._fullscreen_window: QWidget | None = None
        self._saved_geometry: QRect | None = None
        self._controls_opacity = 1.0
        self._fullscreen_hide_timer = QTimer(self)
        self._fullscreen_hide_timer.timeout.connect(self._hide_controls_animation)
        self._last_file_size = 0  # Track file size for growing .part files
        self._parse_attempts = 0  # Track how many times we've tried to re-parse
        # Initialize UI first (for error label), then VLC
        self._init_ui()
        self._init_vlc()
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_progress)

    def _init_vlc(self):
        """Initialize VLC instance and media player."""
        try:
            self._vlc_instance = vlc.Instance()
            self._media_player = self._vlc_instance.media_player_new()
        except Exception as e:
            self._state = "error"
            self._show_error_message(_("VLC initialization failed") + f": {str(e)}")

    def _init_ui(self):
        """Build the player UI with modern dark theme."""
        # Apply dark theme stylesheet
        self.setStyleSheet("""
            QLabel#player_title {
                color: #e0e0e0;
                font-size: 13px;
                padding: 4px 0;
            }
            QWidget#video_container {
                background-color: black;
                border-radius: 4px;
            }
            QLabel#player_thumbnail {
                background-color: #1a1a2e;
                color: #666;
                font-size: 16px;
            }
            QLabel#player_error {
                background-color: rgba(220, 50, 50, 0.9);
                color: white;
                font-size: 14px;
                border-radius: 4px;
            }
            QWidget#player_controls {
                background-color: rgba(30, 30, 40, 0.95);
                border-radius: 6px;
                padding: 8px 12px;
            }
            QPushButton#player_btn {
                background-color: transparent;
                color: #e0e0e0;
                border: none;
                font-size: 16px;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton#player_btn:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QPushButton#player_btn:pressed {
                background-color: rgba(255, 255, 255, 0.2);
            }
            QPushButton#player_btn:disabled {
                color: #666;
            }
            QSlider#player_progress_slider::groove:horizontal {
                border: none;
                height: 6px;
                background: #444;
                border-radius: 3px;
            }
            QSlider#player_progress_slider::handle:horizontal {
                background: #fff;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider#player_progress_slider::sub-page:horizontal {
                background: #ff6b6b;
                border-radius: 3px;
            }
            QSlider#player_volume_slider::groove:horizontal {
                border: none;
                height: 3px;
                background: #444;
                border-radius: 1.5px;
            }
            QSlider#player_volume_slider::handle:horizontal {
                background: #e0e0e0;
                width: 10px;
                margin: -3px 0;
                border-radius: 5px;
            }
            QSlider#player_volume_slider::sub-page:horizontal {
                background: #888;
                border-radius: 1.5px;
            }
            QLabel#player_time_label {
                color: #ccc;
                font-size: 12px;
                font-family: 'Consolas', 'Monaco', monospace;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)

        # Title and BV ID label
        self._title_label = QLabel(_("No video loaded"))
        self._title_label.setObjectName("player_title")
        layout.addWidget(self._title_label)

        # Video surface container with 16:9 aspect ratio
        self._video_container = QWidget()
        self._video_container.setObjectName("video_container")
        self._video_container.setVisible(True)
        self._video_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._video_container.installEventFilter(self)
        self._video_layout = QVBoxLayout(self._video_container)
        self._video_layout.setContentsMargins(0, 0, 0, 0)

        # Thumbnail label (shown when idle)
        self._thumbnail_label = QLabel(_("No video"))
        self._thumbnail_label.setObjectName("player_thumbnail")
        self._thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbnail_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._video_layout.addWidget(self._thumbnail_label)

        # Error label (shown when error)
        self._error_label = QLabel()
        self._error_label.setObjectName("player_error")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setVisible(False)
        self._video_layout.addWidget(self._error_label)

        layout.addWidget(self._video_container)

        # Control bar with dark theme
        self._controls_widget = QWidget()
        self._controls_widget.setObjectName("player_controls")
        controls_layout = QHBoxLayout(self._controls_widget)
        controls_layout.setSpacing(16)
        controls_layout.setContentsMargins(4, 4, 4, 4)

        # Play/Pause button (icon: ▶ / ❚❚)
        self._play_pause_btn = QPushButton("▶")
        self._play_pause_btn.setObjectName("player_btn")
        self._play_pause_btn.setFixedSize(36, 36)
        self._play_pause_btn.clicked.connect(self._on_play_pause_clicked)
        controls_layout.addWidget(self._play_pause_btn)

        # Stop button (icon: ■)
        self._stop_btn = QPushButton("■")
        self._stop_btn.setObjectName("player_btn")
        self._stop_btn.setFixedSize(36, 36)
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        controls_layout.addWidget(self._stop_btn)

        # Progress slider
        self._progress_slider = QSlider(Qt.Orientation.Horizontal)
        self._progress_slider.setObjectName("player_progress_slider")
        self._progress_slider.setRange(0, 1000)
        self._progress_slider.setValue(0)
        self._progress_slider.sliderMoved.connect(self._on_sliderMoved)
        self._progress_slider.setMinimumHeight(20)
        controls_layout.addWidget(self._progress_slider)

        # Time label
        self._time_label = QLabel("00:00 / 00:00")
        self._time_label.setObjectName("player_time_label")
        self._time_label.setMinimumWidth(90)
        controls_layout.addWidget(self._time_label)

        # Volume icon (dynamic)
        self._volume_icon = QLabel("🔈")
        self._volume_icon.setObjectName("player_btn")
        self._volume_icon.setFixedWidth(24)
        controls_layout.addWidget(self._volume_icon)

        # Volume slider
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setObjectName("player_volume_slider")
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(50)
        self._volume_slider.setMaximumWidth(80)
        self._volume_slider.setMinimumHeight(16)
        self._volume_slider.sliderMoved.connect(self._on_volumeChanged)
        controls_layout.addWidget(self._volume_slider)

        # Fullscreen button (icon: ⛶)
        self._fullscreen_btn = QPushButton("⛶")
        self._fullscreen_btn.setObjectName("player_btn")
        self._fullscreen_btn.setFixedSize(36, 36)
        self._fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        controls_layout.addWidget(self._fullscreen_btn)

        layout.addWidget(self._controls_widget)
        self._set_controls_enabled(False)

    def _set_video_surface(self):
        """Set the video output window for VLC."""
        if self._media_player is not None:
            # On Windows, use set_hwnd to embed in QWidget
            target_widget = self._fullscreen_window if self._is_fullscreen else self._video_container
            self._media_player.set_hwnd(target_widget.winId())

    def _show_thumbnail(self, show: bool):
        """Show or hide the thumbnail overlay."""
        self._thumbnail_label.setVisible(show)
        if show:
            self._thumbnail_label.raise_()

    def _show_error_message(self, message: str):
        """Display error message overlay."""
        self._error_label.setText(message)
        self._error_label.setVisible(True)
        self._error_label.raise_()
        self._thumbnail_label.setVisible(False)

    def _clear_error(self):
        """Clear error state."""
        self._error_label.setVisible(False)

    def _set_controls_enabled(self, enabled: bool):
        """Enable or disable playback controls."""
        self._play_pause_btn.setEnabled(enabled)
        self._stop_btn.setEnabled(enabled)
        self._progress_slider.setEnabled(enabled)
        self._volume_slider.setEnabled(enabled)

    def _hide_controls_animation(self):
        """Hide controls after timeout in fullscreen."""
        if self._is_fullscreen and self._controls_widget.isVisible():
            self._controls_widget.hide()
            self._fullscreen_hide_timer.stop()

    def _toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        if self._is_fullscreen:
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()

    def _enter_fullscreen(self):
        """Enter fullscreen mode."""
        if self._is_fullscreen:
            return
        self._is_fullscreen = True

        # Save current geometry
        self._saved_geometry = self._video_container.geometry()

        # Get screen geometry
        screen_geo = QApplication.primaryScreen().geometry()

        # Create fullscreen overlay window
        self._fullscreen_window = QWidget()
        self._fullscreen_window.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self._fullscreen_window.setStyleSheet("background-color: black;")
        self._fullscreen_window.setGeometry(screen_geo)
        self._fullscreen_window.showFullScreen()
        self._fullscreen_window.installEventFilter(self)
        self._fullscreen_window.setFocus()

        # Reparent video container to fullscreen window
        self._video_container.setParent(self._fullscreen_window)
        self._video_container.setGeometry(0, 0, screen_geo.width(), screen_geo.height() - 48)
        self._video_container.show()
        self._video_container.raise_()

        # Reparent controls to fullscreen window
        self._controls_widget.setParent(self._fullscreen_window)
        self._controls_widget.setGeometry(0, screen_geo.height() - 48, screen_geo.width(), 48)
        self._controls_widget.show()

        # Re-attach VLC to fullscreen window
        if self._media_player and self._current_file:
            self._set_video_surface()

        # Auto-hide controls after 3 seconds
        self._fullscreen_hide_timer.start(3000)

    def _exit_fullscreen(self):
        """Exit fullscreen mode."""
        if not self._is_fullscreen:
            return
        self._is_fullscreen = False
        self._fullscreen_hide_timer.stop()

        if self._fullscreen_window:
            self._fullscreen_window.removeEventFilter(self)

            # Stop playback temporarily
            was_playing = self._media_player and self._media_player.is_playing()
            if self._media_player:
                self._media_player.stop()

            # Close fullscreen window first (this unparents widgets automatically)
            self._fullscreen_window.close()
            self._fullscreen_window.deleteLater()
            self._fullscreen_window = None

            # Now re-parent widgets back and add to layout
            self._video_container.setParent(self)
            self._controls_widget.setParent(self)

            # Get main layout and re-add widgets in correct order
            main_layout = self.layout()
            if main_layout:
                # Insert at correct positions (0=title, 1=video, 2=controls)
                main_layout.insertWidget(1, self._video_container)
                main_layout.insertWidget(2, self._controls_widget)

            self._video_container.show()
            self._video_container.raise_()

            # Show controls
            self._controls_widget.show()

            # Re-attach VLC to video container
            if self._media_player and self._current_file:
                self._set_video_surface()
                # Resume playback if it was playing
                if was_playing:
                    self._media_player.play()

            # Let the layout manage geometry instead of using saved geometry
            # which may conflict after re-adding to layout
            self._video_container.updateGeometry()

            # Force UI update
            self.update()
            QApplication.processEvents()

    def eventFilter(self, obj, event):
        """Handle events for fullscreen window and double-click fullscreen."""
        if obj == self._fullscreen_window:
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Escape:
                    self._exit_fullscreen()
                    return True
                elif event.key() == Qt.Key.Key_Space:
                    self._on_play_pause_clicked()
                    return True
            elif event.type() == QEvent.Type.MouseMove:
                # Show controls on mouse move and reset hide timer
                if not self._controls_widget.isVisible():
                    self._controls_widget.show()
                self._fullscreen_hide_timer.stop()
                return True
            elif event.type() == QEvent.Type.MouseButtonPress:
                # Toggle controls visibility on click
                if self._controls_widget.isVisible():
                    self._fullscreen_hide_timer.start(3000)
                else:
                    self._controls_widget.show()
                    self._fullscreen_hide_timer.start(3000)
                return True
        # Handle double-click on video container for fullscreen toggle
        if obj == self._video_container:
            if event.type() == QEvent.Type.MouseButtonDblClick:
                self._toggle_fullscreen()
                return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        """Handle resize to maintain aspect ratio."""
        super().resizeEvent(event)
        # Update video container size to maintain 16:9
        if not self._is_fullscreen:
            width = self._video_container.width()
            if width > 0:
                height = int(width * 9 / 16)
                max_height = self._video_container.maximumHeight()
                if height > max_height and max_height > 0:
                    height = max_height
                self._video_container.setFixedHeight(height)
                self._thumbnail_label.setFixedSize(self._video_container.size())
                self._error_label.setFixedSize(self._video_container.size())

    def set_video_info(self, title: str, bv_id: str):
        """Set the video title and ID to display above player."""
        self._title_label.setText(f"{title}  |  {bv_id}")

    def show_error(self, message: str):
        """Set error state and display error message."""
        self._state = "error"
        self._show_error_message(message)
        self._set_controls_enabled(False)
        if self._media_player:
            self._media_player.stop()

    def load_file(self, file_path: str):
        """Load a video file and start playback."""
        if not self._media_player:
            self._state = "error"
            self._show_error_message(_("VLC not available"))
            return

        # Normalize path for Windows
        import os
        file_path = os.path.normpath(file_path)

        # Check if file exists before trying to play
        if not os.path.exists(file_path):
            self._state = "error"
            self._show_error_message(_("File not found") + f": {os.path.basename(file_path)}")
            return

        self._current_file = file_path
        self._clear_error()
        self._state = "idle"

        # Create media and assign to player
        # Use local file MRL format for Windows paths
        mrl = "file:///" + file_path.replace("\\", "/")
        media = self._vlc_instance.media_new(mrl)
        self._media_player.set_media(media)

        # Set the video output window
        self._set_video_surface()

        # Set volume
        self._media_player.audio_set_volume(self._volume_slider.value())

        # Start playback
        self._media_player.play()

        # Don't check is_playing() immediately - VLC needs time to transition through
        # Opening -> Buffering -> Playing states. Rely on _update_progress instead.
        self._update_timer.start(500)  # Update progress every 500ms

    def play(self):
        """Resume playback."""
        if self._media_player and self._state == "paused":
            self._media_player.play()
            self._state = "playing"
            self._play_pause_btn.setText("❚❚")
        elif self._media_player and self._state == "idle" and self._current_file:
            # Replay from stopped state - need to reload the media
            self._replay()

    def _replay(self):
        """Replay video from beginning after stop."""
        if not self._media_player or not self._current_file:
            return
        # Re-create media and reload
        import os
        mrl = "file:///" + self._current_file.replace(os.sep, "/")
        media = self._vlc_instance.media_new(mrl)
        self._media_player.set_media(media)
        self._set_video_surface()
        self._media_player.play()
        self._state = "playing"
        self._show_thumbnail(False)
        self._set_controls_enabled(True)
        self._play_pause_btn.setText("❚❚")
        self._update_timer.start(500)

    def pause(self):
        """Pause playback."""
        if self._media_player and self._state == "playing":
            self._media_player.pause()
            self._state = "paused"
            self._play_pause_btn.setText("▶")

    def stop(self):
        """Stop playback."""
        if self._media_player:
            self._media_player.stop()
            self._state = "idle"
            self._show_thumbnail(True)
            self._set_controls_enabled(False)
            self._play_pause_btn.setText("▶")
            self._progress_slider.setValue(0)
            self._time_label.setText("00:00 / 00:00")
            self._update_timer.stop()

    def set_volume(self, level: int):
        """Set volume (0-100)."""
        if self._media_player:
            self._media_player.audio_set_volume(level)

    def _on_play_pause_clicked(self):
        """Handle play/pause button click."""
        if self._state == "playing":
            self.pause()
        elif self._state == "paused":
            self.play()
        elif self._state == "idle" and self._current_file:
            self.play()

    def _on_stop_clicked(self):
        """Handle stop button click."""
        self.stop()

    def _on_sliderMoved(self, value: int):
        """Handle progress slider seek."""
        if self._media_player:
            # Convert slider value (0-1000) to position (0.0-1.0)
            position = value / 1000.0
            self._media_player.set_position(position)

    def _on_volumeChanged(self, value: int):
        """Handle volume slider change."""
        self.set_volume(value)
        # Update volume icon based on level
        if value == 0:
            self._volume_icon.setText("🔇")
        elif value < 33:
            self._volume_icon.setText("🔈")
        elif value < 66:
            self._volume_icon.setText("🔉")
        else:
            self._volume_icon.setText("🔊")

    def _update_progress(self):
        """Update progress slider and time label based on VLC state."""
        if not self._media_player:
            return

        is_playing = self._media_player.is_playing()

        # Check actual VLC state via is_playing()
        if is_playing:
            if self._state != "playing":
                self._state = "playing"
                self._show_thumbnail(False)
                self._set_controls_enabled(True)
                self._play_pause_btn.setText("❚❚")  # Pause icon

        # Try to get updated length, especially for growing .part files
        length = self._media_player.get_length()
        current_pos = self._media_player.get_position()

        # If length is 0 or seems wrong for a .part file, try to refresh
        if length <= 0 and self._current_file and self._current_file.endswith('.part'):
            import os
            if os.path.exists(self._current_file):
                # Re-parse the media to get updated info
                media = self._vlc_instance.media_new("file:///" + self._current_file.replace(os.sep, "/"))
                media.parse()
                length = media.get_duration()

        if length > 0:
            slider_value = int(current_pos * 1000)
            self._progress_slider.setValue(slider_value)

            # Update time label
            current_ms = int(current_pos * length)
            current_str = self._format_time(current_ms)
            total_str = self._format_time(length)
            self._time_label.setText(f"{current_str} / {total_str}")

    def _format_time(self, ms: int) -> str:
        """Format milliseconds to MM:SS or HH:MM:SS."""
        if ms <= 0:
            return "00:00"
        seconds = ms // 1000
        minutes = seconds // 60
        hours = minutes // 60
        seconds = seconds % 60
        minutes = minutes % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def set_thumbnail(self, pixmap: QPixmap):
        """Set thumbnail image to show when idle."""
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                self._video_container.width(), self._video_container.height(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self._thumbnail_label.setPixmap(scaled)
        else:
            self._thumbnail_label.setText(_("No thumbnail"))
            self._thumbnail_label.setPixmap(QPixmap())
