from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QSizePolicy
from PyQt6.QtCore import Qt, QTimer, QSize, QEvent
from PyQt6.QtGui import QPixmap, QKeyEvent
import vlc

from src.i18n import _


class VideoPlayerWidget(QWidget):
    """
    VLC-based video player widget with watch-while-downloading support.
    States: idle, playing, paused, error
    Supports fullscreen mode.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("video_player_widget")
        self._state = "idle"
        self._vlc_instance: vlc.Instance | None = None
        self._media_player: vlc.MediaPlayer | None = None
        self._current_file: str | None = None
        self._thumbnail_loader = None
        self._is_fullscreen = False
        self._fullscreen_window: QWidget | None = None
        self._saved_geometry: QSize | None = None
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
        """Build the player UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Title and BV ID label
        self._title_label = QLabel(_("No video loaded"))
        self._title_label.setObjectName("player_title")
        layout.addWidget(self._title_label)

        # Video surface container with 16:9 aspect ratio
        self._video_container = QWidget()
        self._video_container.setObjectName("video_container")
        self._video_container.setStyleSheet("background-color: black;")
        self._video_container.setVisible(True)
        # Set size policy to respect aspect ratio
        self._video_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._video_layout = QVBoxLayout(self._video_container)
        self._video_layout.setContentsMargins(0, 0, 0, 0)

        # Thumbnail label (shown when idle)
        self._thumbnail_label = QLabel(_("No video"))
        self._thumbnail_label.setObjectName("player_thumbnail")
        self._thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbnail_label.setStyleSheet("background-color: #1a1a2e; color: #888;")
        self._thumbnail_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._video_layout.addWidget(self._thumbnail_label)

        # Error label (shown when error)
        self._error_label = QLabel()
        self._error_label.setObjectName("player_error")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setStyleSheet("background-color: rgba(220, 50, 50, 0.9); color: white; padding: 10px;")
        self._error_label.setVisible(False)
        self._video_layout.addWidget(self._error_label)

        layout.addWidget(self._video_container)

        # Control bar
        self._controls_widget = QWidget()
        self._controls_widget.setObjectName("player_controls")
        controls_layout = QHBoxLayout(self._controls_widget)
        controls_layout.setSpacing(12)

        # Play/Pause button
        self._play_pause_btn = QPushButton(_("Play"))
        self._play_pause_btn.setObjectName("player_play_pause_btn")
        self._play_pause_btn.setFixedSize(60, 28)
        self._play_pause_btn.clicked.connect(self._on_play_pause_clicked)
        controls_layout.addWidget(self._play_pause_btn)

        # Stop button
        self._stop_btn = QPushButton(_("Stop"))
        self._stop_btn.setObjectName("player_stop_btn")
        self._stop_btn.setFixedSize(50, 28)
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        controls_layout.addWidget(self._stop_btn)

        # Progress slider
        self._progress_slider = QSlider(Qt.Orientation.Horizontal)
        self._progress_slider.setObjectName("player_progress_slider")
        self._progress_slider.setRange(0, 1000)
        self._progress_slider.setValue(0)
        self._progress_slider.sliderMoved.connect(self._on_sliderMoved)
        controls_layout.addWidget(self._progress_slider)

        # Time label
        self._time_label = QLabel("00:00 / 00:00")
        self._time_label.setObjectName("player_time_label")
        self._time_label.setMinimumWidth(100)
        controls_layout.addWidget(self._time_label)

        # Volume label
        volume_label = QLabel(_("Vol:"))
        controls_layout.addWidget(volume_label)

        # Volume slider
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setObjectName("player_volume_slider")
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(50)
        self._volume_slider.setMaximumWidth(80)
        self._volume_slider.sliderMoved.connect(self._on_volumeChanged)
        controls_layout.addWidget(self._volume_slider)

        # Fullscreen button
        self._fullscreen_btn = QPushButton(_("Fullscreen"))
        self._fullscreen_btn.setObjectName("player_fullscreen_btn")
        self._fullscreen_btn.setFixedSize(80, 28)
        self._fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        controls_layout.addWidget(self._fullscreen_btn)

        controls_layout.addStretch()

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

        # Create fullscreen window
        self._fullscreen_window = QWidget()
        self._fullscreen_window.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self._fullscreen_window.setStyleSheet("background-color: black;")
        self._fullscreen_window.setGeometry(self._video_container.geometry())

        # Move video surface to fullscreen window
        self._video_container.setParent(self._fullscreen_window)
        self._video_container.setGeometry(0, 0, self._fullscreen_window.width(), self._fullscreen_window.height())
        self._video_container.show()
        self._thumbnail_label.setGeometry(0, 0, self._fullscreen_window.width(), self._fullscreen_window.height())
        self._error_label.setGeometry(0, 0, self._fullscreen_window.width(), self._fullscreen_window.height())

        # Re-attach VLC to fullscreen window
        if self._media_player and self._current_file:
            self._set_video_surface()

        self._fullscreen_window.showFullScreen()
        self._fullscreen_window.installEventFilter(self)

        # Hide controls in fullscreen (they'll be shown on mouse move)
        self._controls_widget.hide()

    def _exit_fullscreen(self):
        """Exit fullscreen mode."""
        if not self._is_fullscreen:
            return
        self._is_fullscreen = False

        if self._fullscreen_window:
            self._fullscreen_window.removeEventFilter(self)
            # Move video surface back
            self._video_container.setParent(self)
            self._video_container.setGeometry(0, 0, 640, 360)
            self._video_container.show()
            self._thumbnail_label.setGeometry(0, 0, 640, 360)
            self._error_label.setGeometry(0, 0, 640, 360)

            # Re-attach VLC
            if self._media_player and self._current_file:
                self._set_video_surface()

            self._fullscreen_window.close()
            self._fullscreen_window.deleteLater()
            self._fullscreen_window = None

        self._controls_widget.show()

    def eventFilter(self, obj, event):
        """Handle events for fullscreen window."""
        if obj == self._fullscreen_window:
            if event.type() == QEvent.Type.KeyPress:
                key_event = QKeyEvent(event)
                if key_event.key() == Qt.Key.Key_Escape:
                    self._exit_fullscreen()
                    return True
                elif key_event.key() == Qt.Key.Key_Space:
                    self._on_play_pause_clicked()
                    return True
            elif event.type() == QEvent.Type.MouseMove:
                # Show controls on mouse move
                self._controls_widget.show()
                return True
            elif event.type() == QEvent.Type.MouseButtonPress:
                # Toggle controls visibility on click
                if self._controls_widget.isVisible():
                    self._controls_widget.hide()
                else:
                    self._controls_widget.show()
                return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        """Handle resize to maintain aspect ratio."""
        super().resizeEvent(event)
        # Update video container size to maintain 16:9
        if not self._is_fullscreen:
            width = self._video_container.width()
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
        media = self._vlc_instance.media_new("file:///" + file_path.replace("\\", "/"))
        self._media_player.set_media(media)

        # Set the video output window
        self._set_video_surface()

        # Set volume
        self._media_player.audio_set_volume(self._volume_slider.value())

        # Start playback
        self._media_player.play()
        self._state = "playing"
        self._show_thumbnail(False)
        self._set_controls_enabled(True)
        self._play_pause_btn.setText(_("Pause"))
        self._update_timer.start(500)  # Update progress every 500ms

    def play(self):
        """Resume playback."""
        if self._media_player and self._state == "paused":
            self._media_player.play()
            self._state = "playing"
            self._play_pause_btn.setText(_("Pause"))

    def pause(self):
        """Pause playback."""
        if self._media_player and self._state == "playing":
            self._media_player.pause()
            self._state = "paused"
            self._play_pause_btn.setText(_("Play"))

    def stop(self):
        """Stop playback."""
        if self._media_player:
            self._media_player.stop()
            self._state = "idle"
            self._show_thumbnail(True)
            self._set_controls_enabled(False)
            self._play_pause_btn.setText(_("Play"))
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
            self._media_player.play()
            self._state = "playing"

    def _on_stop_clicked(self):
        """Handle stop button click."""
        self.stop()

    def _on_sliderMoved(self, value: int):
        """Handle progress slider seek."""
        if self._media_player and self._media_player.get_length() > 0:
            # Convert slider value (0-1000) to position (0.0-1.0)
            position = value / 1000.0
            self._media_player.set_position(position)

    def _on_volumeChanged(self, value: int):
        """Handle volume slider change."""
        self.set_volume(value)

    def _update_progress(self):
        """Update progress slider and time label based on VLC state."""
        if not self._media_player:
            return

        # Check actual VLC state via is_playing()
        if self._media_player.is_playing():
            self._state = "playing"
            self._show_thumbnail(False)
            self._set_controls_enabled(True)
            self._play_pause_btn.setText(_("Pause"))
        elif self._state == "playing" and not self._media_player.is_playing():
            # Was playing but now stopped
            pass  # Keep current state, let timer handle it

        length = self._media_player.get_length()
        if length > 0:
            position = self._media_player.get_position()
            self._progress_slider.setValue(int(position * 1000))

            # Update time label
            current_ms = int(position * length)
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
