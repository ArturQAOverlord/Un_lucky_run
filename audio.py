"""Optional audio playback for the Tkinter game."""

from pathlib import Path

try:
    import pygame
except ImportError:  # Keep the game usable before its audio dependency is installed.
    pygame = None


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
    'tournament_complete': 'effects/outcomes/tournament_complete.wav',
    'combat_start': 'effects/transitions/combat_start.wav',
    'tournament_start': 'effects/transitions/tournament_start.wav',
    'ladder_start': 'effects/transitions/ladder_start.wav',
}

MUSIC_GAIN = 0.55
EFFECT_GAIN = 0.8


class AudioManager:
    """Load configured files on demand and keep audio failures out of game logic."""

    def __init__(self, enabled=True, volume=0.7):
        self.enabled = bool(enabled)
        self.volume = self._clamp_volume(volume)
        self.current_scene = None
        self._mixer_ready = False
        self._current_music_path = None
        self._sound_cache = {}

    @staticmethod
    def _clamp_volume(value):
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.7

    def _ensure_mixer(self):
        if pygame is None:
            return False
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            self._mixer_ready = True
            return True
        except Exception:
            self._mixer_ready = False
            return False

    def _stop_music(self):
        if pygame is None or not self._mixer_ready:
            return
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        self._current_music_path = None

    def _stop_all(self):
        if pygame is None or not self._mixer_ready:
            return
        try:
            pygame.mixer.stop()
            pygame.mixer.music.stop()
        except Exception:
            pass
        self._current_music_path = None

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if not self.enabled:
            self._stop_all()
        elif self.current_scene is not None:
            self.play_music(self.current_scene)

    def set_volume(self, volume):
        self.volume = self._clamp_volume(volume)
        if pygame is None or not self._mixer_ready:
            return
        try:
            pygame.mixer.music.set_volume(self.volume * MUSIC_GAIN)
            for sound in self._sound_cache.values():
                sound.set_volume(self.volume * EFFECT_GAIN)
        except Exception:
            pass

    def play_music(self, scene):
        self.current_scene = scene
        track_relative_path = BACKGROUND_TRACKS.get(scene)
        if not self.enabled or track_relative_path is None:
            self._stop_music()
            return

        track_path = AUDIO_DIR / track_relative_path
        if not track_path.is_file():
            self._stop_music()
            return
        if not self._ensure_mixer():
            return

        if self._current_music_path == track_path and pygame.mixer.music.get_busy():
            self.set_volume(self.volume)
            return
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(str(track_path))
            pygame.mixer.music.set_volume(self.volume * MUSIC_GAIN)
            pygame.mixer.music.play(loops=-1)
            self._current_music_path = track_path
        except Exception:
            self._current_music_path = None

    def play_effect(self, name):
        if not self.enabled:
            return
        effect_relative_path = SOUND_EFFECTS.get(name)
        if effect_relative_path is None:
            return
        effect_path = AUDIO_DIR / effect_relative_path
        if not effect_path.is_file() or not self._ensure_mixer():
            return

        cache_key = str(effect_path)
        sound = self._sound_cache.get(cache_key)
        if sound is None:
            try:
                sound = pygame.mixer.Sound(str(effect_path))
            except Exception:
                return
            self._sound_cache[cache_key] = sound
        try:
            sound.set_volume(self.volume * EFFECT_GAIN)
            sound.play()
        except Exception:
            pass

    def close(self):
        self._stop_all()
        if pygame is not None and self._mixer_ready:
            try:
                pygame.mixer.quit()
            except Exception:
                pass
        self._mixer_ready = False
