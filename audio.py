"""Optional audio playback for the Tkinter game."""

import logging
import time
from pathlib import Path

try:
    import pygame
except ImportError as error:  # Keep the game usable before its audio dependency is installed.
    pygame = None
    PYGAME_IMPORT_ERROR = str(error)
else:
    PYGAME_IMPORT_ERROR = None

try:
    from pygame._sdl2 import audio as sdl2_audio, sdl2
except ImportError:  # Without the SDL2 bindings only the system default output is used.
    sdl2_audio = sdl2 = None


logger = logging.getLogger(__name__)

AUDIO_DIR = Path(__file__).resolve().parent / 'music'

BACKGROUND_TRACKS = {
    'lore': 'background/lore.wav',
    'main_menu': 'background/main_menu.wav',
    'collection': 'background/collection.wav',
    'tournament': 'background/tournament.wav',
    'combat': 'background/combat.wav',
}

SOUND_EFFECTS = {
    'button_click': 'effects/ui/button_click.wav',
    'error': 'effects/ui/error.wav',
    'wheel_tick': 'effects/ui/wheel_tick.wav',
    'round_win': 'effects/outcomes/round_win.wav',
    'round_loss': 'effects/outcomes/round_loss.wav',
    'arena_battle_win': 'effects/outcomes/arena_battle_win.wav',
    'arena_battle_loss': 'effects/outcomes/arena_battle_loss.wav',
    'ladder_battle_win': 'effects/outcomes/ladder_battle_win.wav',
    'ladder_battle_loss': 'effects/outcomes/ladder_battle_loss.wav',
    'ladder_run_win': 'effects/outcomes/ladder_run_win.wav',
    'ladder_run_loss': 'effects/outcomes/ladder_run_loss.wav',
    'character_created': 'effects/outcomes/character_created.wav',
    'stat_upgrade': 'effects/outcomes/stat_upgrade.wav',
    'wheel_stop': 'effects/outcomes/wheel_stop.wav',
    'tournament_complete': 'effects/outcomes/tournament_complete.wav',
    'combat_start': 'effects/transitions/combat_start.wav',
    'tournament_start': 'effects/transitions/tournament_start.wav',
    'ladder_start': 'effects/transitions/ladder_start.wav',
}

MUSIC_GAIN = 0.55
EFFECT_GAIN = 0.8
# pygame's default 512-sample buffer crackles on some USB and Bluetooth outputs;
# 1024 samples (about 23 ms) is still unnoticeable for interface sounds.
MIXER_BUFFER = 1024
# Opening a device blocks the Tk thread (about half a second on a cold start), so
# after a failure automatic attempts back off from 5 seconds up to 5 minutes.
RETRY_DELAY = 5.0
MAX_RETRY_DELAY = 300.0
DEFAULT_DEVICE_LABEL = 'Системное по умолчанию'
# SDL and file errors explain themselves; anything else is logged with a traceback.
EXPECTED_ERRORS = tuple(
    error for error in (OSError, getattr(pygame, 'error', None), getattr(sdl2, 'error', None))
    if error is not None
)


def _describe(error):
    return str(error) or type(error).__name__


