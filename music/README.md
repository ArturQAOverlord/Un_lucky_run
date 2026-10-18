# Audio files

Place audio assets in the folders below. The game maps these fixed filenames in
`audio.py`; audio files are optional, so missing files stay silent.
Install the mixer dependency with `python -m pip install -r requirements.txt`.

```text
music/
├── background/
│   ├── lore.wav
│   ├── main_menu.wav
│   ├── collection.wav
│   ├── tournament.wav
│   └── combat.wav
└── effects/
    ├── ui/
    │   ├── button_click.wav
    │   ├── error.wav
    │   └── wheel_tick.wav
    ├── outcomes/
    │   ├── round_win.wav
    │   ├── round_loss.wav
    │   ├── arena_battle_win.wav
    │   ├── arena_battle_loss.wav
    │   ├── ladder_battle_win.wav
    │   ├── ladder_battle_loss.wav
    │   ├── ladder_run_win.wav
    │   ├── ladder_run_loss.wav
    │   ├── character_created.wav
    │   ├── stat_upgrade.wav
    │   ├── wheel_stop.wav
    │   └── tournament_complete.wav
    └── transitions/
        ├── combat_start.wav
        ├── tournament_start.wav
        └── ladder_start.wav
```

The five generated WAV background loops have distinct moods for the lore, main
menu, collection, tournament, and combat. WAV is used so these temporary tracks
work without an audio encoder; replace them with OGG later if desired, updating
the paths in `audio.py`. Keep filenames stable. Background tracks loop while
their section is open. The sound on/off and master volume
settings are saved with the other application options. Round win/loss effects
use the first fighter's result; ladder battle effects play after every ladder
fight, including intermediate wins.

All listed background tracks and effects are temporary synthesized WAVs,
ready to play and easy to replace later.
The error cue plays for error dialogs, not ordinary validation warnings. Arena
result cues describe the first fighter's result. A final ladder result uses its
run-level cue; intermediate wins use the ladder battle cue.

The character creation wheel plays `wheel_tick.wav` as its pointer crosses
segments and `wheel_stop.wav` when a value is selected, including when a spin
is skipped.