class AudioManager:
    """Play music and effects; audio problems are logged and reported, never raised."""

    def __init__(self, enabled=True, volume=0.7, device=None):
        self.enabled = bool(enabled)
        self.volume = self._clamp_volume(volume)
        self.device = device or None  # preferred output; None follows the system default
        self.active_device = None  # output actually open; None after a fallback to the default
        self.last_error = None  # latest problem, shown on the options page
        self.current_scene = None
        self._mixer_ready = False
        self._current_music_path = None
        self._sound_cache = {}
        self._device_present = False
        self._failures = 0
        self._retry_at = 0.0
        self._reported = set()
        if pygame is None:
            logger.warning('Звук недоступен: не удалось импортировать pygame (%s)', PYGAME_IMPORT_ERROR)
        else:
            logger.info('pygame %s, SDL %s', pygame.version.ver,
                        '.'.join(map(str, pygame.get_sdl_version())))

    @staticmethod
    def _clamp_volume(value):
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.7

    @staticmethod
    def device_label(device):
        return device or DEFAULT_DEVICE_LABEL

    @property
    def can_choose_device(self):
        return sdl2_audio is not None and sdl2 is not None

    def _log_problem(self, message, error=None, once=None, level=logging.WARNING):
        """Log an audio problem; problems with a `once` key are logged a single time."""
        if once is not None:
            if once in self._reported:
                return
            self._reported.add(once)
        if error is None:
            logger.log(level, '%s', message)
        else:
            logger.log(level, '%s: %s', message, _describe(error),
                       exc_info=None if isinstance(error, EXPECTED_ERRORS) else error)

    def _ensure_mixer(self):
        if pygame is None:
            return False
        if self._mixer_ready:
            return True
        if time.monotonic() < self._retry_at:
            return False
        return self._open_mixer()

    def _open_mixer(self):
        """Open the preferred output, falling back to the system default."""
        problems = []
        for device in dict.fromkeys((self.device, None)):
            try:
                pygame.mixer.init(buffer=MIXER_BUFFER, devicename=device)
            except Exception as error:  # SDL reports device trouble as pygame.error
                problems.append(f'«{self.device_label(device)}»: {_describe(error)}')
                self._log_problem(
                    f'Не удалось открыть аудиоустройство «{self.device_label(device)}»', error,
                )
                continue
            self._mixer_ready = True
            self.active_device = device
            self.last_error = None if device == self.device else (
                f'«{self.device}» недоступно — звук идёт на системное устройство.'
            )
            frequency, _format, channels = pygame.mixer.get_init()
            get_driver = getattr(pygame.mixer, 'get_driver', None)
            logger.info('Аудиовыход «%s»: %d Гц, %d кан., драйвер %s',
                        self.device_label(device), frequency, channels,
                        get_driver() if get_driver else 'неизвестен')
            devices = self._query_devices() if self.can_choose_device else None
            self._device_present = devices is not None and self.device in devices
            if devices is not None:
                logger.info('Устройства вывода: %s', '; '.join(devices) or 'не найдены')
            return True

        delay = self._postpone_retry()
        self.last_error = 'Не удалось открыть аудиоустройство: ' + '; '.join(problems)
        logger.error('Звук недоступен, следующая попытка через %.0f с', delay)
        return False

    def _postpone_retry(self):
        self._failures += 1
        delay = min(MAX_RETRY_DELAY, RETRY_DELAY * 2 ** (self._failures - 1))
        self._retry_at = time.monotonic() + delay
        return delay

    def _close_mixer(self):
        # A Sound belongs to the mixer that loaded it: playing one after
        # mixer.quit() crashes the interpreter, so the cache goes with the mixer.
        self._sound_cache.clear()
        self._current_music_path = None
        if not self._mixer_ready:
            return
        self._mixer_ready = False
        self.active_device = None
        try:
            pygame.mixer.quit()
        except Exception as error:
            self._log_problem('Не удалось закрыть аудиоустройство', error)

    def _reopen(self):
        """Reopen the output at once, e.g. after another device was chosen."""
        self._close_mixer()
        self._failures = 0
        self._retry_at = 0.0
        self.last_error = None
        if self.enabled and self._ensure_mixer() and self.current_scene is not None:
            self.play_music(self.current_scene)

    def _playback_failed(self, action, error):
        """The open device refused to work: close it and retry on a later call."""
        self._log_problem(f'Сбой воспроизведения ({action})', error, level=logging.ERROR)
        self._close_mixer()
        delay = self._postpone_retry()
        self.last_error = f'Сбой воспроизведения ({action}): {_describe(error)}'
        logger.info('Аудиоустройство будет переоткрыто через %.0f с', delay)

    def _file_exists(self, path):
        if path.is_file():
            return True
        self._log_problem(f'Аудиофайл не найден: {path}', once=('missing', path))
        return False

    def _query_devices(self):
        """Return output device names, or None when SDL cannot list them."""
        try:
            names = sdl2_audio.get_audio_device_names(False)
        except Exception as error:
            self._log_problem('Не удалось получить список аудиоустройств', error, once='list')
            return None
        return list(dict.fromkeys(names))

    def list_devices(self):
        """Return output device names, or an empty list when they cannot be listed."""
        if not self.can_choose_device:
            return []
        if self._mixer_ready:
            return self._query_devices() or []
        # Listing needs the SDL audio subsystem, but while it runs mixer.init()
        # silently does nothing, so the subsystem is shut down right away.
        try:
            sdl2.init_subsystem(sdl2.INIT_AUDIO)
        except Exception as error:
            self._log_problem('Не удалось запустить аудиоподсистему SDL', error, once='subsystem')
            return []
        devices = self._query_devices()
        try:
            pygame.mixer.quit()  # also stops the subsystem started above
        except Exception as error:
            self._log_problem('Не удалось остановить аудиоподсистему SDL', error)
        return devices or []

    def set_device(self, device):
        """Use another output device; None follows the system default."""
        device = device or None
        if device == self.device and self._mixer_ready and self.active_device == device:
            return
        self.device = device
        logger.info('Выбрано аудиоустройство: %s', self.device_label(device))
        self._reopen()

    def refresh(self):
        """Re-read the devices; reopen the output if it is down or on a fallback."""
        devices = self.list_devices()
        if self.enabled and (
            not self._mixer_ready
            or (self.device in devices and self.active_device != self.device)
        ):
            self._reopen()
        return devices

    def check_devices(self):
        """Follow the preferred device being unplugged or plugged back in.

        Cheap enough to poll every few seconds. Returns True if the output was
        reopened. A device that is listed but fails to open is not retried here,
        otherwise the music would restart on every poll.
        """
        if not self._mixer_ready or self.device is None:
            return False
        devices = self._query_devices()
        if devices is None:
            return False
        present = self.device in devices
        was_present, self._device_present = self._device_present, present
        if self.active_device == self.device and not present:
            logger.warning('Аудиоустройство «%s» отключено, переключаюсь на системное', self.device)
        elif self.active_device != self.device and present and not was_present:
            logger.info('Аудиоустройство «%s» снова подключено', self.device)
        else:
            return False
        self._reopen()
        return True

    def status(self):
        """Return (text, level) for the options page; level is 'ok', 'warning' or 'error'."""
        if pygame is None:
            return ('pygame-ce не установлен — звук недоступен. Установите зависимости: '
                    'python -m pip install -r requirements.txt', 'error')
        if not self.enabled:
            return 'Звук выключен.', 'ok'
        if not self._mixer_ready:
            if self.last_error:
                return self.last_error, 'error'
            return 'Устройство откроется при первом звуке.', 'ok'
        frequency, _format, channels = pygame.mixer.get_init()
        text = f'Вывод: {self.device_label(self.active_device)} · {frequency} Гц · {channels} кан.'
        if self.last_error:  # an open mixer only keeps the fallback notice
            return f'{text}\n{self.last_error}', 'warning'
        return text, 'ok'

    def _stop_music(self):
        if not self._mixer_ready:
            return
        try:
            pygame.mixer.music.stop()
        except Exception as error:
            self._playback_failed('остановка музыки', error)
            return
        self._current_music_path = None

    def _stop_all(self):
        if not self._mixer_ready:
            return
        try:
            pygame.mixer.stop()
            pygame.mixer.music.stop()
        except Exception as error:
            self._playback_failed('остановка звука', error)
            return
        self._current_music_path = None

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if not self.enabled:
            self._stop_all()
            return
        self._failures = 0
        self._retry_at = 0.0  # the player asked for sound: try the device right away
        if self._ensure_mixer() and self.current_scene is not None:
            self.play_music(self.current_scene)

    def set_volume(self, volume):
        self.volume = self._clamp_volume(volume)
        if not self._mixer_ready:
            return
        try:
            pygame.mixer.music.set_volume(self.volume * MUSIC_GAIN)
            for sound in self._sound_cache.values():
                sound.set_volume(self.volume * EFFECT_GAIN)
        except Exception as error:
            self._playback_failed('громкость', error)

    def play_music(self, scene):
        self.current_scene = scene
        track_relative_path = BACKGROUND_TRACKS.get(scene)
        if not self.enabled or track_relative_path is None:
            self._stop_music()
            return

        track_path = AUDIO_DIR / track_relative_path
        if not self._file_exists(track_path):
            self._stop_music()
            return
        if not self._ensure_mixer():
            return

        try:
            if self._current_music_path == track_path and pygame.mixer.music.get_busy():
                pygame.mixer.music.set_volume(self.volume * MUSIC_GAIN)
                return
            pygame.mixer.music.stop()
        except Exception as error:
            self._playback_failed(f'музыка «{scene}»', error)
            return
        self._current_music_path = None
        try:
            pygame.mixer.music.load(str(track_path))
        except Exception as error:
            self._log_problem(f'Не удалось загрузить музыку {track_path}', error,
                              once=('load', track_path))
            return
        try:
            pygame.mixer.music.set_volume(self.volume * MUSIC_GAIN)
            pygame.mixer.music.play(loops=-1)
        except Exception as error:
            self._playback_failed(f'музыка «{scene}»', error)
            return
        self._current_music_path = track_path
        self._failures = 0

    def play_effect(self, name):
        if not self.enabled:
            return
        effect_relative_path = SOUND_EFFECTS.get(name)
        if effect_relative_path is None:
            self._log_problem(f'Неизвестный звуковой эффект: {name}', once=('unknown', name))
            return
        effect_path = AUDIO_DIR / effect_relative_path
        if not self._file_exists(effect_path) or not self._ensure_mixer():
            return

        sound = self._sound_cache.get(effect_path)
        if sound is None:
            try:
                sound = pygame.mixer.Sound(str(effect_path))
            except Exception as error:
                self._log_problem(f'Не удалось загрузить эффект {effect_path}', error,
                                  once=('load', effect_path))
                return
            self._sound_cache[effect_path] = sound
        try:
            sound.set_volume(self.volume * EFFECT_GAIN)
            sound.play()
        except Exception as error:
            self._playback_failed(f'эффект «{name}»', error)
            return
        self._failures = 0

    def close(self):
        self._close_mixer()
